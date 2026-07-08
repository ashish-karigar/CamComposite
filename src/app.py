# app.py
import platform
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from pathlib import Path
from ui.app_icon import set_window_icon

from PIL import Image, ImageTk

from constants import COLORS, WINDOW
from styles import configure_styles
from ui import (
    build_header,
    build_controls_panel,
    build_preview_panel,
    build_footer,
)

from services import detect_cameras_for_current_os, PreviewService
from ui.modern_widgets import RoundedButton, RoundedToast


class CamCompositeApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(WINDOW["title"])
        set_window_icon(self)
        self.geometry(WINDOW["size"])
        self.resizable(False, False)

        self.colors = COLORS
        self.current_os = platform.system()
        self.pipeline_running = False

        self.selected_cameras = []
        self.max_cameras = 4
        self.camera_selector_widgets = []
        self.detected_cameras = []
        self.layout_disabled = False
        self.layout_tiles = {}

        self.obs_controller = None
        self.obs_lock = threading.Lock()
        self.toast_frame = None
        self._toast_after_id = None

        if self.current_os == "Darwin":
            from src.utils.obs_mac_controller import MacOBSController

            self.obs_controller = MacOBSController(
                scene_name="CamComposite",
                port=4455,
                password="mylens123",
            )

        self.mode_var = tk.StringVar(value="single")
        self.swapped_var = tk.BooleanVar(value=False)

        # Kept internally for pipeline compatibility.
        # These are no longer shown as checkboxes in the UI.
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
        self.windows_shared_preview_service = None
        self.frame_forwarder = None
        self.windows_engine_service = None

        if self.current_os == "Darwin":
            from src.utils.ndi_frame_sender import NDIFrameSender

            self.frame_forwarder = NDIFrameSender()
            self.preview_service.set_frame_forwarder(self.frame_forwarder)

        elif self.current_os == "Windows":
            from src.services.windows_engine_service import WindowsEngineService
            from src.services.windows_shared_preview_service import WindowsSharedPreviewService

            self.windows_engine_service = WindowsEngineService()
            self.windows_shared_preview_service = WindowsSharedPreviewService(self)

            # Windows:
            # video_engine.exe -> shared memory -> app preview before Start
            # video_engine.exe -> shared memory -> Cam-Composite DirectShow after Start
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

    def _check_windows_preview_engine_started(self):
        if self.current_os != "Windows":
            return

        if self.pipeline_running:
            return

        if self.windows_engine_service is None:
            return

        exit_code = self.windows_engine_service.get_exit_code()

        if exit_code is not None:
            self.preview_text_var.set("Preview unavailable")
            self.set_footer_message(
                "Windows video engine exited early. Check windows_engine/build/runtime/video_engine.log",
                severity="error",
            )

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

    def set_footer_message(self, message, is_error=False, severity=None):
        """
        severity:
          - "info"
          - "warning"
          - "error"

        Backward compatible:
          is_error=True defaults to warning unless severity="error" is passed.
        """
        if severity is None:
            severity = "warning" if is_error else "info"

        self.footer_message_var.set(message)

        if hasattr(self, "footer_label"):
            if severity == "error":
                color = self.colors["error"]
            elif severity == "warning":
                color = self.colors["warning"]
            else:
                color = self.colors["muted"]

            self.footer_label.configure(foreground=color)

        if message and message != "Developed by - @ashish.karigar":
            self.show_toast(message, severity=severity)

    def clear_footer_message(self):
        self.set_footer_message("Developed by - @ashish.karigar", severity="info")

    def show_toast(self, message, is_error=False, severity=None, duration_ms=3000):
        if not message:
            return

        if severity is None:
            severity = "error" if is_error else "info"

        if hasattr(self, "_toast_after_id") and self._toast_after_id is not None:
            try:
                self.after_cancel(self._toast_after_id)
            except Exception:
                pass
            self._toast_after_id = None

        if hasattr(self, "toast_frame") and self.toast_frame is not None:
            try:
                self.toast_frame.destroy()
            except Exception:
                pass
            self.toast_frame = None

        if severity == "error":
            title = "Error"
            bg = self.colors["toast_error_bg"]
            border = self.colors["error"]
            accent = self.colors["error"]
        elif severity == "warning":
            title = "Warning"
            bg = self.colors["toast_warning_bg"]
            border = self.colors["warning"]
            accent = self.colors["warning"]
        else:
            title = "Notice"
            bg = self.colors["toast_bg"]
            border = self.colors["toast_border"]
            accent = self.colors["accent_hover"]

        toast_w = 340
        toast_h = 88

        self.toast_frame = RoundedToast(
            self,
            title=title,
            message=message,
            colors=self.colors,
            bg=bg,
            border=border,
            accent=accent,
            width=toast_w,
            height=toast_h,
            radius=18,
        )

        self.toast_frame.place(
            relx=1.0,
            rely=1.0,
            x=-24,
            y=24,
            width=toast_w,
            height=toast_h,
            anchor="se",
        )

        steps = 8
        start_y = 24
        end_y = -24

        def animate(step=0):
            if not hasattr(self, "toast_frame") or self.toast_frame is None:
                return

            progress = min(1.0, step / steps)
            y = int(start_y + (end_y - start_y) * progress)

            self.toast_frame.place_configure(y=y)

            if step < steps:
                self.after(16, lambda: animate(step + 1))

        animate()

        self._toast_after_id = self.after(duration_ms, self.hide_toast)

    def hide_toast(self):
        self._toast_after_id = None

        if hasattr(self, "toast_frame") and self.toast_frame is not None:
            try:
                self.toast_frame.destroy()
            except Exception:
                pass

        self.toast_frame = None

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

    # -------------------------------------------------------------------------
    # Camera selector buttons
    # -------------------------------------------------------------------------

    def _clear_camera_selector_widgets(self):
        for widget in self.camera_selector_widgets:
            widget.destroy()
        self.camera_selector_widgets.clear()

    def _populate_camera_selectors(self):
        self._clear_camera_selector_widgets()

        if not self.detected_cameras:
            self.selected_cameras = []

            lbl = tk.Label(
                self.cameras_frame,
                text="No cameras detected",
                bg=self.colors["panel"],
                fg=self.colors["muted"],
                font=("Helvetica", 10),
                anchor="w",
            )
            lbl.pack(anchor="w", pady=(8, 0))
            self.camera_selector_widgets.append(lbl)
            self._set_layout_state(disable=False)
            return

        detected_ids = [str(cam["id"]) for cam in self.detected_cameras]

        # Preserve existing selections after Detect Cameras.
        # Only drop cameras that disappeared.
        self.selected_cameras = [
            cam_id for cam_id in self.selected_cameras
            if cam_id in detected_ids
        ]

        # First launch / no current selection:
        # auto-select first camera, but do not reset layout on later detections.
        if not self.selected_cameras:
            self.selected_cameras = [detected_ids[0]]

        for cam in self.detected_cameras:
            cam_id = str(cam["id"])

            btn = RoundedButton(
                self.cameras_frame,
                text="",
                command=lambda cid=cam_id: self._toggle_camera_selection(cid),
                colors=self.colors,
                width=280,
                height=44,
                radius=14,
                anchor="w",
                padx=14,
            )
            btn.pack(fill="x", anchor="w", pady=(6, 0))
            btn.camera_id = cam_id
            self.camera_selector_widgets.append(btn)

        self._sync_layout_after_camera_selection()
        self._refresh_camera_selector_widgets()

        if self.pipeline_running and self.current_os == "Windows":
            self._restart_windows_engine_if_running()
        else:
            if self.pipeline_running and self.current_os == "Darwin":
                self._show_broadcasting_message()
            else:
                names = [self._camera_name_from_id(cid) for cid in self.selected_cameras]
                if names:
                    self.preview_text_var.set("Selected: " + ", ".join(names))
                else:
                    self.preview_text_var.set("No cameras selected")

                self.after(100, self.refresh_preview)

    def _refresh_camera_selector_widgets(self):
        for widget in self.camera_selector_widgets:
            cam_id = getattr(widget, "camera_id", None)
            if cam_id is None:
                continue

            cam_name = self._camera_name_from_id(cam_id)

            if cam_id in self.selected_cameras:
                order = self.selected_cameras.index(cam_id) + 1
                widget.set_text(f"{order}.  {cam_name}")
                widget.set_selected(True)
            else:
                widget.set_text(f"     {cam_name}")
                widget.set_selected(False)

    def _toggle_camera_selection(self, cam_id):
        if cam_id in self.selected_cameras:
            self.selected_cameras.remove(cam_id)
        else:
            if len(self.selected_cameras) >= self.max_cameras:
                self.set_footer_message(
                    f"You can select a maximum of {self.max_cameras} cameras.",
                    is_error=True,
                )
                return

            self.selected_cameras.append(cam_id)
            self.clear_footer_message()

        self._sync_layout_after_camera_selection()
        self._refresh_camera_selector_widgets()

        names = [self._camera_name_from_id(cid) for cid in self.selected_cameras]

        if self.pipeline_running and self.current_os == "Windows":
            self._restart_windows_engine_if_running()
        else:
            if names:
                self.preview_text_var.set("Selected: " + ", ".join(names))
            else:
                self.preview_text_var.set("No cameras selected")

            self.refresh_preview()

    def _sync_layout_after_camera_selection(self):
        selected_count = len(self.selected_cameras)

        if len(self.detected_cameras) == 1:
            self._set_layout_state(disable=True)
            self.mode_var.set("single")
            return

        self._set_layout_state(disable=False)

        allowed_layouts = self._allowed_layouts_for_selection_count(selected_count)
        current_layout = self.mode_var.get()

        # Only change layout if the current layout is no longer valid.
        # Adding cameras should not force a new layout.
        if current_layout not in allowed_layouts:
            self.mode_var.set(self._preferred_layout_for_selection_count(selected_count))

        self._refresh_layout_tiles()

    def _preferred_layout_for_selection_count(self, count):
        if count <= 1:
            return "single"
        if count == 2:
            return "sbs"
        if count == 3:
            return "triple"
        return "quad"

    def _camera_name_from_id(self, cam_id):
        for cam in self.detected_cameras:
            if str(cam["id"]) == str(cam_id):
                return cam["name"]
        return f"Camera {cam_id}"

    # -------------------------------------------------------------------------
    # Window / layout helpers
    # -------------------------------------------------------------------------

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
            if self.windows_shared_preview_service is not None:
                self.windows_shared_preview_service.stop(clear_canvas=True)
        except Exception as e:
            print(f"Windows shared preview close warning: {e}")

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

        if self.current_os == "Windows":
            if self.pipeline_running:
                self._restart_windows_engine_if_running()
            else:
                self.refresh_preview()
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
        self._refresh_camera_selector_widgets()
        self.clear_footer_message()

        if self.current_os == "Windows":
            if self.pipeline_running:
                self._restart_windows_engine_if_running()
            else:
                self.refresh_preview()
        else:
            self.preview_text_var.set("Camera feeds swapped")
            self.refresh_preview()

        if self.pipeline_running:
            mode = self.mode_var.get()
            names = [self._camera_name_from_id(cid) for cid in self.selected_cameras[:2]]
            self.status_var.set(
                f"Running: {', '.join(names)}, {self._layout_label(mode)}"
            )

    # -------------------------------------------------------------------------
    # Preview messages / broadcast state
    # -------------------------------------------------------------------------
    def _load_broadcast_icon(self, size=52):
        icon_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "icons"
            / "video_camera_green.png"
        )

        image = Image.open(icon_path).convert("RGBA")
        image = image.resize((size, size), Image.Resampling.LANCZOS)

        self.broadcast_icon_ref = ImageTk.PhotoImage(image)
        return self.broadcast_icon_ref

    def _show_broadcasting_message(self):
        self.preview_text_var.set("Broadcast started")

        if hasattr(self, "preview_canvas"):
            self.preview_canvas.delete("all")

            canvas_w = max(self.preview_canvas.winfo_width(), 640)
            canvas_h = max(self.preview_canvas.winfo_height(), 360)

            center_x = canvas_w // 2
            center_y = canvas_h // 2

            self.preview_canvas.create_text(
                center_x,
                center_y - 28,
                text="Broadcast started",
                fill=self.colors["text"],
                font=("Helvetica", 20, "bold"),
                anchor="center",
                tags="broadcast_message",
            )

            try:
                icon = self._load_broadcast_icon(size=54)
                self.preview_canvas.create_image(
                    center_x,
                    center_y + 34,
                    image=icon,
                    anchor="center",
                    tags="broadcast_message",
                )
            except Exception as e:
                print(f"Broadcast icon warning: {e}")

        if hasattr(self, "preview_text_label"):
            self.preview_text_label.place_forget()

    def _reset_preview_message_style(self):
        if hasattr(self, "preview_text_label"):
            self.preview_text_label.configure(
                font=("Helvetica", 20, "bold"),
                fg=self.colors["text"],
            )

    def draw_preview_camera_badges(self, image_x, image_y, image_w, image_h):
        if not hasattr(self, "preview_canvas"):
            return

        self.preview_canvas.delete("camera_badge")

        if not self.selected_cameras:
            return

        mode = self.mode_var.get()
        count = len(self.selected_cameras)

        positions = []

        pad = 18
        badge_size = 30

        if mode == "single" or count == 1:
            positions = [(image_x + pad, image_y + pad)]

        elif mode == "sbs":
            positions = [
                (image_x + pad, image_y + pad),
                (image_x + image_w // 2 + pad, image_y + pad),
            ]

        elif mode == "stacked":
            positions = [
                (image_x + pad, image_y + pad),
                (image_x + pad, image_y + image_h // 2 + pad),
            ]

        elif mode == "pip":
            positions = [
                (image_x + pad, image_y + pad),
                (image_x + image_w - 110, image_y + image_h - 88),
            ]

        elif mode == "triple":
            positions = [
                (image_x + pad, image_y + pad),
                (image_x + pad, image_y + image_h // 2 + pad),
                (image_x + image_w // 2 + pad, image_y + image_h // 2 + pad),
            ]

        elif mode == "quad":
            positions = [
                (image_x + pad, image_y + pad),
                (image_x + image_w // 2 + pad, image_y + pad),
                (image_x + pad, image_y + image_h // 2 + pad),
                (image_x + image_w // 2 + pad, image_y + image_h // 2 + pad),
            ]

        else:
            positions = [(image_x + pad, image_y + pad)]

        for index, (badge_x, badge_y) in enumerate(positions[:count], start=1):
            self.preview_canvas.create_oval(
                badge_x,
                badge_y,
                badge_x + badge_size,
                badge_y + badge_size,
                fill=self.colors["accent"],
                outline=self.colors["accent_hover"],
                width=2,
                tags="camera_badge",
            )
            self.preview_canvas.create_text(
                badge_x + badge_size // 2,
                badge_y + badge_size // 2,
                text=str(index),
                fill="white",
                font=("Helvetica", 13, "bold"),
                tags="camera_badge",
            )

    # -------------------------------------------------------------------------
    # Windows broadcast update
    # -------------------------------------------------------------------------

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
            # While broadcasting, update mode/cameras and keep broadcasting ON.
            self.windows_engine_service.start(
                self.mode_var.get(),
                self.selected_cameras,
                force_restart=False,
                broadcasting=True,
            )

            if self.windows_shared_preview_service is not None:
                self.windows_shared_preview_service.stop(clear_canvas=True)

            self.preview_service.stop()
            self._show_broadcasting_message()

            self.status_var.set(
                f"Running: {', '.join([self._camera_name_from_id(cid) for cid in self.selected_cameras])}, "
                f"{self._layout_label(self.mode_var.get())}"
            )
        except Exception as e:
            self.set_footer_message(f"Could not update Windows engine: {e}", severity="error")

    # -------------------------------------------------------------------------
    # macOS OBS background helpers
    # -------------------------------------------------------------------------

    def _start_obs_in_background(self):
        if self.obs_controller is None:
            return

        def worker():
            try:
                with self.obs_lock:
                    self.obs_controller.start()

                if self.auto_hide_obs_var.get():
                    self.after(0, lambda: self.after(1000, self.obs_controller.hide_obs))

                self.after(0, lambda: self.status_var.set("Broadcasting"))
                self.after(0, self.clear_footer_message)

            except Exception as e:
                message = str(e)
                self.after(
                    0,
                    lambda msg=message: self.set_footer_message(
                        f"OBS start warning: {msg}",
                        severity="warning",
                    )
                )

        threading.Thread(
            target=worker,
            name="MacOBSStart",
            daemon=True,
        ).start()

    def _stop_obs_in_background(self):
        if self.obs_controller is None:
            return

        def worker():
            try:
                with self.obs_lock:
                    self.obs_controller.stop()
            except Exception as e:
                print(f"OBS stop warning: {e}")

        threading.Thread(
            target=worker,
            name="MacOBSStop",
            daemon=True,
        ).start()

    # -------------------------------------------------------------------------
    # Pipeline controls
    # -------------------------------------------------------------------------

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

                # Same engine keeps running.
                # Only flip broadcasting=1 so DirectShow starts outputting live frames.
                self.windows_engine_service.start(
                    self.mode_var.get(),
                    self.selected_cameras,
                    force_restart=False,
                    broadcasting=True,
                )

                if self.windows_shared_preview_service is not None:
                    self.windows_shared_preview_service.stop(clear_canvas=True)

                self.preview_service.stop()
                self._show_broadcasting_message()

            else:
                if self.frame_forwarder is not None:
                    self.frame_forwarder.start()

                if self.current_os == "Darwin":
                    # macOS optimization:
                    # Keep camera loop warm and forwarding to NDI/OBS,
                    # but hide local preview while broadcasting.
                    self.preview_service.start(
                        self.selected_cameras,
                        self.mode_var.get(),
                        render_local=False,
                    )
                    self._show_broadcasting_message()
                else:
                    self.preview_service.start(
                        self.selected_cameras,
                        self.mode_var.get(),
                        render_local=self.preview_var.get(),
                    )

            if self.obs_controller is not None:
                if self.current_os == "Darwin":
                    self._start_obs_in_background()
                else:
                    self.obs_controller.start()
                    if self.auto_hide_obs_var.get():
                        self.after(1000, self.obs_controller.hide_obs)

            self.pipeline_running = True

            mode = self.mode_var.get().strip()
            shown_names = [
                self._camera_name_from_id(cid)
                for cid in self.selected_cameras[:2]
            ]

            self.status_var.set(
                f"Running: {', '.join(shown_names)}, {self._layout_label(mode)}"
            )

        except Exception as e:
            self.pipeline_running = False
            try:
                self.preview_service.stop()
            except Exception:
                pass
            try:
                if self.windows_shared_preview_service is not None:
                    self.windows_shared_preview_service.stop(clear_canvas=True)
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

            self.set_footer_message(str(e), severity="error")
            self.status_var.set("Stopped")
            self.preview_text_var.set("Preview unavailable")

    def refresh_preview(self):
        if not self.selected_cameras:
            self.preview_text_var.set("No cameras selected")
            return

        if self.current_os == "Windows":
            if self.pipeline_running:
                if self.windows_shared_preview_service is not None:
                    self.windows_shared_preview_service.stop(clear_canvas=True)
                self._show_broadcasting_message()
                return

            try:
                if self.windows_engine_service is None:
                    raise RuntimeError("Windows C++ video engine is not available.")

                if self.windows_shared_preview_service is None:
                    raise RuntimeError("Windows shared preview service is not available.")

                self._reset_preview_message_style()

                # Do not let old Python preview own cameras on Windows.
                self.preview_service.stop()

                # Critical:
                # Do NOT pass self.after(...) as the third argument.
                # The third argument is force_restart.
                # This must stay False so the existing video_engine.exe keeps running.
                self.windows_engine_service.start(
                    self.mode_var.get(),
                    self.selected_cameras,
                    force_restart=False,
                    broadcasting=False,
                )

                self.after(700, self._check_windows_preview_engine_started)

                self.windows_shared_preview_service.start()

                self.clear_footer_message()

            except Exception as e:
                if self.windows_shared_preview_service is not None:
                    self.windows_shared_preview_service.stop(clear_canvas=True)

                self.preview_text_var.set("Preview unavailable")
                self.set_footer_message(str(e), severity="error")

            return

        if not hasattr(self, "preview_service"):
            return

        try:
            self._reset_preview_message_style()

            render_local = True

            if self.current_os == "Darwin" and self.pipeline_running:
                # macOS optimization:
                # While broadcasting through OBS/NDI, keep the camera loop warm
                # but do not bring local preview back on layout/camera changes.
                render_local = False
            else:
                render_local = self.preview_var.get() if self.pipeline_running else True

            self.preview_service.start(
                self.selected_cameras,
                self.mode_var.get(),
                render_local=render_local,
            )

            if self.current_os == "Darwin" and self.pipeline_running:
                self._show_broadcasting_message()

            self.clear_footer_message()
        except Exception as e:
            self.preview_service.stop()
            self.preview_text_var.set("Preview unavailable")
            self.set_footer_message(str(e), is_error=True)

    def stop_pipeline(self):
        if not self.pipeline_running:
            self.set_footer_message("Pipeline is not running.", is_error=True)
            return

        if self.obs_controller is not None:
            if self.current_os == "Darwin":
                self._stop_obs_in_background()
            else:
                try:
                    self.obs_controller.stop()
                except Exception as e:
                    print(f"OBS stop warning: {e}")

        if self.current_os == "Windows":
            # Do NOT stop video_engine.exe.
            # Keep cameras warm for preview, but flip broadcasting=0.
            if self.windows_engine_service is not None:
                self.windows_engine_service.start(
                    self.mode_var.get(),
                    self.selected_cameras,
                    force_restart=False,
                    broadcasting=False,
                )

            self.preview_service.stop()

            if self.windows_shared_preview_service is not None:
                self.windows_shared_preview_service.start()

        else:
            if self.frame_forwarder is not None:
                self.frame_forwarder.stop()

            # macOS optimization:
            # Do NOT release cameras on Stop.
            # Keep preview warm like Windows; only stop NDI/OBS forwarding.
            if self.current_os == "Darwin" and self.selected_cameras:
                self.preview_service.start(
                    self.selected_cameras,
                    self.mode_var.get(),
                    render_local=True,
                )
            else:
                self.preview_service.stop()

        self.pipeline_running = False
        self.status_var.set("Stopped")
        self.preview_text_var.set(f"{self._layout_label(self.mode_var.get())} preview will appear here")
        self.clear_footer_message()

    def _show_stopped_message(self):
        if hasattr(self, "preview_canvas"):
            self.preview_canvas.delete("all")

        if hasattr(self, "preview_text_label"):
            self.preview_text_label.configure(
                font=("Helvetica", 12, "normal"),
                fg=self.colors["muted"],
            )
            self.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")

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
            else:
                self.setup_var.set(f"{len(cameras)} cameras detected")

        except Exception as e:
            messagebox.showerror("Detect Cameras", f"Camera detection failed:\n{e}")
            self.setup_var.set("Camera detection failed")
            self.set_footer_message(f"Camera detection failed: {e}", severity="error")