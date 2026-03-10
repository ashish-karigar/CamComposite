import tkinter as tk
from tkinter import ttk


class StartupSplash(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.overrideredirect(True)
        self.geometry("700x420")
        self.resizable(False, False)

        self.configure(bg="#111111")

        self.status_var = tk.StringVar(value="Starting setup...")
        self.detail_var = tk.StringVar(value="Please wait while CamComposite checks dependencies.")

        container = tk.Frame(self, bg="#111111", padx=28, pady=28)
        container.pack(fill="both", expand=True)

        title = tk.Label(
            container,
            text="CamComposite",
            font=("SF Pro Display", 26, "bold"),
            fg="#cfcfcf",
            bg="#111111",
        )
        title.pack(anchor="w", pady=(0, 12))

        subtitle = tk.Label(
            container,
            text="Preparing your environment",
            font=("SF Pro Display", 13),
            fg="#cfcfcf",
            bg="#111111",
        )
        subtitle.pack(anchor="w", pady=(0, 24))

        status = tk.Label(
            container,
            textvariable=self.status_var,
            font=("SF Pro Display", 16, "bold"),
            fg="white",
            bg="#111111",
        )
        status.pack(anchor="w", pady=(0, 10))

        detail = tk.Label(
            container,
            textvariable=self.detail_var,
            font=("SF Pro Display", 12),
            fg="#cfcfcf",
            bg="#111111",
            wraplength=620,
            justify="left",
        )
        detail.pack(anchor="w", pady=(0, 18))

        self.progress = ttk.Progressbar(container, mode="indeterminate", length=620)
        self.progress.pack(anchor="w", pady=(0, 18))
        self.progress.start(10)

        self.log_box = tk.Text(
            container,
            height=10,
            width=78,
            bg="#1b1b1b",
            fg="#e8e8e8",
            insertbackground="white",
            relief="flat",
            bd=0,
            font=("Menlo", 11),
        )
        self.log_box.pack(fill="both", expand=True)
        self.log_box.insert("end", "CamComposite startup initialized...\n")
        self.log_box.configure(state="disabled")

        self.protocol("WM_DELETE_WINDOW", lambda: None)

    def set_status(self, status: str, detail: str = ""):
        self.status_var.set(status)
        self.detail_var.set(detail)
        self.update_idletasks()

    def append_log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.update_idletasks()

    def shutdown(self):
        try:
            self.progress.stop()
        except Exception:
            pass