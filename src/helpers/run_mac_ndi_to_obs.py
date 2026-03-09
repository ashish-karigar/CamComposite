import cv2

import NDIlib as ndi
from src.backend.compositor_core import run_compositor

def main():
    if not ndi.initialize():
        raise RuntimeError("NDI initialize failed")

    send_settings = ndi.SendCreate()
    send_settings.ndi_name = "MyLens Program"
    sender = ndi.send_create(send_settings)
    if sender is None:
        raise RuntimeError("NDI send_create failed")

    frame = ndi.VideoFrameV2()

    try:
        for program_bgr in run_compositor(cam_a=1, cam_b=0, mode="pip", preview=True):
            h, w = program_bgr.shape[:2]
            program_bgrx = cv2.cvtColor(program_bgr, cv2.COLOR_BGR2BGRA)

            frame.data = program_bgrx
            frame.FourCC = ndi.FOURCC_VIDEO_TYPE_BGRX
            frame.xres = w
            frame.yres = h
            frame.line_stride_in_bytes = w * 4

            ndi.send_send_video_v2(sender, frame)

    finally:
        ndi.send_destroy(sender)
        ndi.destroy()

if __name__ == "__main__":
    main()