from tkinter import ttk


def build_header(parent):
    header = ttk.Frame(parent, style="App.TFrame")
    header.pack(fill="x")

    ttk.Label(header, text="CamComposite", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="A cleaner cross-platform camera compositor for Windows and macOS.",
        style="Subtitle.TLabel",
    ).pack(anchor="w", pady=(4, 0))

    return header