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
    style.configure("Card.TFrame", background=colors["panel_2"])
    style.configure("Chip.TFrame", background=colors["chip"])

    style.configure(
        "Title.TLabel",
        background=colors["bg"],
        foreground=colors["text"],
        font=("Helvetica", 28, "bold"),
    )

    style.configure(
        "Subtitle.TLabel",
        background=colors["bg"],
        foreground=colors["muted"],
        font=("Helvetica", 11),
    )

    style.configure(
        "HeaderMeta.TLabel",
        background=colors["bg"],
        foreground=colors["muted_2"],
        font=("Helvetica", 10),
    )

    style.configure(
        "PanelTitle.TLabel",
        background=colors["panel"],
        foreground=colors["text"],
        font=("Helvetica", 13, "bold"),
    )

    style.configure(
        "PanelText.TLabel",
        background=colors["panel"],
        foreground=colors["muted"],
        font=("Helvetica", 10),
    )

    style.configure(
        "InnerTitle.TLabel",
        background=colors["panel_2"],
        foreground=colors["text"],
        font=("Helvetica", 11, "bold"),
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
        font=("Helvetica", 13, "bold"),
    )

    style.configure(
        "TCheckbutton",
        background=colors["panel"],
        foreground=colors["text"],
        font=("Helvetica", 10),
        focuscolor=colors["panel"],
    )

    style.configure(
        "Panel.TCheckbutton",
        background=colors["panel"],
        foreground=colors["text"],
        font=("Helvetica", 10),
        focuscolor=colors["panel"],
    )

    style.map(
        "TCheckbutton",
        background=[
            ("active", colors["panel"]),
            ("pressed", colors["panel"]),
        ],
        foreground=[
            ("active", colors["text"]),
            ("pressed", colors["text"]),
        ],
    )

    style.map(
        "Panel.TCheckbutton",
        background=[
            ("active", colors["panel"]),
            ("pressed", colors["panel"]),
        ],
        foreground=[
            ("active", colors["text"]),
            ("pressed", colors["text"]),
        ],
    )

    style.configure(
        "Primary.TButton",
        background=colors["accent"],
        foreground="white",
        borderwidth=0,
        focusthickness=0,
        focuscolor=colors["accent"],
        padding=(16, 11),
        font=("Helvetica", 10, "bold"),
    )

    style.map(
        "Primary.TButton",
        background=[
            ("active", colors["accent_hover"]),
            ("pressed", colors["accent_hover"]),
            ("disabled", colors["border"]),
        ],
        foreground=[
            ("active", "white"),
            ("pressed", "white"),
            ("disabled", colors["muted"]),
        ],
    )

    style.configure(
        "Secondary.TButton",
        background=colors["panel_2"],
        foreground=colors["text"],
        borderwidth=0,
        focusthickness=0,
        focuscolor=colors["panel_2"],
        padding=(16, 11),
        font=("Helvetica", 10, "bold"),
    )

    style.map(
        "Secondary.TButton",
        background=[
            ("active", colors["panel_3"]),
            ("pressed", colors["panel_3"]),
            ("disabled", colors["border_soft"]),
        ],
        foreground=[
            ("active", colors["text"]),
            ("pressed", colors["text"]),
            ("disabled", colors["muted"]),
        ],
    )

    style.configure(
        "Danger.TButton",
        background="#2A1620",
        foreground="#FCA5A5",
        borderwidth=0,
        focusthickness=0,
        focuscolor="#2A1620",
        padding=(16, 11),
        font=("Helvetica", 10, "bold"),
    )

    style.map(
        "Danger.TButton",
        background=[
            ("active", "#3A1D2A"),
            ("pressed", "#3A1D2A"),
        ],
        foreground=[
            ("active", "#FCA5A5"),
            ("pressed", "#FCA5A5"),
        ],
    )

    return style
