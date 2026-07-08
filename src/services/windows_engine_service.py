import os
import subprocess
import sys
from pathlib import Path


class WindowsEngineService:
    def __init__(self):
        self.process = None
        self.current_camera_ids = []
        self.current_mode = None
        self.current_broadcasting = False
        self.runtime_base_dir = None
        self.runtime_dir = None
        self.control_file = None
        self.log_file_handle = None
        self.log_file_path = None

    def start(self, mode, camera_ids, *, force_restart=False, broadcasting=False):
        normalized_mode = str(mode)
        normalized_camera_ids = [str(cam_id) for cam_id in camera_ids]
        normalized_broadcasting = bool(broadcasting)

        exe_path = self._find_engine_exe()
        if exe_path is None:
            raise RuntimeError("Windows video engine executable not found.")

        self.runtime_base_dir = self._get_runtime_base_dir()
        self.runtime_dir = self.runtime_base_dir / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        self.control_file = self.runtime_dir / "control.txt"
        self.log_file_path = self.runtime_dir / "video_engine.log"

        self._write_control_file(
            normalized_mode,
            normalized_camera_ids,
            normalized_broadcasting,
        )

        if self.is_running() and not force_restart:
            print("[WindowsEngine] Engine already running. Updated control file only.")
            self.current_mode = normalized_mode
            self.current_camera_ids = normalized_camera_ids
            self.current_broadcasting = normalized_broadcasting
            return

        self.stop()

        args = [str(exe_path), normalized_mode] + normalized_camera_ids

        print("[WindowsEngine] Starting DirectShow shared-memory engine:")
        print("[WindowsEngine] Args:", " ".join(args))
        print("[WindowsEngine] Working directory:", self.runtime_base_dir)
        print("[WindowsEngine] Control file:", self.control_file)
        print("[WindowsEngine] Log file:", self.log_file_path)
        print("[WindowsEngine] Broadcasting:", normalized_broadcasting)

        creationflags = 0

        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NO_WINDOW

        self.log_file_handle = open(self.log_file_path, "w", encoding="utf-8", buffering=1)

        self.process = subprocess.Popen(
            args,
            cwd=str(self.runtime_base_dir),
            stdout=self.log_file_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )

        self.current_mode = normalized_mode
        self.current_camera_ids = normalized_camera_ids
        self.current_broadcasting = normalized_broadcasting

    def set_broadcasting(self, enabled):
        if not self.current_camera_ids:
            return

        self.current_broadcasting = bool(enabled)

        self._write_control_file(
            self.current_mode or "single",
            self.current_camera_ids,
            self.current_broadcasting,
        )

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
        self.current_broadcasting = False

        if self.log_file_handle is not None:
            try:
                self.log_file_handle.close()
            except Exception:
                pass
            self.log_file_handle = None

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def get_exit_code(self):
        if self.process is None:
            return None
        return self.process.poll()

    def _get_runtime_base_dir(self):
        local_app_data = os.environ.get("LOCALAPPDATA")

        if local_app_data:
            base_dir = Path(local_app_data) / "CamComposite"
        else:
            base_dir = Path.home() / "AppData" / "Local" / "CamComposite"

        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    def _write_control_file(self, mode, camera_ids, broadcasting=False):
        if self.control_file is None:
            self.runtime_base_dir = self._get_runtime_base_dir()
            self.runtime_dir = self.runtime_base_dir / "runtime"
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            self.control_file = self.runtime_dir / "control.txt"

        content = [
            f"mode={mode}",
            "cameras=" + ",".join(camera_ids),
            f"broadcasting={1 if broadcasting else 0}",
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