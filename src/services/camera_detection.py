import platform
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import cv2


HIDDEN_MAC_KEYWORDS = ("obs", "virtual camera", "capture screen")
LOW_PRIORITY_MAC_KEYWORDS = ("iphone", "continuity", "desk view")


def detect_cameras_for_current_os():
    current_os = platform.system()

    if current_os == "Darwin":
        return detect_cameras_macos()

    if current_os == "Windows":
        return detect_cameras_windows()

    return []


def detect_cameras_macos():
    from .mac_avfoundation_capture import list_avfoundation_cameras

    cameras = list_avfoundation_cameras()

    visible_cameras = []
    for camera in cameras:
        name = camera["name"].lower()

        if "obs" in name or "virtual camera" in name:
            continue

        visible_cameras.append(camera)

    return sorted(visible_cameras, key=_mac_camera_sort_key)


def detect_cameras_windows():
    cameras = []

    for index in _detect_opencv_camera_indices_windows():
        cameras.append({
            "id": index,
            "name": f"Camera {index}",
            "preview_index": index,
        })

    return cameras


def _detect_opencv_camera_indices_windows(max_tested=8, stop_after_misses=3):
    indices = []
    misses = 0

    for index in range(max_tested):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)

        if cap is not None and cap.isOpened():
            ok, _ = cap.read()
            cap.release()

            if ok:
                indices.append(index)
                misses = 0
                continue

        misses += 1

        if misses >= stop_after_misses and indices:
            break

    return indices


@lru_cache(maxsize=1)
def _find_ffmpeg():
    project_root = Path(__file__).resolve().parents[2]
    bundled_ffmpeg = project_root / "assets" / "bin" / "macos" / "ffmpeg"

    if bundled_ffmpeg.exists() and _is_ffmpeg_working(str(bundled_ffmpeg)):
        return str(bundled_ffmpeg)

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg and _is_ffmpeg_working(system_ffmpeg):
        return system_ffmpeg

    return None


def _is_ffmpeg_working(ffmpeg_path: str) -> bool:
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return result.returncode == 0
    except Exception:
        return False


def _parse_macos_avfoundation_devices(output: str):
    cameras = []
    seen_names = set()
    in_video_section = False

    for raw_line in output.splitlines():
        line = raw_line.strip()

        if "AVFoundation video devices" in line:
            in_video_section = True
            continue

        if "AVFoundation audio devices" in line:
            break

        if not in_video_section:
            continue

        match = re.search(r"\[(\d+)\]\s+(.+)", line)
        if not match:
            continue

        cam_id = int(match.group(1))
        cam_name = match.group(2).strip()
        normalized = cam_name.lower()

        if any(keyword in normalized for keyword in HIDDEN_MAC_KEYWORDS):
            continue

        if normalized in seen_names:
            continue

        seen_names.add(normalized)

        cameras.append({
            "id": cam_id,
            "name": cam_name,
            "preview_index": len(cameras),
        })

    return cameras


def _mac_camera_sort_key(camera):
    name = camera["name"].lower()

    is_low_priority = any(keyword in name for keyword in LOW_PRIORITY_MAC_KEYWORDS)

    return (
        1 if is_low_priority else 0,
        camera["name"].lower(),
        camera["id"],
    )


if __name__ == "__main__":
    print("ffmpeg path:", _find_ffmpeg())

    cameras = detect_cameras_for_current_os()

    if not cameras:
        print("No cameras detected.")
    else:
        print("Detected cameras:")
        for cam in cameras:
            print(
                f'  ID: {cam["id"]} | Preview Index: {cam["preview_index"]} | Name: {cam["name"]}'
            )