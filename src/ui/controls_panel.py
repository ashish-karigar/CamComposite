# controls_panel.py
from tkinter import ttk


def build_controls_panel(app, parent):
    panel = ttk.Frame(parent, style="Panel.TFrame", padding=18)
    panel.grid(row=0, column=0, sticky="nsw", padx=(0, 18))

    ttk.Label(panel, text="Session Controls", style="PanelTitle.TLabel").pack(anchor="w")
    ttk.Label(
        panel,
        text="Choose cameras, layout, and startup behavior.",
        style="PanelText.TLabel",
    ).pack(anchor="w", pady=(4, 16))

    form = ttk.Frame(panel, style="Panel.TFrame")
    form.pack(fill="x")

    app.cameras_frame = ttk.Frame(form, style="Panel.TFrame")
    app.cameras_frame.pack(fill="x", pady=(0, 12))

    ttk.Label(app.cameras_frame, text="Cameras", style="PanelText.TLabel").pack(anchor="w")

    ttk.Checkbutton(
        panel,
        text="Show local preview window",
        variable=app.preview_var,
    ).pack(anchor="w", pady=(8, 6))

    ttk.Checkbutton(
        panel,
        text="Hide OBS in background",
        variable=app.auto_hide_obs_var,
    ).pack(anchor="w", pady=(0, 16))

    buttons = ttk.Frame(panel, style="Panel.TFrame")
    buttons.pack(fill="x", pady=(4, 10))
    buttons.columnconfigure(0, weight=1)
    buttons.columnconfigure(1, weight=1)

    ttk.Button(
        buttons,
        text="Run Setup Check",
        command=app.run_setup_check,
        style="Secondary.TButton",
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=6)

    ttk.Button(
        buttons,
        text="Detect Cameras",
        command=app.detect_cameras,
        style="Secondary.TButton",
    ).grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=6)

    ttk.Button(
        buttons,
        text="Start",
        command=app.start_pipeline,
        style="Primary.TButton",
    ).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=6)

    ttk.Button(
        buttons,
        text="Stop",
        command=app.stop_pipeline,
        style="Secondary.TButton",
    ).grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=6)

    health = ttk.Frame(panel, style="Inner.TFrame", padding=14)
    health.pack(fill="x", pady=(14, 0))

    ttk.Label(health, text="Setup Status", style="InnerText.TLabel").pack(anchor="w")
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