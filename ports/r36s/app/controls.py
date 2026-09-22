"""Hardware-independent handheld pointer, keyboard and viewport logic."""
import math

BUTTONS = {304: "click", 305: "right", 307: "enter", 308: "keyboard",
           310: "scroll_up", 311: "scroll_down", 312: "zoom", 313: "slow",
           314: "select", 315: "start"}
DIRECTIONS = {544: (0, -1), 545: (0, 1), 546: (-1, 0), 547: (1, 0)}
ROWS = [list("1234567890-=`"), list("qwertyuiop[]"), list("asdfghjkl;'"),
        list("zxcvbnm,./\\"), ["Shift", "Space", "Backspace", "Tab", "Enter", "Hide"]]
SHIFTED = dict(zip("1234567890-=[];'.,/\\`", "!@#$%^&*()_+{}:\">< ?|~".replace(" ", "")))


class Controls:
    def __init__(self, width=1280, height=960, mapping=None):
        self.width, self.height = width, height
        self.x, self.y = width / 2, height / 2
        self.mapping = mapping or BUTTONS
        self.held = set()
        self.hat = {16: 0, 17: 0}
        self.keyboard = False
        self.shift = False
        self.row = self.col = 0
        self.zoom = False
        self.help = True
        self.exit_chord = False
        self.key_repeat = 0

    def event(self, kind, code, value):
        if kind == 0 and code == 3:
            self.held.clear()
            self.hat = {16: 0, 17: 0}
            return [("release_all", None)]
        if kind == 3 and code in self.hat:
            self.hat[code] = value
            return []
        if kind != 1:
            return []
        name = self.mapping.get(code)
        if value == 2:
            return []  # Repeats are driven by elapsed time, not the kernel.
        if value:
            self.held.add(code)
        else:
            self.held.discard(code)
        held_names = {self.mapping.get(k) for k in self.held}
        if {"select", "start"} <= held_names:
            self.exit_chord = True
            return [("close_window", None)]
        if name in ("select", "start"):
            if value:
                return []
            if self.exit_chord:
                if not ({"select", "start"} & held_names):
                    self.exit_chord = False
                return []
            if name == "select":
                self.help = not self.help
                return []
            return [("key", "Escape")]
        if self.help:
            if value and name == "click":
                self.help = False
            return []
        if name == "click":
            if self.keyboard:
                return self.activate_key() if value else []
            return [("button_down" if value else "button_up", 1)]
        if name == "right":
            if self.keyboard:
                return [("key", "BackSpace")] if value else []
            return [("button_down" if value else "button_up", 3)]
        if not value:
            return []
        if name == "keyboard":
            self.keyboard = not self.keyboard
            return [("release_all", None)]
        if name == "zoom":
            self.zoom = not self.zoom
        elif name == "enter":
            return [("key", "Return")]
        elif name == "scroll_up":
            return [("click", 4)]
        elif name == "scroll_down":
            return [("click", 5)]
        return []

    def direction(self):
        x, y = self.hat[16], self.hat[17]
        for code in self.held:
            dx, dy = DIRECTIONS.get(code, (0, 0))
            x += dx
            y += dy
        return max(-1, min(1, x)), max(-1, min(1, y))

    def tick(self, dt):
        dx, dy = self.direction()
        if self.help or not (dx or dy):
            self.key_repeat = 0
            return []
        if self.keyboard:
            self.key_repeat -= dt
            if self.key_repeat <= 0:
                self.row = (self.row + dy) % len(ROWS)
                self.col = (self.col + dx) % len(ROWS[self.row])
                self.key_repeat = 0.18
            return []
        slow = any(self.mapping.get(k) == "slow" for k in self.held)
        speed = 70 if slow else 650
        scale = min(dt, 0.1) * speed / math.hypot(dx, dy)
        self.x = max(0, min(self.width - 1, self.x + dx * scale))
        self.y = max(0, min(self.height - 1, self.y + dy * scale))
        return [("move", (int(self.x), int(self.y)))]

    def label(self, key):
        if len(key) == 1 and self.shift:
            return key.upper() if key.isalpha() else SHIFTED.get(key, key)
        return key

    def activate_key(self):
        key = ROWS[self.row][self.col]
        if key == "Shift":
            self.shift = not self.shift
        elif key == "Hide":
            self.keyboard = False
        elif key in ("Space", "Backspace", "Tab", "Enter"):
            return [("key", {"Space": "space", "Backspace": "BackSpace", "Tab": "Tab", "Enter": "Return"}[key])]
        else:
            return [("text", self.label(key))]
        return []


def viewport(state, physical_width, physical_height):
    if not state.zoom:
        return (0, 0, state.width, state.height)
    w, h = min(physical_width, state.width), min(physical_height, state.height)
    x = max(0, min(state.width - w, int(state.x) - w // 2))
    y = max(0, min(state.height - h, int(state.y) - h // 2))
    return x, y, x + w, y + h
