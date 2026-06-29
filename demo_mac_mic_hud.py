#!/usr/bin/env python3
"""Standalone visual demo for a macOS-inspired voice HUD."""

from __future__ import annotations

import math
import tkinter as tk


WIDTH = 360
HEIGHT = 156
TRANSPARENT = "#ff00ff"


class MacMicHudDemo:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Voice HUD Demo")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT)
        self.root.geometry(f"{WIDTH}x{HEIGHT}+760+420")

        self.canvas = tk.Canvas(
            self.root,
            width=WIDTH,
            height=HEIGHT,
            highlightthickness=0,
            bd=0,
            bg=TRANSPARENT,
        )
        self.canvas.pack(fill="both", expand=True)

        self.tick = 0
        self.mode_index = 0
        self.modes = [
            ("listen", "Dang nghe", "Noi tieng Viet..."),
            ("text", "Da nhan", "Hay toi uu mic nay thong minh hon"),
            ("paste", "Dang dan", "Tra chu ve dung khung chat"),
        ]

        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.root.bind("<Escape>", lambda _event: self.root.destroy())
        self.root.bind("<space>", self.next_mode)
        self.root.bind("<Button-1>", self.next_mode)

        self.drag_start: tuple[int, int, int, int] | None = None
        self.animate()

    def start_drag(self, event: tk.Event) -> None:
        self.drag_start = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

    def drag(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        start_x, start_y, win_x, win_y = self.drag_start
        self.root.geometry(f"+{win_x + event.x_root - start_x}+{win_y + event.y_root - start_y}")

    def next_mode(self, _event: tk.Event | None = None) -> None:
        self.mode_index = (self.mode_index + 1) % len(self.modes)
        self.draw()

    def rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: object) -> None:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.canvas.create_polygon(points, smooth=True, **kwargs)

    def draw(self) -> None:
        self.canvas.delete("all")
        state, title, subtitle = self.modes[self.mode_index]
        pulse = (math.sin(self.tick / 8) + 1) / 2

        self.rounded_rect(18, 24, WIDTH - 18, HEIGHT - 18, 28, fill="#030712", outline="")
        self.rounded_rect(21, 20, WIDTH - 21, HEIGHT - 24, 26, fill="#10131a", outline="#2dd4bf", width=1)
        self.rounded_rect(28, 28, WIDTH - 28, HEIGHT - 32, 22, fill="#171a22", outline="#2a303b", width=1)

        mic_x = 84
        mic_y = 78
        for i in range(4):
            radius = 30 + i * 9 + int(pulse * 4)
            color = "#164e63" if i % 2 else "#0f766e"
            self.canvas.create_oval(
                mic_x - radius,
                mic_y - radius,
                mic_x + radius,
                mic_y + radius,
                outline=color,
                width=1,
            )

        self.canvas.create_oval(mic_x - 32, mic_y - 32, mic_x + 32, mic_y + 32, fill="#0f172a", outline="#67e8f9", width=2)
        self.canvas.create_oval(mic_x - 9, mic_y - 24, mic_x + 9, mic_y - 4, fill="#f8fafc", outline="")
        self.canvas.create_rectangle(mic_x - 9, mic_y - 15, mic_x + 9, mic_y + 4, fill="#f8fafc", outline="")
        self.canvas.create_arc(mic_x - 22, mic_y - 4, mic_x + 22, mic_y + 28, start=200, extent=140, style="arc", outline="#f8fafc", width=4)
        self.canvas.create_line(mic_x, mic_y + 24, mic_x, mic_y + 34, fill="#f8fafc", width=4, capstyle="round")
        self.canvas.create_line(mic_x - 10, mic_y + 34, mic_x + 10, mic_y + 34, fill="#f8fafc", width=4, capstyle="round")

        if state == "listen":
            for i in range(11):
                height = 10 + int((math.sin(self.tick / 3 + i * 0.8) + 1) * 16)
                x = 154 + i * 13
                self.canvas.create_line(x, 88 - height // 2, x, 88 + height // 2, fill="#5eead4", width=5, capstyle="round")
        elif state == "text":
            self.canvas.create_line(158, 86, 178, 106, fill="#86efac", width=6, capstyle="round")
            self.canvas.create_line(178, 106, 228, 58, fill="#86efac", width=6, capstyle="round")
        else:
            for i in range(8):
                angle = self.tick / 7 + i * math.tau / 8
                x = 205 + math.cos(angle) * 46
                y = 88 + math.sin(angle) * 18
                self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#c4b5fd", outline="")

        self.canvas.create_text(148, 50, anchor="w", text=title, fill="#f8fafc", font=("Segoe UI", 15, "bold"))
        self.canvas.create_text(148, 122, anchor="w", text=subtitle, fill="#cbd5e1", font=("Segoe UI", 10), width=188)
        self.canvas.create_text(WIDTH - 32, HEIGHT - 36, anchor="e", text="click/space", fill="#64748b", font=("Segoe UI", 8))

    def animate(self) -> None:
        self.tick += 1
        self.draw()
        self.root.after(45, self.animate)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    MacMicHudDemo().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
