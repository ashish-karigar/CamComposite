# controls_panel.py
from tkinter import ttk

from .modern_widgets import RoundedButton


def build_controls_panel(app, parent):
    panel = ttk.Frame(parent, style="Panel.TFrame", padding=18)
    panel.grid(row=0, column=0, sticky="nsw", padx=(0, 18))

    form = ttk.Frame(panel, style="Panel.TFrame")
    form.pack(fill="x")

    app.cameras_frame = ttk.Frame(form, style="Panel.TFrame")
    app.cameras_frame.pack(fill="x", pady=(0, 14))

    ttk.Label(app.cameras_frame, text="Cameras", style="PanelTitle.TLabel").pack(anchor="w")
    ttk.Label(
        app.cameras_frame,
        text=f"Choose up to {app.max_cameras}. Selected cameras are numbered by preview order.",
        style="PanelText.TLabel",
        wraplength=280,
        justify="left",
    ).pack(anchor="w", pady=(4, 10))

    ttk.Label(panel, text="Session Controls", style="PanelTitle.TLabel").pack(anchor="w")
    ttk.Label(
        panel,
        text="Select cameras, choose a layout, then start broadcasting.",
        style="PanelText.TLabel",
    ).pack(anchor="w", pady=(4, 10))

    buttons = ttk.Frame(panel, style="Panel.TFrame")
    buttons.pack(fill="x", pady=(4, 10))
    buttons.columnconfigure(0, weight=1)
    buttons.columnconfigure(1, weight=1)


    setup_btn = RoundedButton(
        buttons,
        text="Run Setup Check",
        command=app.run_setup_check,
        colors=app.colors,
        width=132,
        height=44,
        radius=14,
    )
    setup_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=6)

    detect_btn = RoundedButton(
        buttons,
        text="Detect Cameras",
        command=app.detect_cameras,
        colors=app.colors,
        width=132,
        height=44,
        radius=14,
    )
    detect_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=6)

    start_btn = RoundedButton(
        buttons,
        text="Start",
        command=app.start_pipeline,
        colors=app.colors,
        width=132,
        height=46,
        radius=15,
        bg=app.colors["accent"],
        hover_bg=app.colors["accent_hover"],
        active_bg=app.colors["accent"],
        fg="white",
        border=app.colors["accent_hover"],
    )
    start_btn.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=6)

    stop_btn = RoundedButton(
        buttons,
        text="Stop",
        command=app.stop_pipeline,
        colors=app.colors,
        width=132,
        height=46,
        radius=15,
        bg="#2A1620",
        hover_bg="#3A1D2A",
        active_bg="#2A1620",
        fg="#FCA5A5",
        border="#3A1D2A",
    )
    stop_btn.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=6)

    health = ttk.Frame(panel, style="Inner.TFrame", padding=14)
    health.pack(fill="x", pady=(14, 0))

    ttk.Label(health, text="Setup Status", style="InnerTitle.TLabel").pack(anchor="w")
    ttk.Label(
        health,
        textvariable=app.setup_var,
        style="CardValue.TLabel",
        wraplength=260,
        justify="left",
    ).pack(anchor="w", pady=(6, 0))
    ttk.Label(
        health,
        text=f"Platform: {app.current_os}",
        style="InnerText.TLabel",
    ).pack(anchor="w", pady=(12, 0))

    return panel