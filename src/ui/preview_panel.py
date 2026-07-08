import platform
import tkinter as tk
from tkinter import ttk

from .modern_widgets import RoundedButton


def build_preview_panel(app, parent):
    hand_cursor = "pointinghand" if platform.system() == "Darwin" else "hand2"
    panel = ttk.Frame(parent, style="Panel.TFrame", padding=18)
    panel.grid(row=0, column=1, sticky="nsew")
    panel.rowconfigure(2, weight=0)
    panel.rowconfigure(3, weight=1)
    panel.columnconfigure(0, weight=1)

    # ---------- Layout picker strip ----------
    top_wrap = ttk.Frame(panel, style="Panel.TFrame")
    top_wrap.grid(row=0, column=0, sticky="ew")
    top_wrap.columnconfigure(0, weight=1)

    strip_canvas = tk.Canvas(
        top_wrap,
        bg=app.colors["panel"],
        highlightthickness=0,
        bd=0,
        height=145,
    )
    strip_canvas.grid(row=0, column=0, sticky="ew", pady=(0,1))

    scrollbar_canvas = tk.Canvas(
        top_wrap,
        height=8,
        bg=app.colors["panel"],
        highlightthickness=0,
        bd=0,
    )
    scrollbar_canvas.grid(row=1, column=0, sticky="ew", pady=(0, 0))

    scrollbar_track = scrollbar_canvas.create_rectangle(
        0, 2, 0, 6,
        fill="black",
        outline="black",
    )

    scrollbar_thumb = scrollbar_canvas.create_rectangle(
        0, 1, 80, 7,
        fill="#7C8CFF",
        outline="#7C8CFF",
    )

    tiles_frame = tk.Frame(strip_canvas, bg=app.colors["panel"])
    strip_window = strip_canvas.create_window((0, 0), window=tiles_frame, anchor="nw")

    def _update_scroll_region(_event=None):
        strip_canvas.configure(scrollregion=strip_canvas.bbox("all"))

    def _resize_inner_frame(event):
        strip_canvas.itemconfigure(strip_window, height=event.height)

    def update_custom_scrollbar():
        try:
            scrollbar_canvas.update_idletasks()
            canvas_width = scrollbar_canvas.winfo_width()
            x0, x1 = strip_canvas.xview()

            if canvas_width <= 1:
                return

            track_y1 = 2
            track_y2 = 6
            scrollbar_canvas.coords(scrollbar_track, 0, track_y1, canvas_width, track_y2)

            thumb_x1 = max(0, canvas_width * x0)
            thumb_x2 = min(canvas_width, canvas_width * x1)

            min_thumb_width = 36
            if thumb_x2 - thumb_x1 < min_thumb_width:
                thumb_x2 = min(canvas_width, thumb_x1 + min_thumb_width)
                if thumb_x2 >= canvas_width:
                    thumb_x1 = max(0, canvas_width - min_thumb_width)

            scrollbar_canvas.coords(scrollbar_thumb, thumb_x1, 1, thumb_x2, 7)
        except Exception:
            pass

    def custom_scroll_to_fraction(fraction):
        strip_canvas.xview_moveto(fraction)
        update_custom_scrollbar()

    def on_custom_scrollbar_click(event):
        canvas_width = max(1, scrollbar_canvas.winfo_width())
        thumb_width = max(36, scrollbar_thumb_coords()[2] - scrollbar_thumb_coords()[0])
        target_left = event.x - (thumb_width / 2)
        fraction = target_left / canvas_width
        fraction = max(0.0, min(1.0, fraction))
        custom_scroll_to_fraction(fraction)

    def scrollbar_thumb_coords():
        coords = scrollbar_canvas.coords(scrollbar_thumb)
        if len(coords) != 4:
            return [0, 1, 36, 7]
        return coords

    def on_thumb_drag_start(event):
        scrollbar_canvas._drag_start_x = event.x
        scrollbar_canvas._drag_thumb_start = scrollbar_thumb_coords()[0]

    def on_thumb_drag(event):
        if not hasattr(scrollbar_canvas, "_drag_start_x"):
            return

        canvas_width = max(1, scrollbar_canvas.winfo_width())
        x0, x1 = strip_canvas.xview()
        visible_fraction = max(0.01, x1 - x0)

        thumb_width = max(36, visible_fraction * canvas_width)
        max_left = max(0, canvas_width - thumb_width)

        delta = event.x - scrollbar_canvas._drag_start_x
        new_left = scrollbar_canvas._drag_thumb_start + delta
        new_left = max(0, min(max_left, new_left))

        fraction = 0.0 if max_left == 0 else new_left / canvas_width
        custom_scroll_to_fraction(fraction)

    scrollbar_canvas.bind("<Button-1>", on_custom_scrollbar_click)
    scrollbar_canvas.tag_bind(scrollbar_thumb, "<ButtonPress-1>", on_thumb_drag_start)
    scrollbar_canvas.tag_bind(scrollbar_thumb, "<B1-Motion>", on_thumb_drag)

    tiles_frame.bind("<Configure>", lambda e: (_update_scroll_region(e), update_custom_scrollbar()))
    strip_canvas.bind("<Configure>", lambda e: (_resize_inner_frame(e), update_custom_scrollbar()))
    def _scroll_layout_strip(event):
        if event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1

        strip_canvas.xview_scroll(delta, "units")
        update_custom_scrollbar()
        return "break"

    def _bind_layout_mousewheel(_event=None):
        strip_canvas.bind_all("<MouseWheel>", _scroll_layout_strip)
        strip_canvas.bind_all("<Shift-MouseWheel>", _scroll_layout_strip)
        strip_canvas.bind_all("<Button-4>", _scroll_layout_strip)
        strip_canvas.bind_all("<Button-5>", _scroll_layout_strip)

    def _unbind_layout_mousewheel(_event=None):
        strip_canvas.unbind_all("<MouseWheel>")
        strip_canvas.unbind_all("<Shift-MouseWheel>")
        strip_canvas.unbind_all("<Button-4>")
        strip_canvas.unbind_all("<Button-5>")

    for scroll_widget in (strip_canvas, tiles_frame):
        scroll_widget.bind("<Enter>", _bind_layout_mousewheel)
        scroll_widget.bind("<Leave>", _unbind_layout_mousewheel)
        scroll_widget.configure(cursor=hand_cursor)

    build_layout_tile(app, tiles_frame, 0, "pip", "Picture in Picture", "One large feed with a floating inset")
    build_layout_tile(app, tiles_frame, 1, "sbs", "Side by Side", "Two camera feeds displayed next to each other")
    build_layout_tile(app, tiles_frame, 2, "stacked", "Top and Bottom", "One feed above the other in a vertical stack")
    build_layout_tile(app, tiles_frame, 3, "single", "Single", "Only the main camera is shown")
    build_layout_tile(app, tiles_frame, 4, "triple", "3 Camera Grid", "Three feeds in a 2x2 grid with top-right empty")
    build_layout_tile(app, tiles_frame, 5, "quad", "4 Camera Grid", "Four feeds arranged in a 2x2 grid")

    update_custom_scrollbar()

    # ---------- Preview ----------
    preview_header = ttk.Frame(panel, style="Panel.TFrame")
    preview_header.grid(row=2, column=0, sticky="ew", pady=(10, 10))
    preview_header.columnconfigure(0, weight=1)

    ttk.Label(
        preview_header,
        text="Preview",
        style="PanelTitle.TLabel",
    ).grid(row=0, column=0, sticky="w")

    app.swap_button = RoundedButton(
        preview_header,
        text="Swap Cameras",
        command=app.swap_cameras,
        colors=app.colors,
        width=132,
        height=36,
        radius=14,
        bg=app.colors["chip"],
        hover_bg=app.colors["chip_hover"],
        active_bg=app.colors["chip"],
        fg=app.colors["text"],
        border=app.colors["border"],
        font=("Helvetica", 10, "bold"),
    )
    app.swap_button.grid(row=0, column=1, sticky="e")

    preview_shell = tk.Frame(
        panel,
        bg=app.colors["preview"],
        highlightthickness=1,
        highlightbackground=app.colors["border"],
    )
    preview_shell.grid(row=3, column=0, sticky="nsew")
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

    return panel


