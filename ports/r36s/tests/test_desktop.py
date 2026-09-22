import errno
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


def test_framebuffer_maps_only_visible_extent(monkeypatch):
    """A driver can advertise more VRAM than its current surface can mmap."""
    import sys
    from types import SimpleNamespace
    import framebuffer as adapter
    def ioctl(fd, command, info):
        if command == 0x4600:
            info.xres, info.yres = 2, 2
            info.xoffset, info.yoffset = 1, 1
            info.bits_per_pixel = 32
        else:
            info.type, info.visual = 0, 2
            info.line_length, info.smem_len = 16, 4096
    def map_surface(fd, length, access):
        if length > 44:
            raise OSError(22, "Driver cannot map the reserved VRAM")
        return bytearray(length)
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(ioctl=ioctl))
    monkeypatch.setattr(adapter.os, "open", lambda *args: 123)
    monkeypatch.setattr(adapter.os, "close", lambda fd: None)
    monkeypatch.setattr(adapter.mmap, "mmap", map_surface)
    screen = adapter.Framebuffer(123)
    assert screen.offset == 20
    assert len(screen.buffer) == 44


@pytest.mark.parametrize("mapping_errno", [errno.EINVAL, errno.ENODEV, errno.ENOSYS])
def test_framebuffer_write_fallback_preserves_padding(monkeypatch, mapping_errno):
    import sys
    from types import SimpleNamespace
    import framebuffer as adapter
    from PIL import Image
    def ioctl(fd, command, info):
        if command == 0x4600:
            info.xres, info.yres = 2, 2
            info.xoffset, info.yoffset = 1, 1
            info.bits_per_pixel = 32
            info.red, info.green, info.blue = adapter.Bitfield(16, 8, 0), adapter.Bitfield(8, 8, 0), adapter.Bitfield(0, 8, 0)
        else:
            info.type, info.visual = 0, 2
            info.line_length, info.smem_len = 16, 64
    def no_mapping(*args, **kwargs):
        raise OSError(mapping_errno, "Mapping unsupported")
    storage = bytearray([99] * 64)
    def partial_write(fd, data, offset):
        count = min(3, len(data))
        storage[offset:offset + count] = data[:count]
        return count
    closed = []
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(ioctl=ioctl))
    monkeypatch.setattr(adapter.os, "open", lambda *args: 123)
    monkeypatch.setattr(adapter.os, "close", closed.append)
    monkeypatch.setattr(adapter.os, "pwrite", partial_write, raising=False)
    monkeypatch.setattr(adapter.mmap, "mmap", no_mapping)
    screen = adapter.Framebuffer(123)
    assert screen.buffer is None
    screen.show_image(Image.new("RGB", (2, 2), "red"))
    assert storage[20:28] == storage[36:44] == b"\x00\x00\xff\x00" * 2
    assert storage[:20] == bytes([99] * 20)
    assert storage[28:36] == bytes([99] * 8)
    monkeypatch.setattr(adapter.os, "pwrite", lambda *args: 0)
    with pytest.raises(OSError, match="no progress"):
        screen.cleanup()
    assert closed == [123]
