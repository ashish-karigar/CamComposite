import threading
import time

import cv2
import numpy as np
import pyvirtualcam
from pyvirtualcam import PixelFormat


OUTPUT_W = 1280
OUTPUT_H = 720


class UnityFrameSender:
    def __init__(self, fps=30, width=OUTPUT_W, height=OUTPUT_H):
        self.fps = fps
        self.width = width
        self.height = height

        self.cam = None
        self.running = False

        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.thread = None

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def send_frame(self, frame_bgr):
        if frame_bgr is None or frame_bgr.size == 0:
            return

        frame_bgr = self._fit_and_pad(frame_bgr, self.width, self.height)

        with self.frame_lock:
            self.latest_frame = frame_bgr

    def _run(self):
        try:
            with pyvirtualcam.Camera(
                width=self.width,
                height=self.height,
                fps=self.fps,
                fmt=PixelFormat.RGB,
                backend="unitycapture",
            ) as cam:
                self.cam = cam
                print(
                    f'[i] UnityCapture virtual camera started: {cam.device} '
                    f'({self.width}x{self.height}@{cam.fps})'
                )

                blank = np.zeros((self.height, self.width, 3), dtype=np.uint8)

                while self.running:
                    with self.frame_lock:
                        frame_to_send = (
                            self.latest_frame.copy()
                            if self.latest_frame is not None
                            else blank
                        )

                    rgb_frame = cv2.cvtColor(frame_to_send, cv2.COLOR_BGR2RGB)
                    cam.send(rgb_frame)
                    cam.sleep_until_next_frame()

        except Exception as e:
            print(f"UnityFrameSender error: {e}")

        finally:
            self.cam = None

    def _fit_and_pad(self, frame, box_w, box_h):
        h, w = frame.shape[:2]

        if h <= 0 or w <= 0:
            return np.zeros((box_h, box_w, 3), dtype=np.uint8)

        scale = min(box_w / w, box_h / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((box_h, box_w, 3), dtype=np.uint8)

        x = (box_w - new_w) // 2
        y = (box_h - new_h) // 2
        canvas[y:y + new_h, x:x + new_w] = resized

        return canvas

    def stop(self):
        self.running = False

        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.5)

        self.thread = None
        self.latest_frame = None
        self.cam = None