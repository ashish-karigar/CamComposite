import cv2
import numpy as np
import pyvirtualcam
from pyvirtualcam import PixelFormat

from compositor_core import run_compositor

def main():
    # Start the compositor first frame to learn resolution
    gen = run_compositor(cam_a=0, cam_b=1, mode="pip", preview=True)
    first = next(gen)
    h, w = first.shape[:2]

    # pyvirtualcam expects RGB
    with pyvirtualcam.Camera(width=w, height=h, fps=30, fmt=PixelFormat.RGB) as cam:
        print(f"Virtual camera started: {cam.device} ({w}x{h}@{cam.fps})")

        # send first frame
        cam.send(cv2.cvtColor(first, cv2.COLOR_BGR2RGB))
        cam.sleep_until_next_frame()

        for program_bgr in gen:
            cam.send(cv2.cvtColor(program_bgr, cv2.COLOR_BGR2RGB))
            cam.sleep_until_next_frame()

if __name__ == "__main__":
    main()