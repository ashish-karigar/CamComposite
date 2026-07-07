import threading
import time
from pathlib import Path

import cv2

from .unity_frame_sender import UnityFrameSender


class CppFrameSender:
    def __init__(self, frame_path, fps=30):
        self.frame_path = Path(frame_path)
        self.sender = UnityFrameSender(fps=fps)

        self.running = False
        self.thread = None
        self.last_mtime = None

    def start(self):
        if self.running:
            return

        self.sender.start()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            try:
                if not self.frame_path.exists():
                    time.sleep(1 / 30)
                    continue

                try:
                    mtime = self.frame_path.stat().st_mtime
                except FileNotFoundError:
                    time.sleep(1 / 30)
                    continue

                if mtime != self.last_mtime:
                    frame = cv2.imread(str(self.frame_path))

                    if frame is not None:
                        self.sender.send_frame(frame)
                        self.last_mtime = mtime

            except Exception as e:
                print(f"[CppFrameSender] read/send warning: {e}")

            time.sleep(1 / 30)

    def stop(self):
        self.running = False

        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.0)

        self.thread = None
        self.sender.stop()