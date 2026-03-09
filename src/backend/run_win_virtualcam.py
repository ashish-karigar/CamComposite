import cv2
from pathlib import Path

import pyvirtualcam
from pyvirtualcam import PixelFormat

from compositor_core import run_compositor
from helpers.win_unitycapture_installer import ensure_unitycapture_installed


def _project_root() -> Path:
    # Assuming structure: project_root/src/run_win_virtualcam.py
    return Path(__file__).resolve().parents[1]


def main():
    project_root = _project_root()

    # 1) Ensure UnityCapture exists and is registered BEFORE starting the pipeline
    ensure_unitycapture_installed(project_root)

    # 2) Start compositor
    gen = run_compositor(cam_a=0, cam_b=1, mode="pip", preview=True)
    first = next(gen)
    h, w = first.shape[:2]

    # 3) Start virtual cam explicitly using unitycapture backend
    with pyvirtualcam.Camera(
        width=w,
        height=h,
        fps=30,
        fmt=PixelFormat.RGB,
        backend="unitycapture",
    ) as cam:
        print(f"[i] Virtual camera started: {cam.device} ({w}x{h}@{cam.fps})")

        cam.send(cv2.cvtColor(first, cv2.COLOR_BGR2RGB))
        cam.sleep_until_next_frame()

        for program_bgr in gen:
            cam.send(cv2.cvtColor(program_bgr, cv2.COLOR_BGR2RGB))
            cam.sleep_until_next_frame()


if __name__ == "__main__":
    main()