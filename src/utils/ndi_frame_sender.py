# ndi_frame_sender.py
import cv2
import numpy as np
import NDIlib as ndi


NDI_SOURCE_NAME = "MyLens Program"


class NDIFrameSender:
    def __init__(self):
        self.running = False
        self.initialized = False
        self.sender = None
        self.video_frame = None

    def start(self):
        if self.running:
            return

        if not ndi.initialize():
            raise RuntimeError("NDI initialization failed")

        send_settings = ndi.SendCreate()
        send_settings.ndi_name = NDI_SOURCE_NAME
        self.sender = ndi.send_create(send_settings)

        if self.sender is None:
            ndi.destroy()
            raise RuntimeError("Failed to create NDI sender")

        self.video_frame = ndi.VideoFrameV2()
        self.running = True
        self.initialized = True
        print(f"NDI sender started: {NDI_SOURCE_NAME}")

    def send_frame(self, frame_bgr):
        if not self.running or self.sender is None:
            return

        if frame_bgr is None or frame_bgr.size == 0:
            return

        frame_bgrx = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2BGRA)
        frame_bgrx = np.ascontiguousarray(frame_bgrx)

        h, w = frame_bgrx.shape[:2]
        self.video_frame.data = frame_bgrx
        self.video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_BGRX
        self.video_frame.xres = w
        self.video_frame.yres = h
        self.video_frame.line_stride_in_bytes = w * 4
        self.video_frame.frame_rate_N = 30000
        self.video_frame.frame_rate_D = 1001

        ndi.send_send_video_v2(self.sender, self.video_frame)

    def stop(self):
        if self.sender is not None:
            try:
                ndi.send_destroy(self.sender)
            except Exception:
                pass
            self.sender = None

        if self.initialized:
            try:
                ndi.destroy()
            except Exception:
                pass

        self.video_frame = None
        self.running = False
        self.initialized = False
        print("NDI sender stopped")