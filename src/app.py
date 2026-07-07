# app.py
import platform
import tkinter as tk
from tkinter import ttk, messagebox

from constants import COLORS, WINDOW
from styles import configure_styles
from ui import (
    build_header,
    build_controls_panel,
    build_preview_panel,
    build_footer,
)

from services import detect_cameras_for_current_os, PreviewService

try:
    from src.services.windows_engine_service import WindowsEngineService
except ImportError:
    WindowsEngineService = None


class CamCompositeApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(WINDOW["title"])
        self.geometry(WINDOW["size"])
        self.resizable(False, False)

        self.colors = COLORS
        self.current_os = platform.system()
        self.pipeline_running = False

        self.selected_cameras = []
        self.max_cameras = 4
        self.camera_check_vars = {}
        self.camera_check_widgets = []
        self.detected_cameras = []
        self.layout_disabled = False
        self.layout_tiles = {}

        self.obs_controller = None

        if self.current_os == "Darwin":
            from src.utils.obs_mac_controller import MacOBSController

            self.obs_controller = MacOBSController(
                scene_name="CamComposite",
                port=4455,
                password="mylens123",
            )

        self.mode_var = tk.StringVar(value="single")
        self.swapped_var = tk.BooleanVar(value=False)
        self.preview_var = tk.BooleanVar(value=True)
        self.auto_hide_obs_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")
        self.setup_var = tk.StringVar(value="Setup not checked yet")
        self.preview_text_var = tk.StringVar(value="Camera preview will appear here")
        self.footer_message_var = tk.StringVar(value="Developed by - @ashish.karigar")

        configure_styles(self, self.colors)
        self._build_layout()
        self._set_platform_defaults()
        self.after(200, self.detect_cameras)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.preview_service = PreviewService(self)
        self.frame_forwarder = None
        self.windows_engine_service = None

        if self.current_os == "Darwin":
            from src.utils.ndi_frame_sender import NDIFrameSender

            self.frame_forwarder = NDIFrameSender()
            self.preview_service.set_frame_forwarder(self.frame_forwarder)

        elif self.current_os == "Windows":
            if WindowsEngineService is not None:
                self.windows_engine_service = WindowsEngineService()

            # Windows output:
            # video_engine.exe -> shared memory -> Cam-Composite DirectShow camera.
            # No UnityCapture, no cpp_latest_frame.jpg, no CppFrameSender.
            self.frame_forwarder = None
            self.preview_service.set_frame_forwarder(None)

        else:
            self.preview_service.set_frame_forwarder(None)

    def _selected_camera_objects(self):
        selected = []
        for selected_id in self.selected_cameras:
            for cam in self.detected_cameras:
                if str(cam["id"]) == str(selected_id):
                    selected.append(cam)
                    break
        return selected

    def _build_layout(self):
        root = ttk.Frame(self, style="App.TFrame", padding=22)
        root.pack(fill="both", expand=True)

        build_header(root)

        body = ttk.Frame(root, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(18, 0))
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        build_controls_panel(self, body)
        build_preview_panel(self, body)
        build_footer(self, root)

    def set_footer_message(self, message, is_error=False):
        self.footer_message_var.set(message)
        if hasattr(self, "footer_label"):
            self.footer_label.configure(
                foreground=(self.colors["error"] if is_error else self.colors["muted"])
            )

    def clear_footer_message(self):
        self.set_footer_message("Developed by - @ashish.karigar", is_error=False)

    def _set_platform_defaults(self):
        if self.current_os == "Darwin":
            self.setup_var.set("macOS backend available")
        elif self.current_os == "Windows":
            self.setup_var.set("Windows DirectShow backend available")
        else:
            self.setup_var.set(f"Unsupported or untested platform: {self.current_os}")

    def run_setup_check(self):
        if self.current_os == "Darwin":
            self.setup_var.set("macOS setup looks ready to be connected")
        elif self.current_os == "Windows":
            if self.windows_engine_service is None:
                self.setup_var.set("Windows video engine service unavailable")
            else:
                self.setup_var.set("Windows DirectShow setup looks ready")
        else:
            self.setup_var.set("Unsupported platform for automated setup checks")

    def _clear_camera_check_widgets(self):
        for widget in self.camera_check_widgets:
            widget.destroy()
        self.camera_check_widgets.clear()
        self.camera_check_vars.clear()

    def _populate_camera_selectors(self):
        self._clear_camera_check_widgets()
        self.selected_cameras = []

        if not self.detected_cameras:
            lbl = tk.Label(
                self.cameras_frame,
                text="No cameras detected",
                bg=self.colors["panel"],
                fg=self.colors["muted"],
                font=("Helvetica", 10),
                anchor="w",
            )
            lbl.pack(anchor="w", pady=(8, 0))
            self.camera_check_widgets.append(lbl)
            self._set_layout_state(disable=False)
            return

        for cam in self.detected_cameras:
            cam_id = str(cam["id"])
            cam_name = cam["name"]

            var = tk.BooleanVar(value=False)
            self.camera_check_vars[cam_id] = var

            cb = tk.Checkbutton(
                self.cameras_frame,
                text=cam_name,
                variable=var,
                command=lambda cid=cam_id: self._on_camera_checkbox_toggle(cid),
                bg=self.colors["panel"],
                fg=self.colors["text"],
                activebackground=self.colors["panel"],
                activeforeground=self.colors["text"],
                selectcolor=self.colors["accent"],
                highlightthickness=0,
                bd=0,
                relief="flat",
                font=("Helvetica", 11),
                anchor="w",
                padx=4,
                pady=6,
            )
            cb.pack(fill="x", anchor="w", pady=(6, 0))
            self.camera_check_widgets.append(cb)

        if len(self.detected_cameras) == 1:
            only_id = str(self.detected_cameras[0]["id"])
            self.camera_check_vars[only_id].set(True)
            self.selected_cameras = [only_id]
            self.mode_var.set("single")
            self._set_layout_state(disable=True)

            if self.pipeline_running and self.current_os == "Windows":
                self._show_broadcasting_message()
            else:
                self.preview_text_var.set("Single camera detected and selected automatically")
                self.after(100, self.refresh_preview)
        else:
            first_id = str(self.detected_cameras[0]["id"])
            self.camera_check_vars[first_id].set(True)
            self.selected_cameras = [first_id]
            self.mode_var.set("single")
            self._set_layout_state(disable=False)

            if self.pipeline_running and self.current_os == "Windows":
                self._show_broadcasting_message()
            else:
                self.preview_text_var.set(f"Selected: {self._camera_name_from_id(first_id)}")
                self.after(100, self.refresh_preview)

    def _on_camera_checkbox_toggle(self, cam_id):
        selected = [cid for cid, var in self.camera_check_vars.items() if var.get()]

        if len(selected) > self.max_cameras:
            self.camera_check_vars[cam_id].set(False)
            self.set_footer_message(f"You can select a maximum of {self.max_cameras} cameras.", is_error=True)
            selected = [cid for cid, var in self.camera_check_vars.items() if var.get()]
        else:
            self.clear_footer_message()

        self.selected_cameras = selected

        if len(self.detected_cameras) == 1:
            self.mode_var.set("single")
            self._set_layout_state(disable=True)

            if self.pipeline_running and self.current_os == "Windows":
                self._restart_windows_engine_if_running()
            else:
                self.refresh_preview()

            return

        selected_count = len(self.selected_cameras)

        if selected_count < 2 and self.mode_var.get() != "single":
            self.mode_var.set("single")
            self.preview_text_var.set("Select more cameras to enable multi-camera layouts")

        allowed_layouts = self._allowed_layouts_for_selection_count(selected_count)
        if self.mode_var.get() not in allowed_layouts:
            self.mode_var.set(allowed_layouts[0])

        self._refresh_layout_tiles()

        names = [self._camera_name_from_id(cid) for cid in self.selected_cameras]

        if self.pipeline_running and self.current_os == "Windows":
            self._restart_windows_engine_if_running()
        else:
            if names:
                self.preview_text_var.set("Selected: " + ", ".join(names))
            else:
                self.preview_text_var.set("No cameras selected")

            self.refresh_preview()

    def _camera_name_from_id(self, cam_id):
        for cam in self.detected_cameras:
            if str(cam["id"]) == str(cam_id):
                return cam["name"]
        return f"Camera {cam_id}"

    def _on_close(self):
        try:
            if self.obs_controller is not None:
                self.obs_controller.stop()
        except Exception as e:
            print(f"OBS close warning: {e}")

        try:
            self.preview_service.stop()
        except Exception as e:
            print(f"Preview close warning: {e}")

        try:
            if self.windows_engine_service is not None:
                self.windows_engine_service.stop()
            if self.frame_forwarder is not None:
                self.frame_forwarder.stop()
        except Exception as e:
            print(f"Frame forwarder close warning: {e}")

        self.destroy()

    def _refresh_layout_tiles(self):
        if not hasattr(self, "layout_tiles"):
            return

        for key, frame in self.layout_tiles.items():
            if key == self.mode_var.get():
                frame.configure(highlightbackground=self.colors["accent"], highlightthickness=2)
            else:
                frame.configure(highlightbackground=self.colors["border"], highlightthickness=1)

            if self.layout_disabled and key != "single":
                frame.configure(bg=self.colors["disabled_tile"])
                for child in frame.winfo_children():
                    try:
                        child.configure(bg=self.colors["disabled_tile"])
                    except Exception:
                        pass
            else:
                frame.configure(bg=self.colors["panel_2"])
                for child in frame.winfo_children():
                    try:
                        child.configure(bg=self.colors["panel_2"])
                    except Exception:
                        pass

    def select_layout(self, mode_key):
        if self.layout_disabled and mode_key != "single":
            return

        allowed_layouts = self._allowed_layouts_for_selection_count(len(self.selected_cameras))
        if mode_key not in allowed_layouts:
            required = {
                "pip": 2,
                "sbs": 2,
                "stacked": 2,
                "triple": 3,
                "quad": 4,
            }.get(mode_key, 1)
            self.set_footer_message(f"Select {required} cameras to use this layout.", is_error=True)
            return

        self.mode_var.set(mode_key)
        self._refresh_layout_tiles()
        self.clear_footer_message()

        if self.pipeline_running and self.current_os == "Windows":
            self._restart_windows_engine_if_running()
        else:
            self.preview_text_var.set(f"{self._layout_label(mode_key)} selected")
            self.refresh_preview()

    def _set_layout_state(self, disable=False):
        self.layout_disabled = disable

        if disable:
            self.mode_var.set("single")

        self._refresh_layout_tiles()

    def _allowed_layouts_for_selection_count(self, count):
        if count <= 1:
            return ["single"]
        if count == 2:
            return ["single", "pip", "sbs", "stacked"]
        if count == 3:
            return ["single", "pip", "sbs", "stacked", "triple"]
        return ["single", "pip", "sbs", "stacked", "triple", "quad"]

    def _layout_label(self, mode_key):
        labels = {
            "pip": "Picture in Picture",
            "sbs": "Side by Side",
            "stacked": "Top and Bottom",
            "single": "Single Camera",
            "triple": "3 Camera Grid",
            "quad": "4 Camera Grid",
        }
        return labels.get(mode_key, mode_key)

    def swap_cameras(self):
        if len(self.selected_cameras) < 2:
            self.set_footer_message("Select at least 2 cameras to swap the first two feeds.", is_error=True)
            return

        self.selected_cameras[0], self.selected_cameras[1] = self.selected_cameras[1], self.selected_cameras[0]
        self.swapped_var.set(not self.swapped_var.get())
        self.clear_footer_message()

        if self.pipeline_running and self.current_os == "Windows":
            self._restart_windows_engine_if_running()
        else:
            self.preview_text_var.set("Camera feeds swapped")
            self.refresh_preview()

        if self.pipeline_running:
            mode = self.mode_var.get()
            self.status_var.set(
                f"Running: {self._camera_name_from_id(self.selected_cameras[0])}, "
                f"{self._camera_name_from_id(self.selected_cameras[1])}, "
                f"{self._layout_label(mode)}"
            )

    def _show_broadcasting_message(self):
        self.preview_text_var.set("Broadcast started")

        if hasattr(self, "preview_text_label"):
            self.preview_text_label.configure(
                font=("Helvetica", 12, "normal"),
                fg=self.colors["muted"],
            )
            self.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")

    def _restart_windows_engine_if_running(self):
        if self.current_os != "Windows":
            return

        if not self.pipeline_running:
            return

        if self.windows_engine_service is None:
            return

        if not self.selected_cameras:
            return

        try:
            # Important: preview must be stopped while broadcasting on Windows,
            # otherwise it can steal the camera from video_engine.exe.
            self.preview_service.stop()

            self.windows_engine_service.start(
                self.mode_var.get(),
                self.selected_cameras,
            )

            self._show_broadcasting_message()

            self.status_var.set(
                f"Running: {', '.join([self._camera_name_from_id(cid) for cid in self.selected_cameras])}, "
                f"{self._layout_label(self.mode_var.get())}"
            )
        except Exception as e:
            self.set_footer_message(f"Could not restart Windows engine: {e}", is_error=True)

    def start_pipeline(self):
        if self.pipeline_running:
            self.set_footer_message("Pipeline is already running.", is_error=True)
            return

        if not self.selected_cameras:
            self.set_footer_message("Please detect and select at least 1 camera.", is_error=True)
            return

        required_counts = {
            "single": 1,
            "pip": 2,
            "sbs": 2,
            "stacked": 2,
            "triple": 3,
            "quad": 4,
        }
        required = required_counts.get(self.mode_var.get(), 1)

        if len(self.selected_cameras) < required:
            self.set_footer_message(
                f"Please select at least {required} camera(s) for {self._layout_label(self.mode_var.get())}.",
                is_error=True,
            )
            return

        try:
            self.clear_footer_message()

            if self.current_os == "Windows":
                if self.windows_engine_service is None:
                    raise RuntimeError("Windows C++ video engine is not available.")

                # Important: turn off app preview before starting engine.
                # Both preview and engine cannot reliably read the same camera on Windows.
                self.preview_service.stop()

                self.windows_engine_service.start(
                    self.mode_var.get(),
                    self.selected_cameras,
                )

                self._show_broadcasting_message()

            else:
                if self.frame_forwarder is not None:
                    self.frame_forwarder.start()

                self.preview_service.start(
                    self.selected_cameras,
                    self.mode_var.get(),
                    render_local=self.preview_var.get(),
                )

            if self.obs_controller is not None:
                self.obs_controller.start()
                if self.auto_hide_obs_var.get():
                    self.after(1000, self.obs_controller.hide_obs)

            self.pipeline_running = True

            mode = self.mode_var.get().strip()
            cam_a = self.selected_cameras[0] if len(self.selected_cameras) >= 1 else ""
            cam_b = self.selected_cameras[1] if len(self.selected_cameras) >= 2 else ""

            self.status_var.set(
                f"Running: {self._camera_name_from_id(cam_a)}"
                + (f", {self._camera_name_from_id(cam_b)}" if cam_b else "")
                + f", {self._layout_label(mode)}"
            )

        except Exception as e:
            self.pipeline_running = False
            try:
                self.preview_service.stop()
            except Exception:
                pass
            try:
                if self.windows_engine_service is not None:
                    self.windows_engine_service.stop()
                if self.frame_forwarder is not None:
                    self.frame_forwarder.stop()
            except Exception:
                pass
            try:
                if self.obs_controller is not None:
                    self.obs_controller.stop()
            except Exception:
                pass

            self.set_footer_message(str(e), is_error=True)
            self.status_var.set("Stopped")
            self.preview_text_var.set("Preview unavailable")

    def refresh_preview(self):
        if not hasattr(self, "preview_service"):
            return

        if not self.selected_cameras:
            self.preview_text_var.set("No cameras selected")
            return

        if self.current_os == "Windows" and self.pipeline_running:
            self.preview_service.stop()
            self._show_broadcasting_message()
            return

        try:
            if hasattr(self, "preview_text_label"):
                self.preview_text_label.configure(
                    font=("Helvetica", 20, "bold"),
                    fg=self.colors["text"],
                )
            self.preview_service.start(
                self.selected_cameras,
                self.mode_var.get(),
                render_local=self.preview_var.get() if self.pipeline_running else True,
            )

            self.clear_footer_message()
        except Exception as e:
            self.preview_service.stop()
            self.preview_text_var.set("Preview unavailable")
            self.set_footer_message(str(e), is_error=True)

    def stop_pipeline(self):
        if not self.pipeline_running:
            self.set_footer_message("Pipeline is not running.", is_error=True)
            return

        try:
            if self.obs_controller is not None:
                self.obs_controller.stop()
        except Exception as e:
            print(f"OBS stop warning: {e}")

        self.preview_service.stop()

        if self.windows_engine_service is not None:
            self.windows_engine_service.stop()

        if self.frame_forwarder is not None:
            self.frame_forwarder.stop()

        self.pipeline_running = False
        self.status_var.set("Stopped")
        self.preview_text_var.set(f"{self._layout_label(self.mode_var.get())} preview will appear here")
        self.clear_footer_message()

        # Bring local preview back after stopping on Windows.
        if self.current_os == "Windows" and self.selected_cameras:
            self.after(300, self.refresh_preview)

    def detect_cameras(self):
        try:
            cameras = detect_cameras_for_current_os()
            self.detected_cameras = cameras
            self._populate_camera_selectors()

            if not cameras:
                self.setup_var.set("No cameras detected")
                self.preview_text_var.set("No cameras found")
                return

            if len(cameras) == 1:
                self.setup_var.set(f"1 camera detected: {cameras[0]['name']}")
                self.preview_text_var.set("Single camera mode auto-selected")
            else:
                self.setup_var.set(f"{len(cameras)} cameras detected")
                self.preview_text_var.set(f"Select up to {self.max_cameras} cameras")

        except Exception as e:
            messagebox.showerror("Detect Cameras", f"Camera detection failed:\n{e}")
            self.setup_var.set("Camera detection failed")
            self.preview_text_var.set("Camera detection failed")