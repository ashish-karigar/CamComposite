import json
import platform
import subprocess
from pathlib import Path


def discover_windows_cameras_native():
    if platform.system() != "Windows":
        return []

    exe_path = _find_camera_discovery_exe()
    if exe_path is None:
        return []

    try:
        result = subprocess.run(
            [str(exe_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return []

        cameras = json.loads(result.stdout)

        return [
            {
                "id": cam["id"],
                "name": cam["name"],
                "device_path": cam.get("device_path", ""),
                "preview_index": cam["preview_index"],
            }
            for cam in cameras
        ]

    except Exception as e:
        print(f"Windows native camera discovery failed: {e}")
        return []


def _find_camera_discovery_exe():
    root = Path(__file__).resolve().parents[2]

    candidates = [
        root / "windows_engine" / "build" / "Release" / "camera_discovery.exe",
        root / "windows_engine" / "build" / "camera_discovery.exe",
        root / "assets" / "bin" / "windows" / "camera_discovery.exe",
    ]

    for path in candidates:
        if path.exists():
            return path

    return None