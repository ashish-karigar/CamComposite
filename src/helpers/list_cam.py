# list_cam.py
from tkinter import messagebox


def detect_cameras(self):
    try:
        if self.current_os == "Darwin":
            cameras = self._detect_cameras_macos()
        elif self.current_os == "Windows":
            cameras = self._detect_cameras_windows()
        else:
            messagebox.showerror("Detect Cameras", f"Unsupported OS: {self.current_os}")
            return

        self.detected_cameras = cameras
        self._populate_camera_selectors()

        if not cameras:
            self.setup_var.set("No cameras detected")
            self.preview_text_var.set("No cameras found")
            return

        if len(cameras) == 1:
            self.setup_var.set(f"1 camera detected: {cameras[0]['name']}")
            self.preview_text_var.set("Single camera mode auto-selected")
        else:
            self.setup_var.set(f"{len(cameras)} cameras detected")
            self.preview_text_var.set("Select up to 2 cameras")

    except Exception as e:
        messagebox.showerror("Detect Cameras", f"Camera detection failed:\n{e}")
        self.setup_var.set("Camera detection failed")