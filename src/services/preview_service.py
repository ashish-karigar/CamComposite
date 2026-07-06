# preview_service.py
import cv2
import numpy as np
from PIL import Image, ImageTk

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
        self.captures = []
        self.preview_job = None
        self.preview_image_ref = None
        self.canvas_image_id = None
        self.frame_forwarder = None
        self.render_local = True
        self.video_profile = get_video_profile()
        self.output_w = self.video_profile["width"]
        self.output_h = self.video_profile["height"]
        self.output_fps = self.video_profile["fps"]

    def set_frame_forwarder(self, forwarder):
        self.frame_forwarder = forwarder

    def start(self, selected_camera_ids, mode, render_local=True):
        self.stop()

        if not selected_camera_ids:
            raise RuntimeError("No camera selected.")

        self.render_local = render_local
        self.captures = []

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

        for idx, selected_id in enumerate(camera_ids_to_open):
            cam = self._camera_by_selected_id(selected_id)
            if cam is None:
                self.stop()
                raise RuntimeError(f'Camera #{idx + 1} not found.')

            cap = self._open_capture(cam)
            if not cap.isOpened():
                self.stop()
                raise RuntimeError(f'Failed to open "{cam["name"]}".')

            self.captures.append(cap)

        if self.render_local:
            self.app.preview_text_label.place_forget()
        else:
            self.app.preview_canvas.delete("all")
            self.app.preview_text_var.set("Local preview disabled")
            self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")

        self._update_frame()

    def _open_capture(self, camera):
        if self.app.current_os == "Darwin":
            if MacAVFoundationCapture is None:
                raise RuntimeError("AVFoundation capture is only available on macOS.")

            cap = MacAVFoundationCapture(
                unique_id=camera["unique_id"],
                width=self.output_w,
                height=self.output_h,
                fps=self.output_fps,
            )
            cap.open()
            return cap

        if self.app.current_os == "Windows":
            cap = cv2.VideoCapture(int(camera["preview_index"]), cv2.CAP_DSHOW)

            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.output_w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.output_h)
            cap.set(cv2.CAP_PROP_FPS, self.output_fps)

            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = cap.get(cv2.CAP_PROP_FPS)

            print(
                f'[CAPTURE] {camera["name"]}: '
                f'requested={self.output_w}x{self.output_h}@{self.output_fps}, '
                f'actual={actual_w}x{actual_h}@{actual_fps}'
            )

            return cap

        return cv2.VideoCapture(int(camera["preview_index"]))

    def _camera_by_selected_id(self, selected_id):
        for cam in self.app.detected_cameras:
            if str(cam["id"]) == str(selected_id):
                return cam
        return None

    def _update_frame(self):
        if not self.captures:
            return

        mode = self.app.mode_var.get()
        frames = []

        for cap in self.captures:
            ok, frame = cap.read()
            if not ok or frame is None:
                self.preview_job = self.app.after(60, self._update_frame)
                return
            frames.append(frame)

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
        if self.preview_job is not None:
            try:
                self.app.after_cancel(self.preview_job)
            except Exception:
                pass
            self.preview_job = None

        for cap in self.captures:
            try:
                cap.release()
            except Exception:
                pass

        self.captures = []
        self.preview_image_ref = None

        if hasattr(self.app, "preview_canvas"):
            self.app.preview_canvas.delete("all")

        if hasattr(self.app, "preview_text_label"):
            self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")