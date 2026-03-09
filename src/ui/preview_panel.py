# preview_panel.py
import tkinter as tk
from tkinter import ttk


def build_preview_panel(app, parent):
    panel = ttk.Frame(parent, style="Panel.TFrame", padding=18)
    panel.grid(row=0, column=1, sticky="nsew")
    panel.rowconfigure(2, weight=1)
    panel.columnconfigure(0, weight=1)

    top = ttk.Frame(panel, style="Panel.TFrame")
    top.grid(row=0, column=0, sticky="ew")
    top.columnconfigure((0, 1, 2, 3), weight=1)

    build_layout_tile(app, top, 0, "pip", "Picture in Picture", "One large feed with a floating inset")
    build_layout_tile(app, top, 1, "sbs", "Side by Side", "Two camera feeds displayed next to each other")
    build_layout_tile(app, top, 2, "stacked", "Top and Bottom", "One feed above the other in a vertical stack")
    build_layout_tile(app, top, 3, "single", "Single", "Only the main camera is shown")

    ttk.Label(panel, text="Preview", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(18, 10))

    preview_shell = tk.Frame(
        panel,
        bg=app.colors["preview"],
        highlightthickness=1,
        highlightbackground=app.colors["border"],
    )
    preview_shell.grid(row=2, column=0, sticky="nsew")
    preview_shell.grid_rowconfigure(0, weight=1)
    preview_shell.grid_columnconfigure(0, weight=1)

    center = tk.Frame(preview_shell, bg=app.colors["preview"])
    center.grid(row=0, column=0, sticky="nsew")
    center.grid_propagate(False)

    app.preview_canvas = tk.Canvas(
        center,
        bg=app.colors["preview"],
        highlightthickness=0,
        bd=0,
    )
    app.preview_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

    app.preview_text_label = tk.Label(
        center,
        textvariable=app.preview_text_var,
        bg=app.colors["preview"],
        fg=app.colors["text"],
        font=("Helvetica", 20, "bold"),
        justify="center",
    )
    app.preview_text_label.place(relx=0.5, rely=0.5, anchor="center")

    app.swap_button = tk.Button(
        preview_shell,
        text="Swap Cameras",
        bg=app.colors["chip"],
        fg=app.colors["text1"],
        activebackground="#2d3448",
        activeforeground=app.colors["text1"],
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        font=("Helvetica", 10, "bold"),
        padx=12,
        pady=6,
        command=app.swap_cameras,
    )
    app.swap_button.place(relx=1.0, x=-14, y=14, anchor="ne")

    return panel


def build_layout_tile(app, parent, column, mode_key, title, subtitle):
    outer = tk.Frame(
        parent,
        bg=app.colors["panel_2"],
        highlightthickness=1,
        highlightbackground=app.colors["border"],
        cursor="hand2",
    )
    outer.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))

    def handle_click(_event=None, key=mode_key):
        if app.layout_disabled and key != "single":
            return
        app.select_layout(key)

    canvas = tk.Canvas(
        outer,
        width=168,
        height=78,
        bg=app.colors["panel_2"],
        highlightthickness=0,
        bd=0,
    )
    canvas.pack(fill="x", padx=10, pady=(10, 8))
    draw_layout_icon(app, canvas, mode_key)

    title_lbl = tk.Label(
        outer,
        text=title,
        bg=app.colors["panel_2"],
        fg=app.colors["text"],
        font=("Helvetica", 11, "bold"),
        anchor="w",
        justify="left",
    )
    title_lbl.pack(fill="x", padx=10)

    sub_lbl = tk.Label(
        outer,
        text=subtitle,
        bg=app.colors["panel_2"],
        fg=app.colors["muted"],
        font=("Helvetica", 9),
        anchor="nw",
        justify="left",
        wraplength=150,
        height=2,
    )
    sub_lbl.pack(fill="x", padx=10, pady=(4, 10))

    for widget in (outer, canvas, title_lbl, sub_lbl):
        widget.bind("<Button-1>", handle_click)

    if not hasattr(app, "layout_tiles"):
        app.layout_tiles = {}
    app.layout_tiles[mode_key] = outer
    app._refresh_layout_tiles()


def draw_layout_icon(app, canvas, mode_key):
    bg = app.colors["preview"]
    primary = app.colors["accent"]
    secondary = "#8793b8"

    canvas.create_rectangle(7, 7, 161, 71, outline=app.colors["border"], fill=bg, width=1)

    if mode_key == "pip":
        canvas.create_rectangle(17, 17, 151, 61, outline="", fill=primary)
        canvas.create_rectangle(108, 24, 144, 46, outline="", fill=secondary)
    elif mode_key == "sbs":
        canvas.create_rectangle(17, 17, 81, 61, outline="", fill=primary)
        canvas.create_rectangle(87, 17, 151, 61, outline="", fill=secondary)
    elif mode_key == "stacked":
        canvas.create_rectangle(17, 17, 151, 36, outline="", fill=primary)
        canvas.create_rectangle(17, 42, 151, 61, outline="", fill=secondary)
    elif mode_key == "single":
        canvas.create_rectangle(17, 17, 151, 61, outline="", fill=primary)