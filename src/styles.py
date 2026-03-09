from tkinter import ttk


def configure_styles(root, colors):
    style = ttk.Style(root)

    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(bg=colors["bg"])

    style.configure("App.TFrame", background=colors["bg"])
    style.configure("Panel.TFrame", background=colors["panel"])
    style.configure("Inner.TFrame", background=colors["panel_2"])

    style.configure(
        "Title.TLabel",
        background=colors["bg"],
        foreground=colors["text"],
        font=("Helvetica", 24, "bold"),
    )
    style.configure(
        "Subtitle.TLabel",
        background=colors["bg"],
        foreground=colors["muted"],
        font=("Helvetica", 10),
    )
    style.configure(
        "PanelTitle.TLabel",
        background=colors["panel"],
        foreground=colors["text"],
        font=("Helvetica", 12, "bold"),
    )
    style.configure(
        "PanelText.TLabel",
        background=colors["panel"],
        foreground=colors["muted"],
        font=("Helvetica", 10),
    )
    style.configure(
        "InnerText.TLabel",
        background=colors["panel_2"],
        foreground=colors["muted"],
        font=("Helvetica", 10),
    )
    style.configure(
        "Status.TLabel",
        background=colors["bg"],
        foreground=colors["muted"],
        font=("Helvetica", 10),
    )
    style.configure(
        "CardValue.TLabel",
        background=colors["panel_2"],
        foreground=colors["text"],
        font=("Helvetica", 14, "bold"),
    )

    style.configure(
        "TCheckbutton",
        background=colors["panel"],
        foreground=colors["text"],
        font=("Helvetica", 10),
    )
    style.map(
        "TCheckbutton",
        background=[("active", colors["panel"])],
        foreground=[("active", colors["text"])],
    )

    style.configure(
        "Primary.TButton",
        background=colors["accent"],
        foreground="white",
        borderwidth=0,
        focusthickness=0,
        padding=(14, 10),
        font=("Helvetica", 10, "bold"),
    )
    style.map(
        "Primary.TButton",
        background=[
            ("active", colors["accent_hover"]),
            ("pressed", colors["accent_hover"]),
        ],
        foreground=[("active", "white")],
    )

    style.configure(
        "Secondary.TButton",
        background=colors["panel_2"],
        foreground=colors["text"],
        borderwidth=0,
        focusthickness=0,
        padding=(14, 10),
        font=("Helvetica", 10),
    )
    style.map(
        "Secondary.TButton",
        background=[
            ("active", "#262c38"),
            ("pressed", "#262c38"),
        ],
        foreground=[("active", colors["text"])],
    )

    return style