def build_layout_tile(app, parent, column, mode_key, title, subtitle):
    outer = tk.Frame(
        parent,
        width=190,
        height=145,
        bg=app.colors["panel_2"],
        highlightthickness=1,
        highlightbackground=app.colors["border"],
        cursor="pointinghand" if platform.system() == "Darwin" else "hand2",
    )
    outer.grid(row=0, column=column, padx=(0 if column == 0 else 16, 0), sticky="n")
    outer.pack_propagate(False)

    def handle_click(_event=None, key=mode_key):
        if app.layout_disabled and key != "single":
            return
        app.select_layout(key)

    canvas = tk.Canvas(
        outer,
        width=168,
        height=75,
        bg=app.colors["panel_2"],
        highlightthickness=0,
        bd=0,
    )
    canvas.pack(fill="x", padx=10, pady=(10, 4))
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
        wraplength=200,
    )
    sub_lbl.pack(fill="x", padx=10, pady=(4, 8))

    for widget in (outer, canvas, title_lbl, sub_lbl):
        widget.bind("<Button-1>", handle_click)

    if not hasattr(app, "layout_tiles"):
        app.layout_tiles = {}
    app.layout_tiles[mode_key] = outer
    outer.update_idletasks()
    app._refresh_layout_tiles()


def draw_layout_icon(app, canvas, mode_key):
    bg = app.colors["preview"]
    primary = app.colors["accent"]
    secondary = "#8793b8"

    canvas_h = int(canvas.cget("height"))
    canvas_w = int(canvas.cget("width"))

    left = 17
    top = 17
    right = 151
    bottom = 61
    mid_x = (left + right) // 2
    mid_y = (top + bottom) // 2
    gap = 6

    bg_h = 64
    bg_x1 = 7
    bg_x2 = canvas_w - 7
    bg_y1 = (canvas_h - bg_h) // 2
    bg_y2 = bg_y1 + bg_h

    canvas.create_rectangle(
        bg_x1, bg_y1, bg_x2, bg_y2,
        outline=app.colors["border"],
        fill=bg,
        width=1,
    )

    if mode_key == "single":
        canvas.create_rectangle(left, top, right, bottom, outline="", fill=primary)

    elif mode_key == "pip":
        canvas.create_rectangle(left, top, right, bottom, outline="", fill=primary)
        canvas.create_rectangle(right - 42, top + 8, right - 8, top + 28, outline="", fill=secondary)

    elif mode_key == "sbs":
        canvas.create_rectangle(left, top, mid_x - gap // 2, bottom, outline="", fill=primary)
        canvas.create_rectangle(mid_x + gap // 2, top, right, bottom, outline="", fill=secondary)

    elif mode_key == "stacked":
        canvas.create_rectangle(left, top, right, mid_y - gap // 2, outline="", fill=primary)
        canvas.create_rectangle(left, mid_y + gap // 2, right, bottom, outline="", fill=secondary)

    elif mode_key == "triple":
        canvas.create_rectangle(left, top, mid_x - gap // 2, mid_y - gap // 2, outline="", fill=primary)
        canvas.create_rectangle(left, mid_y + gap // 2, mid_x - gap // 2, bottom, outline="", fill=secondary)
        canvas.create_rectangle(mid_x + gap // 2, mid_y + gap // 2, right, bottom, outline="", fill=primary)

    elif mode_key == "quad":
        canvas.create_rectangle(left, top, mid_x - gap // 2, mid_y - gap // 2, outline="", fill=primary)
        canvas.create_rectangle(mid_x + gap // 2, top, right, mid_y - gap // 2, outline="", fill=secondary)
        canvas.create_rectangle(left, mid_y + gap // 2, mid_x - gap // 2, bottom, outline="", fill=secondary)
        canvas.create_rectangle(mid_x + gap // 2, mid_y + gap // 2, right, bottom, outline="", fill=primary)