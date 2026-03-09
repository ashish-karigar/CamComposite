# camera_detection.py
import platform
import re
import shutil
import subprocess
import cv2


def detect_cameras_for_current_os():
    current_os = platform.system()

    if current_os == "Darwin":
        named_cameras = detect_cameras_macos()
    elif current_os == "Windows":
        named_cameras = detect_cameras_windows()
    else:
        return []

    preview_indices = detect_opencv_camera_indices()

    cameras = []
    for i, cam in enumerate(named_cameras):
        preview_index = preview_indices[i] if i < len(preview_indices) else cam["id"]
        cameras.append({
            "id": cam["id"],
            "name": cam["name"],
            "preview_index": preview_index,
        })

    return cameras


def detect_cameras_macos():
    ffmpeg_path = _find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg and make sure it is in PATH.")

    result = subprocess.run(
        [ffmpeg_path, "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    )

    output = (result.stdout or "") + "\n" + (result.stderr or "")
    return _parse_macos_avfoundation_devices(output)


def detect_cameras_windows():
    ffmpeg_path = _find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg and make sure it is in PATH.")

    result = subprocess.run(
        [ffmpeg_path, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True,
        text=True,
    )

    output = (result.stdout or "") + "\n" + (result.stderr or "")
    return _parse_windows_dshow_devices(output)


def detect_opencv_camera_indices(max_tested=10):
    indices = []

    for index in range(max_tested):
        cap = cv2.VideoCapture(index)
        if cap is not None and cap.isOpened():
            ok, _ = cap.read()
            cap.release()
            if ok:
                indices.append(index)

    return indices


def _find_ffmpeg():
    return shutil.which("ffmpeg")


def _parse_macos_avfoundation_devices(output: str):
    cameras = []
    in_video_section = False

    for line in output.splitlines():
        line = line.strip()

        if "AVFoundation video devices" in line:
            in_video_section = True
            continue

        if "AVFoundation audio devices" in line:
            in_video_section = False
            continue

        if not in_video_section:
            continue

        match = re.search(r"\[(\d+)\]\s+(.+)", line)
        if match:
            cam_id = int(match.group(1))
            cam_name = match.group(2).strip()

            if not _is_duplicate_name(cameras, cam_name):
                cameras.append({"id": cam_id, "name": cam_name})

    return cameras


def _parse_windows_dshow_devices(output: str):
    cameras = []
    in_video_section = False
    next_id = 0

    for raw_line in output.splitlines():
        line = raw_line.strip()

        if "DirectShow video devices" in line:
            in_video_section = True
            continue

        if "DirectShow audio devices" in line:
            in_video_section = False
            continue

        if not in_video_section:
            continue

        match = re.search(r'"([^"]+)"', line)
        if match:
            cam_name = match.group(1).strip()

            if cam_name.startswith("@device_"):
                continue

            if not _is_duplicate_name(cameras, cam_name):
                cameras.append({"id": next_id, "name": cam_name})
                next_id += 1

    return cameras


def _is_duplicate_name(devices, name):
    return any(device["name"] == name for device in devices)


if __name__ == "__main__":
    try:
        cameras = detect_cameras_for_current_os()

        if not cameras:
            print("No cameras detected.")
        else:
            print("Detected cameras:")
            for cam in cameras:
                print(
                    f'  ID: {cam["id"]} | Preview Index: {cam["preview_index"]} | Name: {cam["name"]}'
                )
    except Exception as e:
        print(f"Camera detection failed: {e}")