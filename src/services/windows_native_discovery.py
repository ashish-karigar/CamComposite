import json
import platform
import subprocess
import sys
from pathlib import Path


def discover_windows_cameras_native():
    if platform.system() != "Windows":
        return []

    exe_path = _find_camera_discovery_exe()
    if exe_path is None:
        print("Windows native camera discovery failed: camera_discovery.exe not found.")
        return []

    try:
        result = subprocess.run(
            [str(exe_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            print(f"Windows native camera discovery failed with code {result.returncode}: {result.stderr}")
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
    candidates = []

    # Dev/source checkout path.
    source_root = Path(__file__).resolve().parents[2]
    candidates.extend([
        source_root / "windows_engine" / "build" / "Release" / "camera_discovery.exe",
        source_root / "windows_engine" / "build" / "camera_discovery.exe",
        source_root / "assets" / "bin" / "windows" / "camera_discovery.exe",
    ])

    # PyInstaller one-folder app path.
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent

        candidates.extend([
            exe_dir / "assets" / "bin" / "windows" / "camera_discovery.exe",
            exe_dir / "_internal" / "assets" / "bin" / "windows" / "camera_discovery.exe",
        ])

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundle_root = Path(meipass)
            candidates.append(
                bundle_root / "assets" / "bin" / "windows" / "camera_discovery.exe"
            )

    for path in candidates:
        if path.exists():
            return path

    print("camera_discovery.exe search paths checked:")
    for path in candidates:
        print(f"  {path}")

    return None