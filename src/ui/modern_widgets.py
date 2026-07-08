import platform
import tkinter as tk


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        parent,
        text,
        command=None,
        colors=None,
        width=130,
        height=42,
        radius=14,
        bg=None,
        fg=None,
        hover_bg=None,
        active_bg=None,
        border=None,
        font=("Helvetica", 10, "bold"),
        anchor="center",
        padx=14,
    ):
        self.colors = colors or {}
        self.command = command
        self.text = text
        self.radius = radius
        self.normal_bg = bg or self.colors.get("panel_2", "#182235")
        self.hover_bg = hover_bg or self.colors.get("panel_3", "#202B3F")
        self.active_bg = active_bg or self.colors.get("accent", "#6D7DFF")
        self.normal_fg = fg or self.colors.get("text", "#F8FAFC")
        self.border = border or self.colors.get("border", "#263244")
        self.font = font
        self.anchor = anchor
        self.padx = padx
        self.is_selected = False
        self.is_disabled = False

        canvas_bg = self.colors.get("panel", "#111827")

        try:
            canvas_bg = parent.cget("bg")
        except Exception:
            pass

        super().__init__(
            parent,
            width=width,
            height=height,
            bg=canvas_bg,
            highlightthickness=0,
            bd=0,
            cursor="pointinghand" if platform.system() == "Darwin" else "hand2",
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda _event: self.redraw())

        self.redraw()

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, splinesteps=16, **kwargs)

    def redraw(self, fill=None):
        self.delete("all")

        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())

        if fill is None:
            fill = self.active_bg if self.is_selected else self.normal_bg

        outline = self.colors.get("accent_hover", "#8491FF") if self.is_selected else self.border
        text_fill = "white" if self.is_selected else self.normal_fg

        self._rounded_rect(
            1,
            1,
            width - 2,
            height - 2,
            self.radius,
            fill=fill,
            outline=outline,
            width=1,
        )

        if self.anchor == "w":
            x = self.padx
            anchor = "w"
        else:
            x = width / 2
            anchor = "center"

        self.create_text(
            x,
            height / 2,
            text=self.text,
            fill=text_fill,
            font=self.font,
            anchor=anchor,
        )

    def set_text(self, text):
        self.text = text
        self.redraw()

    def set_selected(self, selected):
        self.is_selected = selected
        self.redraw()

    def set_disabled(self, disabled):
        self.is_disabled = disabled
        self.configure(
            cursor="arrow" if disabled else ("pointinghand" if platform.system() == "Darwin" else "hand2")
        )
        self.redraw(fill=self.colors.get("disabled_tile", "#0F172A") if disabled else None)

    def _on_enter(self, _event=None):
        if not self.is_disabled and not self.is_selected:
            self.redraw(fill=self.hover_bg)

    def _on_leave(self, _event=None):
        self.redraw()

    def _on_press(self, _event=None):
        if not self.is_disabled:
            self.redraw(fill=self.colors.get("chip_hover", self.hover_bg))

    def _on_release(self, _event=None):
        if self.is_disabled:
            return

        self.redraw()
        if self.command:
            self.command()

class RoundedToast(tk.Canvas):
    def __init__(
        self,
        parent,
        title,
        message,
        colors,
        bg,
        border,
        accent,
        width=340,
        height=86,
        radius=18,
    ):
        self.colors = colors
        self.title = title
        self.message = message
        self.card_bg = bg
        self.border = border
        self.accent = accent
        self.radius = radius

        super().__init__(
            parent,
            width=width,
            height=height,
            bg=colors["bg"],
            highlightthickness=0,
            bd=0,
        )

        self.bind("<Configure>", lambda _event: self.redraw())
        self.redraw()

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def redraw(self):
        self.delete("all")

        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())

        self._rounded_rect(
            1,
            1,
            width - 2,
            height - 2,
            self.radius,
            fill=self.card_bg,
            outline=self.border,
            width=1,
        )

        self.create_oval(
            16,
            18,
            26,
            28,
            fill=self.accent,
            outline=self.accent,
        )

        self.create_text(
            38,
            18,
            text=self.title,
            fill=self.accent,
            font=("Helvetica", 10, "bold"),
            anchor="nw",
        )

        self.create_text(
            16,
            42,
            text=self.message,
            fill=self.colors["text"],
            font=("Helvetica", 10),
            anchor="nw",
            width=300,
        )