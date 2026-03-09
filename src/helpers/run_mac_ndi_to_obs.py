# run_mac_ndi_to_obs.py
import argparse
import time

import cv2
import numpy as np
import NDIlib as ndi

from src.prototypes.compositor_core import open_cam


NDI_SOURCE_NAME = "MyLens Program"


def fit_height(frame, target_h):
    h, w = frame.shape[:2]
    scale = target_h / h
    new_w = max(1, int(w * scale))
    return cv2.resize(frame, (new_w, target_h), interpolation=cv2.INTER_AREA)


def fit_width(frame, target_w):
    h, w = frame.shape[:2]
    scale = target_w / w
    new_h = max(1, int(h * scale))
    return cv2.resize(frame, (target_w, new_h), interpolation=cv2.INTER_AREA)


def compose_pip(base_bgr, pip_bgr, pip_scale=0.28, margin=20):
    base = base_bgr.copy()
    base_h, base_w = base.shape[:2]

    pip_h = int(base_h * pip_scale)
    pip_w = int(pip_bgr.shape[1] * (pip_h / pip_bgr.shape[0]))
    pip_img = cv2.resize(pip_bgr, (pip_w, pip_h), interpolation=cv2.INTER_AREA)

    x2 = base_w - margin
    y1 = margin
    x1 = x2 - pip_w
    y2 = y1 + pip_h

    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(base_w, x2)
    y2 = min(base_h, y2)

    cv2.rectangle(base, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (255, 255, 255), 2)
    base[y1:y2, x1:x2] = pip_img[:(y2 - y1), :(x2 - x1)]
    return base


def compose_sbs(a_bgr, b_bgr):
    target_h = min(a_bgr.shape[0], b_bgr.shape[0])
    a = fit_height(a_bgr, target_h)
    b = fit_height(b_bgr, target_h)
    return cv2.hconcat([a, b])


def compose_stacked(a_bgr, b_bgr):
    target_w = min(a_bgr.shape[1], b_bgr.shape[1])
    a = fit_width(a_bgr, target_w)
    b = fit_width(b_bgr, target_w)
    return cv2.vconcat([a, b])


def compose_frame(frame_a, frame_b, mode):
    if mode == "single" or frame_b is None:
        return frame_a

    if mode == "pip":
        return compose_pip(frame_a, frame_b)

    if mode == "sbs":
        return compose_sbs(frame_a, frame_b)

    if mode == "stacked":
        return compose_stacked(frame_a, frame_b)

    return frame_a


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cam-a", required=True, type=int)
    parser.add_argument("--cam-b", type=int, default=None)
    parser.add_argument("--mode", required=True, choices=["single", "pip", "sbs", "stacked"])
    args = parser.parse_args()

    if not ndi.initialize():
        raise RuntimeError("NDI initialization failed")

    send_settings = ndi.SendCreate()
    send_settings.ndi_name = NDI_SOURCE_NAME
    sender = ndi.send_create(send_settings)

    if sender is None:
        ndi.destroy()
        raise RuntimeError("Failed to create NDI sender")

    print(f"NDI sender created with source name: {NDI_SOURCE_NAME}")

    video_frame = ndi.VideoFrameV2()

    cap_a = open_cam(args.cam_a)
    cap_b = None

    if args.cam_b is not None and args.mode != "single":
        cap_b = open_cam(args.cam_b)

    try:
        while True:
            ok_a, frame_a = cap_a.read()
            if not ok_a or frame_a is None:
                time.sleep(0.01)
                continue

            frame_b = None
            if cap_b is not None and args.mode != "single":
                ok_b, temp_b = cap_b.read()
                if ok_b and temp_b is not None:
                    frame_b = temp_b

            program = compose_frame(frame_a, frame_b, args.mode)

            frame_bgrx = cv2.cvtColor(program, cv2.COLOR_BGR2BGRA)
            frame_bgrx = np.ascontiguousarray(frame_bgrx)

            h, w = frame_bgrx.shape[:2]
            video_frame.data = frame_bgrx
            video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_BGRX
            video_frame.xres = w
            video_frame.yres = h
            video_frame.line_stride_in_bytes = w * 4
            video_frame.frame_rate_N = 30000
            video_frame.frame_rate_D = 1001

            ndi.send_send_video_v2(sender, video_frame)

    finally:
        cap_a.release()
        if cap_b is not None:
            cap_b.release()

        ndi.send_destroy(sender)
        ndi.destroy()


if __name__ == "__main__":
    main()