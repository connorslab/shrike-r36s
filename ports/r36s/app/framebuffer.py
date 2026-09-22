"""Linux framebuffer adapter shared with the local SeedSigner R36S port."""
import ctypes as C
import errno
import glob
import json
import mmap
import os
import select
import struct
import threading

from PIL import Image


class Bitfield(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ("offset", "length", "msb_right")]


class VarInfo(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in (
        "xres", "yres", "xres_virtual", "yres_virtual", "xoffset", "yoffset",
        "bits_per_pixel", "grayscale")]
    _fields_ += [(name, Bitfield) for name in ("red", "green", "blue", "transp")]
    _fields_ += [(name, C.c_uint32) for name in (
        "nonstd", "activate", "height", "width", "accel_flags", "pixclock",
        "left_margin", "right_margin", "upper_margin", "lower_margin",
        "hsync_len", "vsync_len", "sync", "vmode", "rotate", "colorspace")]
    _fields_ += [("reserved", C.c_uint32 * 4)]


class FixInfo(C.Structure):
    _fields_ = [("id", C.c_char * 16), ("smem_start", C.c_ulong),
                ("smem_len", C.c_uint32), ("type", C.c_uint32),
                ("type_aux", C.c_uint32), ("visual", C.c_uint32),
                ("xpanstep", C.c_uint16), ("ypanstep", C.c_uint16),
                ("ywrapstep", C.c_uint16), ("line_length", C.c_uint32),
                ("mmio_start", C.c_ulong), ("mmio_len", C.c_uint32),
                ("accel", C.c_uint32), ("capabilities", C.c_uint16),
                ("reserved", C.c_uint16 * 2)]


def pack_pixels(image, bits, fields):
    import numpy as np
    if bits not in (16, 32):
        raise ValueError("Only RGB565/RGB888 framebuffers are supported")
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint32)
    packed = np.zeros(rgb.shape[:2], dtype=np.uint32)
    for channel, field in enumerate(fields[:3]):
        if field.msb_right or not 0 < field.length <= 8 or field.offset + field.length > bits:
            raise ValueError("Unsupported framebuffer channel layout")
        packed |= (rgb[:, :, channel] >> (8 - field.length)) << field.offset
    alpha = fields[3]
    if alpha.length:
        packed |= ((1 << alpha.length) - 1) << alpha.offset
    return packed.astype("<u2" if bits == 16 else "<u4").tobytes()


class Framebuffer:
    width, height = 320, 240

    def __init__(self, fd):
        import fcntl
        self.fd = fd
        try:
            self.var, self.fix = VarInfo(), FixInfo()
            fcntl.ioctl(self.fd, 0x4600, self.var)  # FBIOGET_VSCREENINFO
            fcntl.ioctl(self.fd, 0x4602, self.fix)  # FBIOGET_FSCREENINFO
            v, f = self.var, self.fix
            if f.type != 0 or f.visual != 2 or v.grayscale or v.bits_per_pixel not in (16, 32):
                raise RuntimeError("R36S requires a packed true-color 16/32-bit framebuffer")
            self.row_bytes = v.xres * (v.bits_per_pixel // 8)
            self.offset = v.yoffset * f.line_length + v.xoffset * (v.bits_per_pixel // 8)
            if (not v.xres or not v.yres or self.row_bytes > f.line_length or
                    self.offset + (v.yres - 1) * f.line_length + self.row_bytes > f.smem_len):
                raise RuntimeError("Invalid framebuffer bounds")
            # Map only the surface we use, excluding unused framebuffer memory.
            mapped_length = self.offset + (v.yres - 1) * f.line_length + self.row_bytes
            self.buffer = None
            backend = os.environ.get("R36S_FB_BACKEND", "write")
            if backend not in ("write", "mmap"):
                raise ValueError("R36S_FB_BACKEND must be write or mmap")
            # The R36XS driver can block inside mmap indefinitely, so waiting
            # for an exception before falling back is insufficient. Prefer writes.
            if backend == "mmap":
                try:
                    self.buffer = mmap.mmap(self.fd, mapped_length, access=mmap.ACCESS_WRITE)
                except OSError as exc:
                    if exc.errno not in (errno.EINVAL, errno.ENODEV, errno.ENOSYS):
                        raise
        except BaseException:
            os.close(self.fd)
            raise

    def show_image(self, image, x_start=0, y_start=0):
        v = self.var
        scale = min(v.xres / image.width, v.yres / image.height)
        size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        screen = Image.new("RGB", (v.xres, v.yres))
        screen.paste(image.convert("RGB").resize(size, Image.Resampling.NEAREST),
                     ((v.xres - size[0]) // 2, (v.yres - size[1]) // 2))
        raw = pack_pixels(screen, v.bits_per_pixel, [v.red, v.green, v.blue, v.transp])
        if self.fix.line_length == self.row_bytes:
            self._write_pixels(self.offset, raw)
        else:
            for row in range(v.yres):
                start = self.offset + row * self.fix.line_length
                self._write_pixels(start, raw[row * self.row_bytes:(row + 1) * self.row_bytes])

    def _write_pixels(self, offset, data):
        if self.buffer is not None:
            self.buffer[offset:offset + len(data)] = data
            return
        remaining = memoryview(data)
        while remaining:
            count = os.pwrite(self.fd, remaining, offset)
            if count <= 0:
                raise OSError(errno.EIO, "Framebuffer write made no progress")
            offset += count
            remaining = remaining[count:]

    def cleanup(self):
        try:
            self.show_image(Image.new("RGB", (320, 240)))
        finally:
            try:
                if self.buffer is not None:
                    self.buffer.close()
            finally:
                os.close(self.fd)
