import cv2
import time
import numpy as np
import platform

def open_cam(src: int, width=1920, height=1080, fps=30):
    system = platform.system()

    if system == "Windows":
        cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
    elif system == "Darwin":   # macOS
        cap = cv2.VideoCapture(src, cv2.CAP_AVFOUNDATION)
    else:
        cap = cv2.VideoCapture(src)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {src}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    return cap

def composite_pip(base_bgr: np.ndarray, pip_bgr: np.ndarray,
                  pip_scale=0.30, margin=20):
    """PiP: base full frame, pip in top-right."""
    H, W = base_bgr.shape[:2]
    pip_h = int(H * pip_scale)
    pip_w = int(pip_bgr.shape[1] * (pip_h / pip_bgr.shape[0]))

    pip_resized = cv2.resize(pip_bgr, (pip_w, pip_h), interpolation=cv2.INTER_AREA)

    x2 = W - margin
    y1 = margin
    x1 = x2 - pip_w
    y2 = y1 + pip_h

    # Clamp just in case
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(W, x2); y2 = min(H, y2)

    out = base_bgr.copy()
    out[y1:y2, x1:x2] = pip_resized[:(y2-y1), :(x2-x1)]
    return out

def composite_side_by_side(a_bgr: np.ndarray, b_bgr: np.ndarray):
    """Side-by-side with same height."""
    Ha, Wa = a_bgr.shape[:2]
    Hb, Wb = b_bgr.shape[:2]

    H = min(Ha, Hb)
    a = cv2.resize(a_bgr, (int(Wa * (H / Ha)), H), interpolation=cv2.INTER_AREA)
    b = cv2.resize(b_bgr, (int(Wb * (H / Hb)), H), interpolation=cv2.INTER_AREA)

    return np.hstack([a, b])

def run_compositor(cam_a=0, cam_b=1, mode="pip", preview=True):
    capA = open_cam(cam_a)
    capB = open_cam(cam_b)

    last = time.time()
    fps_smoothed = 0.0

    try:
        while True:
            okA, a = capA.read()
            okB, b = capB.read()
            if not okA or a is None:
                print("Camera A frame missing")
                continue
            if not okB or b is None:
                print("Camera B frame missing")
                continue

            if mode == "pip":
                program = composite_pip(a, b)
            elif mode == "sbs":
                program = composite_side_by_side(a, b)
            else:
                raise ValueError("mode must be 'pip' or 'sbs'")

            # FPS display (optional)
            now = time.time()
            dt = now - last
            last = now
            inst_fps = 1.0 / dt if dt > 0 else 0.0
            fps_smoothed = 0.9 * fps_smoothed + 0.1 * inst_fps

            if preview:
                cv2.putText(program, f"{mode.upper()}  {fps_smoothed:.1f} FPS",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,0), 2)
                cv2.imshow("Program", program)
                k = cv2.waitKey(1) & 0xFF
                if k == ord('q'):
                    break
                if k == ord('m'):
                    mode = "sbs" if mode == "pip" else "pip"

            yield program  # <— IMPORTANT: this yields the composited program frames

    finally:
        capA.release()
        capB.release()
        cv2.destroyAllWindows()