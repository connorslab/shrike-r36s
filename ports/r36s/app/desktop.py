"""Capture the private X desktop and inject handheld pointer/keyboard events."""
import time
from PIL import Image, ImageDraw, ImageFont
from controls import ROWS, viewport


class Desktop:
    def __init__(self, connection, state):
        from Xlib import X, XK
        from Xlib.ext import xtest
        self.X, self.XK, self.xtest = X, XK, xtest
        self.connection, self.state = connection, state
        self.root = connection.screen().root
        self.buttons = set()
        self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)

    def apply(self, actions):
        X, d = self.X, self.connection
        for action, value in actions:
            if action == "move":
                self.xtest.fake_input(d, X.MotionNotify, x=value[0], y=value[1])
            elif action in ("button_down", "button_up"):
                self.xtest.fake_input(d, X.ButtonPress if action == "button_down" else X.ButtonRelease, value)
                if action == "button_down":
                    self.buttons.add(value)
                else:
                    self.buttons.discard(value)
            elif action == "click":
                self.xtest.fake_input(d, X.ButtonPress, value)
                self.xtest.fake_input(d, X.ButtonRelease, value)
            elif action in ("key", "text"):
                self.type_key(value, action == "text")
            elif action == "release_all":
                for button in self.buttons:
                    self.xtest.fake_input(d, X.ButtonRelease, button)
                self.buttons.clear()
            elif action == "close_window":
                # WM_DELETE is delivered by the window manager to the active window.
                # Shrike gets its usual close/save confirmation, never a forced kill.
                self.type_key("F4", alt=True)
        d.flush()

    def type_key(self, value, literal=False, alt=False):
        X, d = self.X, self.connection
        keysym = ord(value) if literal else self.XK.string_to_keysym(value)
        # Use the X server's actual US keymap, including shifted punctuation.
        candidates = [(code, index) for code, index in d.keysym_to_keycodes(keysym) if index in (0, 1)]
        if not candidates:
            raise RuntimeError("Key is not present in the desktop keymap")
        code, index = candidates[0]
        modifiers = []
        if index == 1:
            modifiers.append(d.keysym_to_keycode(self.XK.string_to_keysym("Shift_L")))
        if alt:
            modifiers.append(d.keysym_to_keycode(self.XK.string_to_keysym("Alt_L")))
        try:
            for modifier in modifiers:
                self.xtest.fake_input(d, X.KeyPress, modifier)
            self.xtest.fake_input(d, X.KeyPress, code)
            self.xtest.fake_input(d, X.KeyRelease, code)
        finally:
            for modifier in reversed(modifiers):
                self.xtest.fake_input(d, X.KeyRelease, modifier)

    def render(self, width, height):
        s = self.state
        raw = self.root.get_image(0, 0, s.width, s.height, self.X.ZPixmap, 0xffffffff)
        order = "BGRX" if self.connection.display.info.image_byte_order == self.X.LSBFirst else "XRGB"
        frame = Image.frombytes("RGB", (s.width, s.height), raw.data, "raw", order)
        crop = viewport(s, width, height)
        frame = frame.crop(crop).resize((width, height), Image.Resampling.BILINEAR)
        draw = ImageDraw.Draw(frame)
        x = int((s.x - crop[0]) * width / (crop[2] - crop[0]))
        y = int((s.y - crop[1]) * height / (crop[3] - crop[1]))
        draw.polygon([(x, y), (x + 3, y + 18), (x + 7, y + 12), (x + 16, y + 12)], fill="white", outline="black")
        if s.keyboard:
            top = int(height * 0.43)
            draw.rectangle((0, top - 26, width, height), fill="#101827")
            draw.text((8, top - 24), "D-pad: key   A: type   B: erase   Y: hide", font=self.font, fill="white")
            row_height = (height - top) / len(ROWS)
            for r, row in enumerate(ROWS):
                cell_width = width / len(row)
                for c, key in enumerate(row):
                    x0, y0 = int(c * cell_width), int(top + r * row_height)
                    fill = "#db9428" if (r, c) == (s.row, s.col) else "#29374c"
                    draw.rectangle((x0 + 2, y0 + 2, int(x0 + cell_width - 2), int(y0 + row_height - 2)), fill=fill)
                    label = s.label(key)
                    if label == "Backspace":
                        label = "Bksp"
                    draw.text((x0 + 5, y0 + 9), label, font=self.font, fill="white")
        if s.help:
            draw.rectangle((12, 12, width - 12, height - 12), fill="#101827", outline="#db9428", width=2)
            lines = ["SHRIKE  /  R36S", "", "D-pad: move pointer   A: left click / drag",
                     "B: right click   X: Enter   Y: keyboard", "L1 / R1: scroll up / down",
                     "L2: overview / readable zoom", "Hold R2: precise pointer movement",
                     "Start: Escape   Select: show this help", "Select + Start: close active window",
                     "", "Close Shrike normally to return to ArkOS.",
                     "A: dismiss help and start"]
            for i, text in enumerate(lines):
                draw.text((26, 25 + i * 30), text, font=self.font, fill="white")
        return frame
