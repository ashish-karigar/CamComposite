import ctypes
import ctypes.wintypes
import struct

import cv2
import numpy as np
from PIL import Image, ImageTk

try:
    from constants import get_video_profile
except ImportError:
    from src.constants import get_video_profile


PREVIEW_DELAY_MS = 30

CAMCOMP_SHARED_MEMORY_NAME = "Local\\CamCompositeFrameBuffer"

CAMCOMP_MAGIC = 0x43434D50
CAMCOMP_VERSION = 3

CAMCOMP_WIDTH = 1920
CAMCOMP_HEIGHT = 1080
CAMCOMP_BYTES_PER_PIXEL = 2
CAMCOMP_FRAME_SIZE = CAMCOMP_WIDTH * CAMCOMP_HEIGHT * CAMCOMP_BYTES_PER_PIXEL
CAMCOMP_BUFFER_COUNT = 2

HEADER_FORMAT = "<11i"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
SHARED_MEMORY_SIZE = HEADER_SIZE + (CAMCOMP_BUFFER_COUNT * CAMCOMP_FRAME_SIZE)

FILE_MAP_READ = 0x0004

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

kernel32.OpenFileMappingW.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.wintypes.BOOL,
    ctypes.wintypes.LPCWSTR,
]
kernel32.OpenFileMappingW.restype = ctypes.wintypes.HANDLE

kernel32.MapViewOfFile.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.c_size_t,
]
kernel32.MapViewOfFile.restype = ctypes.c_void_p

kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
kernel32.UnmapViewOfFile.restype = ctypes.wintypes.BOOL

kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
kernel32.CloseHandle.restype = ctypes.wintypes.BOOL


