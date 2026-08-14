# preview_service.py
import cv2
import numpy as np
import threading
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
IDLE_CAPTURE_POLL_DELAY_MS = 100


def _ordered_unique_camera_ids(camera_ids):
    unique_ids = []
    seen = set()

    for camera_id in camera_ids:
        normalized_id = str(camera_id)
        if normalized_id in seen:
            continue
        seen.add(normalized_id)
        unique_ids.append(normalized_id)

    return unique_ids


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
        self.frame_sink = None
        self.render_local = True
        self.video_profile = get_video_profile()
        self.output_w = self.video_profile["width"]
        self.output_h = self.video_profile["height"]
        self.output_fps = self.video_profile["fps"]
        self.failed_frame_counts = {}
        self.usb_warning_shown = False
        self.failed_camera_ids = set()

        # Used by macOS async camera open/close path.
        # Windows pipeline no longer relies on this service for camera ownership.
        self.capture_lock = threading.Lock()
        self.opening_camera_ids = set()

    def set_frame_forwarder(self, forwarder):
        self.frame_forwarder = forwarder

    def set_frame_sink(self, sink):
        self.frame_sink = sink

    def _has_active_output(self):
        """Return whether a downstream consumer currently needs full frames."""
        if self.frame_forwarder is not None:
            # Existing forwarders expose `running`; unknown forwarder types are
            # treated as active for compatibility.
            if getattr(self.frame_forwarder, "running", True):
                return True

        if self.frame_sink is not None:
            is_recording = getattr(self.frame_sink, "is_recording", None)
            if is_recording is None or is_recording():
                return True

        return False

    def set_render_local(self, enabled):
        self.render_local = bool(enabled)

        if self.render_local:
            if hasattr(self.app, "preview_text_label"):
                self.app.preview_text_label.place_forget()
        else:
            if hasattr(self.app, "preview_canvas"):
                self.app.preview_canvas.delete("all")
            if hasattr(self.app, "preview_text_var"):
                self.app.preview_text_var.set("Local preview disabled")
            if hasattr(self.app, "preview_text_label"):
                self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")

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
        camera_ids_to_open = _ordered_unique_camera_ids(selected_camera_ids)[:required]

        self.active_camera_ids = [str(cam_id) for cam_id in camera_ids_to_open]
        self._sync_open_captures(self.active_camera_ids)

        if self.render_local:
            self.app.preview_text_label.place_forget()
        else:
            self.app.preview_canvas.delete("all")
            self.app.preview_text_var.set("Local preview disabled")
            self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")

        self._update_frame()

    def reorder_active_cameras(self, selected_camera_ids, mode, render_local=True):
        """
        Reorder already-open cameras without restarting capture devices.

        Returns True when the reorder was applied safely.
        Returns False when the requested layout needs a different camera set,
        so the caller can fall back to a full refresh/start.
        """
        if not selected_camera_ids:
            return False

        required_counts = {
            "single": 1,
            "pip": 2,
            "sbs": 2,
            "stacked": 2,
            "triple": 3,
            "quad": 4,
        }

        required = required_counts.get(mode, 1)
        new_active_ids = _ordered_unique_camera_ids(selected_camera_ids)[:required]

        with self.capture_lock:
            open_ids = set(self.captures.keys())

        old_active_set = set(self.active_camera_ids)
        new_active_set = set(new_active_ids)

        # Safe reorder only:
        # same camera set, different order.
        # No open/release needed, so no camera light blink.
        if new_active_set != old_active_set:
            return False

        if not new_active_set.issubset(open_ids):
            return False

        self.active_camera_ids = new_active_ids
        self.render_local = render_local

        if self.render_local and hasattr(self.app, "preview_text_label"):
            self.app.preview_text_label.place_forget()

        if self.preview_job is None:
            self._update_frame()

        return True

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
                f"requested={capture_w}x{capture_h}@{capture_fps}, "
                f"actual={actual_w}x{actual_h}@{actual_fps}"
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
                with self.capture_lock:
                    cap_to_release = self.captures.pop(cam_id, None)

                self.last_good_frames.pop(cam_id, None)
                self.failed_frame_counts.pop(cam_id, None)
                self.failed_camera_ids.discard(cam_id)

                if cap_to_release is not None:
                    if self.app.current_os == "Darwin":
                        self._release_capture_in_background(cap_to_release, cam_id)
                    else:
                        try:
                            cap_to_release.release()
                        except Exception:
                            pass

        for cam_id in needed_ids:
            cam_id = str(cam_id)

            with self.capture_lock:
                already_open = cam_id in self.captures

            if already_open or cam_id in self.opening_camera_ids:
                continue

            cam = self._camera_by_selected_id(cam_id)
            if cam is None:
                raise RuntimeError(f"Camera {cam_id} not found.")

            if self.app.current_os == "Darwin":
                self._open_capture_in_background(cam_id, cam)
            else:
                self._open_capture_sync(cam_id, cam)

    def _open_capture_sync(self, cam_id, cam):
        try:
            cap = self._open_capture(cam, self.app.mode_var.get())

            if not cap.isOpened():
                raise RuntimeError(f'Failed to open "{cam["name"]}".')

            threaded = ThreadedCapture(
                cap,
                name=cam.get("name", f"Camera {cam_id}")
            ).start()

            with self.capture_lock:
                self.captures[cam_id] = threaded

            self.failed_camera_ids.discard(cam_id)

        except Exception as e:
            print(f"Camera open warning for {cam.get('name', cam_id)}: {e}")

            self.failed_camera_ids.add(cam_id)

            self._show_status_warning(
                "One camera could not start. USB bandwidth may be overloaded. "
                "Try connecting the capture card/cameras to different USB ports."
            )

    def _open_capture_in_background(self, cam_id, cam):
        self.opening_camera_ids.add(cam_id)
        self.failed_camera_ids.discard(cam_id)

        def worker():
            try:
                print(f"[PreviewService] Opening macOS camera {cam_id} in background...")

                cap = self._open_capture(cam, self.app.mode_var.get())

                if not cap.isOpened():
                    raise RuntimeError(f'Failed to open "{cam["name"]}".')

                threaded = ThreadedCapture(
                    cap,
                    name=cam.get("name", f"Camera {cam_id}")
                ).start()

                with self.capture_lock:
                    if cam_id in self.active_camera_ids:
                        self.captures[cam_id] = threaded
                        self.failed_camera_ids.discard(cam_id)
                    else:
                        threaded.release()

                print(f"[PreviewService] macOS camera {cam_id} ready.")

            except Exception as e:
                print(f"Camera open warning for {cam.get('name', cam_id)}: {e}")

                self.failed_camera_ids.add(cam_id)

                self._show_status_warning(
                    "One camera could not start. USB bandwidth may be overloaded. "
                    "Try connecting the capture card/cameras to different USB ports."
                )

            finally:
                self.opening_camera_ids.discard(cam_id)

        threading.Thread(
            target=worker,
            name=f"MacCameraOpen-{cam_id}",
            daemon=True,
        ).start()

    def _release_capture_in_background(self, cap, cam_id):
        def worker():
            try:
                print(f"[PreviewService] Releasing macOS camera {cam_id} in background...")
                cap.release()
                print(f"[PreviewService] macOS camera {cam_id} released.")
            except Exception as e:
                print(f"[PreviewService] macOS camera {cam_id} release warning: {e}")

        threading.Thread(
            target=worker,
            name=f"MacCameraRelease-{cam_id}",
            daemon=True,
        ).start()

    def _update_frame(self):
        if not self.active_camera_ids:
            return

        # Keep capture threads warm for instant focus-in recovery, but avoid
        # pulling and composing 1080p frames while the local preview is hidden
        # and neither broadcasting nor recording is active.
        if not self.render_local and not self._has_active_output():
            self.preview_job = self.app.after(
                IDLE_CAPTURE_POLL_DELAY_MS,
                self._update_frame,
            )
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

            with self.capture_lock:
                cap = self.captures.get(cam_id)

            if cap is None:
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

        if self.frame_sink is not None:
            try:
                self.frame_sink.submit(composed)
            except Exception as e:
                print(f"Frame sink warning: {e}")

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
            output = self._fit_and_pad(frames[0], self.output_w, self.output_h)
            return self._draw_camera_numbers(output, "single", min(len(frames), 1))

        if mode == "sbs" and len(frames) >= 2:
            left = self._fit_and_pad(frames[0], self.output_w // 2, self.output_h)
            right = self._fit_and_pad(frames[1], self.output_w // 2, self.output_h)
            output = cv2.hconcat([left, right])
            return self._draw_camera_numbers(output, "sbs", 2)

        if mode == "stacked" and len(frames) >= 2:
            top = self._fit_and_pad(frames[0], self.output_w, self.output_h // 2)
            bottom = self._fit_and_pad(frames[1], self.output_w, self.output_h // 2)
            output = cv2.vconcat([top, bottom])
            return self._draw_camera_numbers(output, "stacked", 2)

        if mode == "pip" and len(frames) >= 2:
            output = self._compose_pip(frames[0], frames[1])
            return self._draw_camera_numbers(output, "pip", 2)

        if mode == "triple" and len(frames) >= 3:
            output = self._compose_triple_grid(frames[:3])
            return self._draw_camera_numbers(output, "triple", 3)

        if mode == "quad" and len(frames) >= 4:
            output = self._compose_quad_grid(frames[:4])
            return self._draw_camera_numbers(output, "quad", 4)

        output = self._fit_and_pad(frames[0], self.output_w, self.output_h)
        return self._draw_camera_numbers(output, "single", 1)

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

    def _draw_camera_numbers(self, frame, mode, count):
        h, w = frame.shape[:2]
        pad = 34

        positions = []

        if mode == "single" or count == 1:
            positions = [(pad, pad + 34)]

        elif mode == "sbs":
            positions = [
                (pad, pad + 34),
                (w // 2 + pad, pad + 34),
            ]

        elif mode == "stacked":
            positions = [
                (pad, pad + 34),
                (pad, h // 2 + pad + 34),
            ]

        elif mode == "pip":
            inset_w = int(w * 0.28)
            margin = 20
            positions = [
                (pad, pad + 34),
                (w - inset_w - margin + pad // 2, margin + pad + 22),
            ]

        elif mode == "triple":
            positions = [
                (pad, pad + 34),
                (pad, h // 2 + pad + 34),
                (w // 2 + pad, h // 2 + pad + 34),
            ]

        elif mode == "quad":
            positions = [
                (pad, pad + 34),
                (w // 2 + pad, pad + 34),
                (pad, h // 2 + pad + 34),
                (w // 2 + pad, h // 2 + pad + 34),
            ]

        for index, pos in enumerate(positions[:count], start=1):
            self._draw_camera_number(frame, str(index), pos)

        return frame

    def _draw_camera_number(self, frame, text, position):
        x, y = position

        font = cv2.FONT_HERSHEY_DUPLEX
        scale = 0.95
        thickness = 2

        # Soft shadow for readability without looking like a badge.
        cv2.putText(
            frame,
            text,
            (x + 2, y + 2),
            font,
            scale,
            (0, 0, 0),
            thickness + 2,
            cv2.LINE_AA,
        )

        # Clean white modern-looking number.
        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    def _blank_cell(self, width, height):
        return np.zeros((height, width, 3), dtype=np.uint8)

    def _fit_and_pad(self, frame, box_w, box_h):
        # Keep the output independent from the capture buffer, but avoid a
        # full-frame resize when the camera already delivered the target size.
        if frame.shape[1] == box_w and frame.shape[0] == box_h:
            return frame.copy()

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

    def stop(self, release_captures=True, clear_canvas=True):
        self.last_good_frames = {}
        self.failed_frame_counts = {}
        self.usb_warning_shown = False
        self.failed_camera_ids = set()
        self.opening_camera_ids = set()

        if self.preview_job is not None:
            try:
                self.app.after_cancel(self.preview_job)
            except Exception:
                pass
            self.preview_job = None

        if release_captures:
            with self.capture_lock:
                captures_to_release = list(self.captures.items())
                self.captures = {}

            for cam_id, cap in captures_to_release:
                try:
                    if self.app.current_os == "Darwin":
                        self._release_capture_in_background(cap, cam_id)
                    else:
                        cap.release()
                except Exception:
                    pass

            self.active_camera_ids = []

        self.preview_image_ref = None

        if clear_canvas and hasattr(self.app, "preview_canvas"):
            self.app.preview_canvas.delete("all")

        if clear_canvas and hasattr(self.app, "preview_text_label"):
            self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")
