# preview_service.py
import cv2
from PIL import Image, ImageTk


class PreviewService:
    def __init__(self, app):
        self.app = app
        self.capture_a = None
        self.capture_b = None
        self.preview_job = None
        self.preview_image_ref = None
        self.canvas_image_id = None
        self.frame_forwarder = None
        self.render_local = True

    def set_frame_forwarder(self, forwarder):
        self.frame_forwarder = forwarder

    def start(self, selected_camera_ids, mode, render_local=True):
        self.stop()

        if not selected_camera_ids:
            raise RuntimeError("No camera selected.")

        self.render_local = render_local

        cam_a = self._camera_by_selected_id(selected_camera_ids[0])
        if cam_a is None:
            raise RuntimeError("Primary camera not found.")

        if self.app.current_os == "Darwin":
            self.capture_a = cv2.VideoCapture(int(cam_a["preview_index"]), cv2.CAP_AVFOUNDATION)
        elif self.app.current_os == "Windows":
            self.capture_a = cv2.VideoCapture(int(cam_a["preview_index"]), cv2.CAP_DSHOW)
        else:
            self.capture_a = cv2.VideoCapture(int(cam_a["preview_index"]))
        if not self.capture_a.isOpened():
            self.capture_a = None
            raise RuntimeError(f'Failed to open "{cam_a["name"]}".')

        if len(selected_camera_ids) > 1 and mode != "single":
            cam_b = self._camera_by_selected_id(selected_camera_ids[1])
            if cam_b is None:
                self.stop()
                raise RuntimeError("Secondary camera not found.")

            if self.app.current_os == "Darwin":
                self.capture_b = cv2.VideoCapture(int(cam_b["preview_index"]), cv2.CAP_AVFOUNDATION)
            elif self.app.current_os == "Windows":
                self.capture_b = cv2.VideoCapture(int(cam_b["preview_index"]), cv2.CAP_DSHOW)
            else:
                self.capture_b = cv2.VideoCapture(int(cam_b["preview_index"]))
            if not self.capture_b.isOpened():
                self.stop()
                raise RuntimeError(f'Failed to open "{cam_b["name"]}".')

        if self.render_local:
            self.app.preview_text_label.place_forget()
        else:
            self.app.preview_canvas.delete("all")
            self.app.preview_text_var.set("Local preview disabled")
            self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")

        self._update_frame()

    def _camera_by_selected_id(self, selected_id):
        for cam in self.app.detected_cameras:
            if str(cam["id"]) == str(selected_id):
                return cam
        return None

    def _update_frame(self):
        if self.capture_a is None:
            return

        mode = self.app.mode_var.get()

        ok_a, frame_a = self.capture_a.read()
        if not ok_a or frame_a is None:
            self.preview_job = self.app.after(60, self._update_frame)
            return

        frame_b = None
        if self.capture_b is not None and mode != "single":
            ok_b, temp_b = self.capture_b.read()
            if ok_b and temp_b is not None:
                frame_b = temp_b

        composed = self._compose_frame(frame_a, frame_b, mode)

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
                x, y,
                anchor="nw",
                image=photo
            )

        self.preview_job = self.app.after(30, self._update_frame)

    def _compose_frame(self, frame_a, frame_b, mode):
        if mode == "single" or frame_b is None:
            return frame_a

        if mode == "sbs":
            target_h = min(frame_a.shape[0], frame_b.shape[0])
            a = self._resize_to_height_keep_aspect(frame_a, target_h)
            b = self._resize_to_height_keep_aspect(frame_b, target_h)
            return cv2.hconcat([a, b])

        if mode == "stacked":
            target_w = min(frame_a.shape[1], frame_b.shape[1])
            a = self._resize_to_width_keep_aspect(frame_a, target_w)
            b = self._resize_to_width_keep_aspect(frame_b, target_w)
            return cv2.vconcat([a, b])

        if mode == "pip":
            return self._compose_pip(frame_a, frame_b)

        return frame_a

    def _compose_pip(self, base_frame, inset_frame):
        base = base_frame.copy()
        base_h, base_w = base.shape[:2]

        max_inset_w = int(base_w * 0.28)
        max_inset_h = int(base_h * 0.28)

        inset = self._fit_inside_box(inset_frame, max_inset_w, max_inset_h)
        inset_h, inset_w = inset.shape[:2]

        margin = 20
        x1 = base_w - inset_w - margin
        y1 = margin
        x2 = x1 + inset_w
        y2 = y1 + inset_h

        cv2.rectangle(base, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (255, 255, 255), 2)
        base[y1:y2, x1:x2] = inset
        return base

    def _fit_inside_box(self, frame, box_w, box_h):
        h, w = frame.shape[:2]
        scale = min(box_w / w, box_h / h)

        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        return cv2.resize(frame, (new_w, new_h))

    def _resize_to_height_keep_aspect(self, frame, target_h):
        h, w = frame.shape[:2]
        scale = target_h / h
        new_w = max(1, int(w * scale))
        return cv2.resize(frame, (new_w, target_h))

    def _resize_to_width_keep_aspect(self, frame, target_w):
        h, w = frame.shape[:2]
        scale = target_w / w
        new_h = max(1, int(h * scale))
        return cv2.resize(frame, (target_w, new_h))

    def stop(self):
        if self.preview_job is not None:
            try:
                self.app.after_cancel(self.preview_job)
            except Exception:
                pass
            self.preview_job = None

        if self.capture_a is not None:
            self.capture_a.release()
            self.capture_a = None

        if self.capture_b is not None:
            self.capture_b.release()
            self.capture_b = None

        self.preview_image_ref = None

        if hasattr(self.app, "preview_canvas"):
            self.app.preview_canvas.delete("all")

        if hasattr(self.app, "preview_text_label"):
            self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")