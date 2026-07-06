import threading
import time


class ThreadedCapture:
    def __init__(self, capture, name="Camera"):
        self.capture = capture
        self.name = name

        self.running = False
        self.thread = None

        self.latest_frame = None
        self.latest_ok = False
        self.lock = threading.Lock()

    def start(self):
        if self.running:
            return self

        self.running = True
        self.thread = threading.Thread(
            target=self._reader_loop,
            name=f"ThreadedCapture-{self.name}",
            daemon=True,
        )
        self.thread.start()
        return self

    def _reader_loop(self):
        while self.running:
            try:
                ok, frame = self.capture.read()

                if ok and frame is not None:
                    with self.lock:
                        self.latest_ok = True
                        self.latest_frame = frame
                else:
                    time.sleep(0.01)

            except Exception as e:
                print(f"[ThreadedCapture] {self.name} read warning: {e}")
                time.sleep(0.03)

    def read(self):
        with self.lock:
            if not self.latest_ok or self.latest_frame is None:
                return False, None
            return True, self.latest_frame.copy()

    def isOpened(self):
        try:
            return self.capture is not None and self.capture.isOpened()
        except Exception:
            return False

    def release(self):
        self.running = False

        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.0)

        self.thread = None

        try:
            if self.capture is not None:
                self.capture.release()
        except Exception:
            pass

        self.capture = None
        self.latest_frame = None
        self.latest_ok = False