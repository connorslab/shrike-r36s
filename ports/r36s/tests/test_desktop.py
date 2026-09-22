import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image, ImageFont
from Xlib import X, XK

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from controls import Controls
from desktop import Desktop
from framebuffer import pack_pixels, Bitfield, Framebuffer


class FakeConnection:
    def __init__(self):
        self.calls = []
    def keysym_to_keycodes(self, sym):
        return [(38, 1 if sym == ord("A") else 0)]
    def keysym_to_keycode(self, sym):
        return 50 if sym == XK.string_to_keysym("Shift_L") else 64
    def flush(self):
        pass


def desktop():
    view = Desktop.__new__(Desktop)
    view.X, view.XK = X, XK
    view.connection = FakeConnection()
    view.xtest = SimpleNamespace(fake_input=lambda d, *args, **kwargs: d.calls.append((args, kwargs)))
    view.buttons = set()
    return view


def test_uppercase_keys_release_shift():
    view = desktop()
    view.type_key("A", literal=True)
    assert [call[0] for call in view.connection.calls] == [(X.KeyPress, 50), (X.KeyPress, 38), (X.KeyRelease, 38), (X.KeyRelease, 50)]


def test_close_uses_window_manager_not_process_kill():
    view = desktop()
    view.apply([("close_window", None)])
    assert view.connection.calls[0][0] == (X.KeyPress, 64)
    assert view.connection.calls[-1][0] == (X.KeyRelease, 64)


def test_release_all_clears_drag_buttons():
    view = desktop()
    view.apply([("button_down", 1), ("button_down", 3), ("release_all", None)])
    assert not view.buttons
    assert (X.ButtonRelease, 1) in [call[0] for call in view.connection.calls]


@pytest.mark.parametrize("help,keyboard,zoom", [(True, False, False), (False, True, False), (False, False, True)])
def test_frame_capture_and_overlay_render(help, keyboard, zoom):
    view = desktop()
    view.state = Controls()
    view.state.help, view.state.keyboard, view.state.zoom = help, keyboard, zoom
    view.font = ImageFont.load_default()
    view.connection.display = SimpleNamespace(info=SimpleNamespace(image_byte_order=X.LSBFirst))
    view.root = SimpleNamespace(get_image=lambda *args: SimpleNamespace(data=bytes((30, 20, 10, 0)) * (1280 * 960)))
    image = view.render(640, 480)
    assert image.size == (640, 480)
    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == (10, 20, 30)


@pytest.mark.parametrize("color,expected", [("red", b"\x00\xf8"), ("blue", b"\x1f\x00"), ("white", b"\xff\xff")])
def test_rgb565(color, expected):
    fields = [Bitfield(11, 5, 0), Bitfield(5, 6, 0), Bitfield(0, 5, 0), Bitfield()]
    assert pack_pixels(Image.new("RGB", (1, 1), color), 16, fields) == expected


def test_rgb8888():
    fields = [Bitfield(16, 8, 0), Bitfield(8, 8, 0), Bitfield(0, 8, 0), Bitfield(24, 8, 0)]
    assert pack_pixels(Image.new("RGB", (1, 1), (1, 2, 3)), 32, fields) == b"\x03\x02\x01\xff"
