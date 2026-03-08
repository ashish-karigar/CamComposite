import cv2

def try_open(i):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # DirectShow on Windows
    ok = cap.isOpened()
    if ok:
        ok2, frame = cap.read()
        ok = ok2 and frame is not None
    cap.release()
    return ok

found = []
for i in range(0, 10):
    if try_open(i):
        found.append(i)

print("Working camera indices:", found)