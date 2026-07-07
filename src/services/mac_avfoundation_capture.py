import ctypes
import threading
import time

import AVFoundation
import CoreMedia
import Foundation
import Quartz
import objc
import dispatch
import numpy as np


try:
    CamCompositeAVFrameDelegate = objc.lookUpClass("CamCompositeAVFrameDelegate")
except objc.error:
    class CamCompositeAVFrameDelegate(Foundation.NSObject):
        def init(self):
            self = objc.super(CamCompositeAVFrameDelegate, self).init()
            if self is None:
                return None

            self.latest_frame = None
            self.lock = threading.Lock()
            return self

        def captureOutput_didOutputSampleBuffer_fromConnection_(
            self,
            output,
            sample_buffer,
            connection,
        ):
            pixel_buffer = CoreMedia.CMSampleBufferGetImageBuffer(sample_buffer)
            if pixel_buffer is None:
                return

            Quartz.CVPixelBufferLockBaseAddress(pixel_buffer, 0)

            try:
                width = int(Quartz.CVPixelBufferGetWidth(pixel_buffer))
                height = int(Quartz.CVPixelBufferGetHeight(pixel_buffer))
                bytes_per_row = int(Quartz.CVPixelBufferGetBytesPerRow(pixel_buffer))
                base_address = Quartz.CVPixelBufferGetBaseAddress(pixel_buffer)

                if (
                    not base_address
                    or width <= 0
                    or height <= 0
                    or bytes_per_row <= 0
                ):
                    return

                size = bytes_per_row * height

                if hasattr(base_address, "as_buffer"):
                    raw = base_address.as_buffer(size)
                else:
                    raw = ctypes.string_at(base_address, size)

                arr = np.frombuffer(raw, dtype=np.uint8, count=size)
                bgra = arr.reshape((height, bytes_per_row // 4, 4))[:, :width, :]

                # BGRA -> BGR
                bgr = bgra[:, :, :3].copy()

                with self.lock:
                    self.latest_frame = bgr

            except Exception as e:
                print(f"AVFoundation frame copy warning: {e}")

            finally:
                Quartz.CVPixelBufferUnlockBaseAddress(pixel_buffer, 0)

        @objc.python_method
        def read_latest(self):
            with self.lock:
                if self.latest_frame is None:
                    return False, None

                return True, self.latest_frame.copy()


def list_avfoundation_cameras():
    devices = AVFoundation.AVCaptureDevice.devicesWithMediaType_(
        AVFoundation.AVMediaTypeVideo
    )

    cameras = []

    for device in devices:
        name = str(device.localizedName())
        unique_id = str(device.uniqueID())

        cameras.append(
            {
                "id": unique_id,
                "name": name,
                "unique_id": unique_id,
                "preview_index": unique_id,
            }
        )

    return cameras


class MacAVFoundationCapture:
    def __init__(self, unique_id, width=1280, height=720, fps=30):
        self.unique_id = unique_id
        self.width = width
        self.height = height
        self.fps = fps

        self.session = None
        self.device_input = None
        self.output = None
        self.delegate = None
        self.queue = None

    def open(self):
        device = AVFoundation.AVCaptureDevice.deviceWithUniqueID_(self.unique_id)
        if device is None:
            return False

        self.session = AVFoundation.AVCaptureSession.alloc().init()
        self.session.beginConfiguration()
        self.session.setSessionPreset_(AVFoundation.AVCaptureSessionPreset1280x720)

        self.device_input, error = (
            AVFoundation.AVCaptureDeviceInput.deviceInputWithDevice_error_(
                device,
                None,
            )
        )

        if error is not None or self.device_input is None:
            self.session.commitConfiguration()
            return False

        if not self.session.canAddInput_(self.device_input):
            self.session.commitConfiguration()
            return False

        self.session.addInput_(self.device_input)

        self.output = AVFoundation.AVCaptureVideoDataOutput.alloc().init()
        self.output.setAlwaysDiscardsLateVideoFrames_(True)
        self.output.setVideoSettings_(
            {
                Quartz.kCVPixelBufferPixelFormatTypeKey: Quartz.kCVPixelFormatType_32BGRA
            }
        )

        self.delegate = CamCompositeAVFrameDelegate.alloc().init()
        self.queue = dispatch.dispatch_queue_create(
            b"com.camcomposite.avfoundation.capture",
            None,
        )

        self.output.setSampleBufferDelegate_queue_(self.delegate, self.queue)

        if not self.session.canAddOutput_(self.output):
            self.session.commitConfiguration()
            return False

        self.session.addOutput_(self.output)
        self.session.commitConfiguration()
        self.session.startRunning()

        deadline = time.time() + 2.0

        while time.time() < deadline:
            ok, frame = self.read()
            if ok and frame is not None:
                return True

            time.sleep(0.03)

        return self.isOpened()

    def isOpened(self):
        return self.session is not None and bool(self.session.isRunning())

    def read(self):
        if self.delegate is None:
            return False, None

        return self.delegate.read_latest()

    def release(self):
        if self.output is not None:
            try:
                self.output.setSampleBufferDelegate_queue_(None, None)
            except Exception:
                pass

        if self.session is not None:
            try:
                self.session.stopRunning()
            except Exception:
                pass

        self.session = None
        self.device_input = None
        self.output = None
        self.delegate = None
        self.queue = None