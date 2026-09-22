"""Keep the Linux text console from repainting over a framebuffer application."""
import array
import fcntl
import os
import sys


def main():
    fd = os.open('/dev/tty0', os.O_RDWR)
    try:
        if sys.argv[1] == 'enter':
            previous = array.array('i', [0])
            fcntl.ioctl(fd, 0x4B3B, previous)  # KDGETMODE
            fcntl.ioctl(fd, 0x4B3A, 1)  # KDSETMODE / KD_GRAPHICS
            print(previous[0])
        else:
            mode = int(sys.argv[1])
            if mode not in (0, 1):
                raise ValueError('Invalid saved console mode')
            fcntl.ioctl(fd, 0x4B3A, mode)
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
