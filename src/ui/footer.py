# footer.py
from tkinter import ttk


def build_footer(app, parent):
    footer = ttk.Frame(parent, style="App.TFrame")
    footer.pack(fill="x", pady=(12, 0))

    app.footer_label = ttk.Label(
        footer,
        textvariable=app.footer_message_var,
        style="Status.TLabel",
        foreground=app.colors["muted"],   # default color here
    )
    app.footer_label.pack(anchor="w")

    return footer