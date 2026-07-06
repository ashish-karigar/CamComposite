# preview_service.py
import cv2
import numpy as np
from PIL import Image, ImageTk
from .threaded_capture import ThreadedCapture

MacAVFoundationCapture = None

try:
    from .mac_avfoundation_capture import MacAVFoundationCapture
except ImportError:
    pass

try:
    from constants import get_video_profile
except ImportError:
    from src.constants import get_video_profile

PREVIEW_DELAY_MS = 30


class PreviewService:
    def __init__(self, app):
        self.app = app
        self.captures = {}
        self.active_camera_ids = []
        self.last_good_frames = {}
        self.preview_job = None
        self.preview_image_ref = None
        self.canvas_image_id = None
        self.frame_forwarder = None
        self.render_local = True
        self.video_profile = get_video_profile()
        self.output_w = self.video_profile["width"]
        self.output_h = self.video_profile["height"]
        self.output_fps = self.video_profile["fps"]
        self.failed_frame_counts = {}
        self.usb_warning_shown = False
        self.failed_camera_ids = set()

    def set_frame_forwarder(self, forwarder):
        self.frame_forwarder = forwarder

    def _show_status_warning(self, message):
        if hasattr(self.app, "set_footer_message"):
            self.app.after(0, lambda: self.app.set_footer_message(message, is_error=True))
        else:
            print(message)

    def start(self, selected_camera_ids, mode, render_local=True):
        self._cancel_preview_loop()

        if not selected_camera_ids:
            raise RuntimeError("No camera selected.")

        self.render_local = render_local
        self.usb_warning_shown = False

        required_counts = {
            "single": 1,
            "pip": 2,
            "sbs": 2,
            "stacked": 2,
            "triple": 3,
            "quad": 4,
        }

        required = required_counts.get(mode, 1)
        camera_ids_to_open = selected_camera_ids[:required]

        self.active_camera_ids = [str(cam_id) for cam_id in camera_ids_to_open]
        self._sync_open_captures(self.active_camera_ids)

        if self.render_local:
            self.app.preview_text_label.place_forget()
        else:
            self.app.preview_canvas.delete("all")
            self.app.preview_text_var.set("Local preview disabled")
            self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")

        self._update_frame()

    def _is_capture_card(self, camera):
        text = " ".join([
            str(camera.get("name", "")),
            str(camera.get("id", "")),
            str(camera.get("device_path", "")),
            str(camera.get("unique_id", "")),
        ]).lower()

        capture_keywords = [
            "capture",
            "hdmi",
            "usb video",
            "usb3",
            "uvc",
            "534d",
            "2109",
        ]

        return any(keyword in text for keyword in capture_keywords)

    def _open_capture(self, camera, mode):
        capture_w = self.output_w
        capture_h = self.output_h
        capture_fps = self.output_fps

        if self.app.current_os == "Darwin":
            if MacAVFoundationCapture is None:
                raise RuntimeError("AVFoundation capture is only available on macOS.")

            cap = MacAVFoundationCapture(
                unique_id=camera["unique_id"],
                width=capture_w,
                height=capture_h,
                fps=capture_fps,
            )
            cap.open()
            return cap

        if self.app.current_os == "Windows":
            cap = cv2.VideoCapture(int(camera["preview_index"]), cv2.CAP_DSHOW)

            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, capture_w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, capture_h)
            cap.set(cv2.CAP_PROP_FPS, capture_fps)

            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = cap.get(cv2.CAP_PROP_FPS)

            print(
                f'requested={capture_w}x{capture_h}@{capture_fps}, '
            )

            return cap

        return cv2.VideoCapture(int(camera["preview_index"]))

    def _camera_by_selected_id(self, selected_id):
        for cam in self.app.detected_cameras:
            if str(cam["id"]) == str(selected_id):
                return cam
        return None

    def _cancel_preview_loop(self):
        if self.preview_job is not None:
            try:
                self.app.after_cancel(self.preview_job)
            except Exception:
                pass
            self.preview_job = None

    def _sync_open_captures(self, needed_ids):
        needed = set(str(x) for x in needed_ids)

        for cam_id in list(self.captures.keys()):
            if cam_id not in needed:
                try:
                    self.captures[cam_id].release()
                except Exception:
                    pass
                del self.captures[cam_id]
                self.last_good_frames.pop(cam_id, None)

        for cam_id in needed_ids:
            cam_id = str(cam_id)
            if cam_id in self.captures:
                continue

            cam = self._camera_by_selected_id(cam_id)
            if cam is None:
                raise RuntimeError(f"Camera {cam_id} not found.")

            try:
                cap = self._open_capture(cam, self.app.mode_var.get())

                if not cap.isOpened():
                    raise RuntimeError(f'Failed to open "{cam["name"]}".')

                self.captures[cam_id] = ThreadedCapture(
                    cap,
                    name=cam.get("name", f"Camera {cam_id}")
                ).start()

                self.failed_camera_ids.discard(cam_id)

            except Exception as e:
                print(f"Camera open warning for {cam.get('name', cam_id)}: {e}")

                self.failed_camera_ids.add(cam_id)

                self._show_status_warning(
                    "One camera could not start. USB bandwidth may be overloaded. "
                    "Try connecting the capture card/cameras to different USB ports."
                )

    def _update_frame(self):
        if not self.active_camera_ids:
            return

        mode = self.app.mode_var.get()
        frames = []

        for cam_id in self.active_camera_ids:
            cam_id = str(cam_id)

            if cam_id in self.failed_camera_ids:
                if not self.usb_warning_shown:
                    self.usb_warning_shown = True
                    self._show_status_warning(
                        "One camera could not start. USB bandwidth may be overloaded. "
                        "Try connecting the capture card/cameras to different USB ports."
                    )

                frames.append(self._blank_cell(self.output_w, self.output_h))
                continue

            cap = self.captures.get(cam_id)

            if cap is None:
                if not self.usb_warning_shown:
                    self.usb_warning_shown = True
                    self._show_status_warning(
                        "One camera could not start. USB bandwidth may be overloaded. "
                        "Try connecting the capture card/cameras to different USB ports."
                    )

                frames.append(self._blank_cell(self.output_w, self.output_h))
                continue

            ok, frame = cap.read()

            if ok and frame is not None:
                self.failed_frame_counts[cam_id] = 0
                self.last_good_frames[cam_id] = frame
                frames.append(frame)
                continue

            self.failed_frame_counts[cam_id] = self.failed_frame_counts.get(cam_id, 0) + 1

            if self.failed_frame_counts[cam_id] >= 30 and not self.usb_warning_shown:
                self.usb_warning_shown = True
                self._show_status_warning(
                    "Camera feed unstable. USB bandwidth may be overloaded. "
                    "Try connecting the capture card/cameras to different USB ports."
                )

            if cam_id in self.last_good_frames:
                frames.append(self.last_good_frames[cam_id])
                continue

            frames.append(self._blank_cell(self.output_w, self.output_h))

        if not frames:
            self.preview_job = self.app.after(60, self._update_frame)
            return

        composed = self._compose_frame(frames, mode)

        if self.frame_forwarder is not None:
            try:
                self.frame_forwarder.send_frame(composed)
            except Exception as e:
                print(f"Frame forward warning: {e}")

        if self.render_local:
            canvas_w = max(self.app.preview_canvas.winfo_width(), 640)
            canvas_h = max(self.app.preview_canvas.winfo_height(), 360)

            display_frame = self._fit_inside_box(composed, canvas_w, canvas_h)
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

            image = Image.fromarray(display_frame)
            photo = ImageTk.PhotoImage(image=image)
            self.preview_image_ref = photo

            self.app.preview_canvas.delete("all")

            img_h, img_w = display_frame.shape[:2]
            x = (canvas_w - img_w) // 2
            y = (canvas_h - img_h) // 2

            self.canvas_image_id = self.app.preview_canvas.create_image(
                x,
                y,
                anchor="nw",
                image=photo,
            )

        self.preview_job = self.app.after(PREVIEW_DELAY_MS, self._update_frame)

    def _compose_frame(self, frames, mode):
        if not frames:
            raise RuntimeError("No frames available for preview.")

        if mode == "single" or len(frames) == 1:
            return self._fit_and_pad(frames[0], self.output_w, self.output_h)

        if mode == "sbs" and len(frames) >= 2:
            left = self._fit_and_pad(frames[0], self.output_w // 2, self.output_h)
            right = self._fit_and_pad(frames[1], self.output_w // 2, self.output_h)
            return cv2.hconcat([left, right])

        if mode == "stacked" and len(frames) >= 2:
            top = self._fit_and_pad(frames[0], self.output_w, self.output_h // 2)
            bottom = self._fit_and_pad(frames[1], self.output_w, self.output_h // 2)
            return cv2.vconcat([top, bottom])

        if mode == "pip" and len(frames) >= 2:
            return self._compose_pip(frames[0], frames[1])

        if mode == "triple" and len(frames) >= 3:
            return self._compose_triple_grid(frames[:3])

        if mode == "quad" and len(frames) >= 4:
            return self._compose_quad_grid(frames[:4])

        return self._fit_and_pad(frames[0], self.output_w, self.output_h)

    def _compose_pip(self, base_frame, inset_frame):
        base = self._fit_and_pad(base_frame, self.output_w, self.output_h)
        base_h, base_w = base.shape[:2]

        inset_w = int(base_w * 0.28)
        inset_h = int(base_h * 0.28)
        inset = self._fit_and_pad(inset_frame, inset_w, inset_h)

        margin = 20
        x1 = base_w - inset_w - margin
        y1 = margin
        x2 = x1 + inset_w
        y2 = y1 + inset_h

        cv2.rectangle(base, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (255, 255, 255), 2)
        base[y1:y2, x1:x2] = inset
        return base

    def _compose_triple_grid(self, frames):
        cell_w = self.output_w // 2
        cell_h = self.output_h // 2

        tl = self._fit_and_pad(frames[0], cell_w, cell_h)
        blank = self._blank_cell(cell_w, cell_h)
        bl = self._fit_and_pad(frames[1], cell_w, cell_h)
        br = self._fit_and_pad(frames[2], cell_w, cell_h)

        top_row = cv2.hconcat([tl, blank])
        bottom_row = cv2.hconcat([bl, br])
        return cv2.vconcat([top_row, bottom_row])

    def _compose_quad_grid(self, frames):
        cell_w = self.output_w // 2
        cell_h = self.output_h // 2

        tl = self._fit_and_pad(frames[0], cell_w, cell_h)
        tr = self._fit_and_pad(frames[1], cell_w, cell_h)
        bl = self._fit_and_pad(frames[2], cell_w, cell_h)
        br = self._fit_and_pad(frames[3], cell_w, cell_h)

        top_row = cv2.hconcat([tl, tr])
        bottom_row = cv2.hconcat([bl, br])
        return cv2.vconcat([top_row, bottom_row])

    def _blank_cell(self, width, height):
        return np.zeros((height, width, 3), dtype=np.uint8)

    def _fit_and_pad(self, frame, box_w, box_h):
        fitted = self._fit_inside_box(frame, box_w, box_h)
        h, w = fitted.shape[:2]

        canvas = self._blank_cell(box_w, box_h)
        x = (box_w - w) // 2
        y = (box_h - h) // 2

        canvas[y:y + h, x:x + w] = fitted
        return canvas

    def _fit_inside_box(self, frame, box_w, box_h):
        h, w = frame.shape[:2]

        if h <= 0 or w <= 0:
            return self._blank_cell(box_w, box_h)

        scale = min(box_w / w, box_h / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def stop(self):
        self.last_good_frames = {}
        self.failed_frame_counts = {}
        self.usb_warning_shown = False
        self.failed_camera_ids = set()
        if self.preview_job is not None:
            try:
                self.app.after_cancel(self.preview_job)
            except Exception:
                pass
            self.preview_job = None

        for cap in self.captures.values():
            try:
                cap.release()
            except Exception:
                pass

        self.captures = {}
        self.active_camera_ids = []
        self.preview_image_ref = None

        if hasattr(self.app, "preview_canvas"):
            self.app.preview_canvas.delete("all")

        if hasattr(self.app, "preview_text_label"):
            self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")