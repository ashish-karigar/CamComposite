# src/utils/unity_frame_sender.py

import threading
import time

import cv2
import pyvirtualcam
from pyvirtualcam import PixelFormat


class UnityFrameSender:
    def __init__(self, fps=30):
        self.fps = fps

        self.cam = None
        self.running = False

        self.width = None
        self.height = None

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
        if frame_bgr is None:
            return

        h, w = frame_bgr.shape[:2]

        if self.width is None or self.height is None:
            self.width = w
            self.height = h

        if w != self.width or h != self.height:
            frame_bgr = cv2.resize(frame_bgr, (self.width, self.height))

        with self.frame_lock:
            self.latest_frame = frame_bgr.copy()

    def _run(self):
        while self.running and (self.width is None or self.height is None):
            time.sleep(0.01)

        if not self.running:
            return

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

                while self.running:
                    frame_to_send = None

                    with self.frame_lock:
                        if self.latest_frame is not None:
                            frame_to_send = self.latest_frame.copy()

                    if frame_to_send is not None:
                        rgb_frame = cv2.cvtColor(frame_to_send, cv2.COLOR_BGR2RGB)
                        cam.send(rgb_frame)

                    cam.sleep_until_next_frame()

        except Exception as e:
            print(f"UnityFrameSender error: {e}")

        finally:
            self.cam = None

    def stop(self):
        self.running = False

        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.5)

        self.thread = None
        self.latest_frame = None
        self.width = None
        self.height = None
        self.cam = None