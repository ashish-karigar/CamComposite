# app.py
import platform
import tkinter as tk
from tkinter import ttk, messagebox

from constants import COLORS, WINDOW
from styles import configure_styles
from services import detect_cameras_for_current_os
from ui import (
    build_header,
    build_controls_panel,
    build_preview_panel,
    build_footer,
)

from services import detect_cameras_for_current_os, PreviewService
from src.utils.obs_mac_controller import MacOBSController
from src.utils.ndi_frame_sender import NDIFrameSender


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
        self.camera_check_vars = {}
        self.camera_check_widgets = []
        self.detected_cameras = []
        self.layout_disabled = False
        self.layout_tiles = {}

        self.obs_controller = None

        if platform.system() == "Darwin":
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
        self.ndi_sender = NDIFrameSender()
        self.preview_service.set_frame_forwarder(self.ndi_sender)

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
            self.footer_label.configure(foreground=(self.colors["error"] if is_error else self.colors["muted"]))

    def clear_footer_message(self):
        self.set_footer_message("Developed by - @ashish.karigar", is_error=False)

    def _set_platform_defaults(self):
        if self.current_os == "Darwin":
            self.setup_var.set("macOS backend available")
        elif self.current_os == "Windows":
            self.setup_var.set("Windows backend available")
        else:
            self.setup_var.set(f"Unsupported or untested platform: {self.current_os}")

    def run_setup_check(self):
        if self.current_os == "Darwin":
            self.setup_var.set("macOS setup looks ready to be connected")
        elif self.current_os == "Windows":
            self.setup_var.set("Windows setup check will be connected next")
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
            self.preview_text_var.set("Single camera detected and selected automatically")
            self.after(100, self.refresh_preview)
        else:
            first_id = str(self.detected_cameras[0]["id"])
            self.camera_check_vars[first_id].set(True)
            self.selected_cameras = [first_id]
            self.mode_var.set("single")
            self._set_layout_state(disable=False)
            self.preview_text_var.set(f"Selected: {self._camera_name_from_id(first_id)}")
            self.after(100, self.refresh_preview)

    def _on_camera_checkbox_toggle(self, cam_id):
        selected = [cid for cid, var in self.camera_check_vars.items() if var.get()]

        if len(selected) > 2:
            self.camera_check_vars[cam_id].set(False)
            self.set_footer_message("You can select a maximum of 2 cameras.", is_error=True)
            selected = [cid for cid, var in self.camera_check_vars.items() if var.get()]
        else:
            self.clear_footer_message()

        self.selected_cameras = selected

        if len(self.detected_cameras) == 1:
            self.mode_var.set("single")
            self._set_layout_state(disable=True)
            return

        if len(self.selected_cameras) < 2 and self.mode_var.get() != "single":
            self.mode_var.set("single")
            self.preview_text_var.set("Select 2 cameras to enable dual-camera layouts")

        self._refresh_layout_tiles()

        names = [self._camera_name_from_id(cid) for cid in self.selected_cameras]
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
            self.ndi_sender.stop()
        except Exception as e:
            print(f"NDI close warning: {e}")

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

        if mode_key != "single" and len(self.selected_cameras) < 2:
            self.set_footer_message("Select 2 cameras to use this layout.", is_error=True)
            return

        self.mode_var.set(mode_key)
        self._refresh_layout_tiles()
        self.preview_text_var.set(f"{self._layout_label(mode_key)} selected")
        self.clear_footer_message()
        self.refresh_preview()

    def _set_layout_state(self, disable=False):
        self.layout_disabled = disable

        if disable:
            self.mode_var.set("single")

        self._refresh_layout_tiles()

    def _layout_label(self, mode_key):
        labels = {
            "pip": "Picture in Picture",
            "sbs": "Side by Side",
            "stacked": "Top and Bottom",
            "single": "Single Camera",
        }
        return labels.get(mode_key, mode_key)

    def swap_cameras(self):
        if len(self.selected_cameras) < 2:
            self.set_footer_message("Select 2 cameras to swap.", is_error=True)
            return

        self.selected_cameras[0], self.selected_cameras[1] = self.selected_cameras[1], self.selected_cameras[0]
        self.swapped_var.set(not self.swapped_var.get())
        self.preview_text_var.set("Camera feeds swapped")
        self.clear_footer_message()
        self.refresh_preview()

        if self.pipeline_running:
            mode = self.mode_var.get()
            self.status_var.set(
                f"Running: {self._camera_name_from_id(self.selected_cameras[0])}, "
                f"{self._camera_name_from_id(self.selected_cameras[1])}, "
                f"{self._layout_label(mode)}"
            )

    def start_pipeline(self):
        if self.pipeline_running:
            self.set_footer_message("Pipeline is already running.", is_error=True)
            return

        if not self.selected_cameras:
            self.set_footer_message("Please detect and select at least 1 camera.", is_error=True)
            return

        if self.mode_var.get() != "single" and len(self.selected_cameras) < 2:
            self.set_footer_message("Please select 2 cameras for dual-camera layouts.", is_error=True)
            return

        try:
            self.clear_footer_message()

            self.ndi_sender.start()

            # Always run the capture/compositor loop so OBS gets frames,
            # even when local preview is disabled.
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
            self.preview_text_var.set("Preview connected" if self.preview_var.get() else "Local preview disabled")

        except Exception as e:
            self.pipeline_running = False
            try:
                self.preview_service.stop()
            except Exception:
                pass
            try:
                self.ndi_sender.stop()
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

        try:
            # If pipeline is running, keep the sender/compositor in sync with current UI state.
            if self.pipeline_running:
                self.preview_service.start(
                    self.selected_cameras,
                    self.mode_var.get(),
                    render_local=self.preview_var.get(),
                )
            else:
                # Before pipeline start, this is just local preview behavior.
                self.preview_service.start(
                    self.selected_cameras,
                    self.mode_var.get(),
                    render_local=True,
                )

            self.clear_footer_message()
        except Exception as e:
            self.preview_service.stop()
            self.preview_text_var.set("Preview unavailable")
            self.set_footer_message(str(e), is_error=True)

    # def _mock_pipeline_start(self):
    #     mode = self.mode_var.get().strip()
    #     cam_a = self.selected_cameras[0] if len(self.selected_cameras) >= 1 else ""
    #     cam_b = self.selected_cameras[1] if len(self.selected_cameras) >= 2 else ""
    #     preview = self.preview_var.get()
    #     hide_obs = self.auto_hide_obs_var.get()
    #
    #     self.after(
    #         0,
    #         lambda: self.status_var.set(
    #             f"Running: {self._camera_name_from_id(cam_a)}"
    #             + (f", {self._camera_name_from_id(cam_b)}" if cam_b else "")
    #             + f", {self._layout_label(mode)}"
    #         ),
    #     )
    #     self.after(0, lambda: self.preview_text_var.set("Preview connected"))
    #     _ = preview, hide_obs

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
        self.ndi_sender.stop()

        self.pipeline_running = False
        self.status_var.set("Stopped")
        self.preview_text_var.set(f"{self._layout_label(self.mode_var.get())} preview will appear here")
        self.clear_footer_message()

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
                self.preview_text_var.set("Select up to 2 cameras")

        except Exception as e:
            messagebox.showerror("Detect Cameras", f"Camera detection failed:\n{e}")
            self.setup_var.set("Camera detection failed")