class WindowsSharedPreviewService:
    def __init__(self, app):
        self.app = app
        self.preview_job = None
        self.preview_image_ref = None
        self.h_map = None
        self.view_ptr = None
        self.last_good_bgr = None
        self.frame_sink = None
        self.render_local = True
        self.video_profile = get_video_profile()
        self.output_w = self.video_profile["width"]
        self.output_h = self.video_profile["height"]

    def set_frame_sink(self, sink):
        self.frame_sink = sink

    def set_render_local(self, enabled):
        self.render_local = bool(enabled)

    def start(self, render_local=True):
        self._cancel_preview_loop()
        self.render_local = bool(render_local)

        if not self._open_shared_memory():
            if self.render_local:
                self._show_waiting_message()
            self.preview_job = self.app.after(
                250,
                lambda: self.start(render_local=self.render_local),
            )
            return

        self._update_frame()

    def stop(self, clear_canvas=True):
        self._cancel_preview_loop()
        self._close_shared_memory()

        self.last_good_bgr = None
        self.preview_image_ref = None

        if clear_canvas and hasattr(self.app, "preview_canvas"):
            self.app.preview_canvas.delete("all")

    def _cancel_preview_loop(self):
        if self.preview_job is not None:
            try:
                self.app.after_cancel(self.preview_job)
            except Exception:
                pass
            self.preview_job = None

    def _open_shared_memory(self):
        if self.view_ptr is not None:
            return True

        self.h_map = kernel32.OpenFileMappingW(
            FILE_MAP_READ,
            False,
            CAMCOMP_SHARED_MEMORY_NAME,
        )

        if not self.h_map:
            self.h_map = None
            return False

        self.view_ptr = kernel32.MapViewOfFile(
            self.h_map,
            FILE_MAP_READ,
            0,
            0,
            SHARED_MEMORY_SIZE,
        )

        if not self.view_ptr:
            kernel32.CloseHandle(self.h_map)
            self.h_map = None
            self.view_ptr = None
            return False

        return True

    def _close_shared_memory(self):
        if self.view_ptr is not None:
            try:
                kernel32.UnmapViewOfFile(self.view_ptr)
            except Exception:
                pass
            self.view_ptr = None

        if self.h_map is not None:
            try:
                kernel32.CloseHandle(self.h_map)
            except Exception:
                pass
            self.h_map = None

    def _read_bytes(self, offset, size):
        if self.view_ptr is None:
            return None

        try:
            return ctypes.string_at(self.view_ptr + offset, size)
        except Exception:
            return None

    def _read_header(self):
        raw = self._read_bytes(0, HEADER_SIZE)
        if raw is None or len(raw) != HEADER_SIZE:
            return None

        try:
            return struct.unpack(HEADER_FORMAT, raw)
        except Exception:
            return None

    def _read_frame(self):
        if self.view_ptr is None:
            return None

        header = self._read_header()
        if header is None:
            return None

        (
            magic,
            version,
            width,
            height,
            bytes_per_pixel,
            frame_size,
            buffer_count,
            writing,
            readable_buffer_index,
            frame_index_before,
            broadcasting,
        ) = header

        # Critical: do not render uninitialized shared memory.
        # A fresh YUY2 zero buffer looks green.
        if frame_index_before <= 0:
            return None

        if (
            magic != CAMCOMP_MAGIC
            or version != CAMCOMP_VERSION
            or width != CAMCOMP_WIDTH
            or height != CAMCOMP_HEIGHT
            or bytes_per_pixel != CAMCOMP_BYTES_PER_PIXEL
            or frame_size != CAMCOMP_FRAME_SIZE
            or buffer_count != CAMCOMP_BUFFER_COUNT
            or readable_buffer_index < 0
            or readable_buffer_index >= CAMCOMP_BUFFER_COUNT
        ):
            return None

        buffer_offset = HEADER_SIZE + (readable_buffer_index * CAMCOMP_FRAME_SIZE)
        frame_bytes = self._read_bytes(buffer_offset, CAMCOMP_FRAME_SIZE)

        if frame_bytes is None or len(frame_bytes) != CAMCOMP_FRAME_SIZE:
            return None

        header_after = self._read_header()
        if header_after is None:
            return None

        frame_index_after = header_after[9]
        readable_buffer_after = header_after[8]

        if frame_index_before != frame_index_after or readable_buffer_index != readable_buffer_after:
            return None

        try:
            yuy2 = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(
                (CAMCOMP_HEIGHT, CAMCOMP_WIDTH, 2)
            )

            bgr = cv2.cvtColor(yuy2, cv2.COLOR_YUV2BGR_YUY2)
            return bgr
        except Exception:
            return None

    def _update_frame(self):
        frame = self._read_frame()

        if frame is not None:
            self.last_good_bgr = frame
        elif self.last_good_bgr is not None:
            frame = self.last_good_bgr
        else:
            self._show_waiting_message()
            self.preview_job = self.app.after(250, self._update_frame)
            return

        if self.frame_sink is not None:
            try:
                self.frame_sink.submit(frame)
            except Exception as exc:
                print(f"Windows frame sink warning: {exc}")

        if not self.render_local:
            self.preview_job = self.app.after(PREVIEW_DELAY_MS, self._update_frame)
            return

        if hasattr(self.app, "preview_text_label"):
            self.app.preview_text_label.place_forget()

        canvas_w = max(self.app.preview_canvas.winfo_width(), 640)
        canvas_h = max(self.app.preview_canvas.winfo_height(), 360)

        display_frame = self._fit_inside_box(frame, canvas_w, canvas_h)
        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

        image = Image.fromarray(display_frame)
        photo = ImageTk.PhotoImage(image=image)
        self.preview_image_ref = photo

        self.app.preview_canvas.delete("all")

        img_h, img_w = display_frame.shape[:2]
        x = (canvas_w - img_w) // 2
        y = (canvas_h - img_h) // 2

        self.app.preview_canvas.create_image(
            x,
            y,
            anchor="nw",
            image=photo,
        )

        self.preview_job = self.app.after(PREVIEW_DELAY_MS, self._update_frame)

    def _fit_inside_box(self, frame, box_w, box_h):
        h, w = frame.shape[:2]

        if h <= 0 or w <= 0:
            return np.zeros((box_h, box_w, 3), dtype=np.uint8)

        scale = min(box_w / w, box_h / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def _show_waiting_message(self):
        if hasattr(self.app, "preview_canvas"):
            self.app.preview_canvas.delete("all")

        if hasattr(self.app, "preview_text_label"):
            self.app.preview_text_label.configure(
                font=("Helvetica", 14, "normal"),
                fg=self.app.colors["muted"],
            )

        self.app.preview_text_var.set("Loading preview...")
        self.app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")
