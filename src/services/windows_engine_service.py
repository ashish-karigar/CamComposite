import subprocess
from pathlib import Path


class WindowsEngineService:
    def __init__(self):
        self.process = None

    def start(self, mode, camera_ids):
        self.stop()

        exe_path = self._find_engine_exe()
        if exe_path is None:
            raise RuntimeError("Windows video engine executable not found.")

        # Remove old/stale bridge frame before starting engine
        frame_path = exe_path.parent.parent / "cpp_latest_frame.jpg"
        try:
            if frame_path.exists():
                frame_path.unlink()
        except Exception as e:
            print(f"[WindowsEngine] Could not delete stale frame: {e}")

        args = [str(exe_path), mode] + [str(cam_id) for cam_id in camera_ids]

        print("[WindowsEngine] Starting:", " ".join(args))
        print("[WindowsEngine] Working directory:", exe_path.parent.parent)

        self.process = subprocess.Popen(
            args,
            cwd=str(exe_path.parent.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def stop(self):
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

        self.process = None

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def _find_engine_exe(self):
        root = Path(__file__).resolve().parents[2]

        candidates = [
            root / "windows_engine" / "build" / "Release" / "video_engine.exe",
            root / "windows_engine" / "build" / "video_engine.exe",
            root / "assets" / "bin" / "windows" / "video_engine.exe",
        ]

        for path in candidates:
            if path.exists():
                return path

        return None