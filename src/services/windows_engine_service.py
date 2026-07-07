import subprocess
import sys
from pathlib import Path


class WindowsEngineService:
    def __init__(self):
        self.process = None
        self.current_camera_ids = []
        self.current_mode = None
        self.runtime_dir = None
        self.control_file = None

    def start(self, mode, camera_ids):
        normalized_mode = str(mode)
        normalized_camera_ids = [str(cam_id) for cam_id in camera_ids]

        exe_path = self._find_engine_exe()
        if exe_path is None:
            raise RuntimeError("Windows video engine executable not found.")

        workdir = exe_path.parent.parent
        self.runtime_dir = workdir / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        self.control_file = self.runtime_dir / "control.txt"

        # Always write latest requested mode/cameras.
        self._write_control_file(normalized_mode, normalized_camera_ids)

        # If engine is already running with same camera set, do NOT restart.
        # The engine will read control.txt and switch layout internally.
        if self.is_running() and normalized_camera_ids == self.current_camera_ids:
            print("[WindowsEngine] Engine already running. Updated layout control file only.")
            self.current_mode = normalized_mode
            return

        # Camera set changed, or engine is not running. Restart required.
        self.stop()

        args = [str(exe_path), normalized_mode] + normalized_camera_ids

        print("[WindowsEngine] Starting DirectShow shared-memory engine:")
        print("[WindowsEngine] Args:", " ".join(args))
        print("[WindowsEngine] Working directory:", workdir)
        print("[WindowsEngine] Control file:", self.control_file)

        creationflags = 0

        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NO_WINDOW

        self.process = subprocess.Popen(
            args,
            cwd=str(workdir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )

        self.current_mode = normalized_mode
        self.current_camera_ids = normalized_camera_ids

    def stop(self):
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    print("[WindowsEngine] Stopping engine...")
                    self.process.terminate()
                    self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                    self.process.wait(timeout=2)
                except Exception:
                    pass

        self.process = None
        self.current_mode = None
        self.current_camera_ids = []

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def _write_control_file(self, mode, camera_ids):
        if self.control_file is None:
            root = Path(__file__).resolve().parents[2]
            self.runtime_dir = root / "windows_engine" / "build" / "runtime"
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            self.control_file = self.runtime_dir / "control.txt"

        content = [
            f"mode={mode}",
            "cameras=" + ",".join(camera_ids),
        ]

        tmp_file = self.control_file.with_suffix(".tmp")
        tmp_file.write_text("\n".join(content) + "\n", encoding="utf-8")
        tmp_file.replace(self.control_file)

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