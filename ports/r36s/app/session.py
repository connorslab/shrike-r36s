"""One desktop session. Open devices as root, then permanently drop privileges."""
import fcntl
import glob
import json
import os
from pathlib import Path
import pwd
import resource
import select
import signal
import socket
import struct
import subprocess
import tempfile
import time

from controls import BUTTONS, Controls
from framebuffer import Framebuffer


def input_path(config):
    if config.get("input_device"):
        path = config["input_device"]
        if not path.startswith("/dev/input/event"):
            raise ValueError("input_device must be a Linux event device")
        return path
    devices = []
    for filename in glob.glob("/sys/class/input/event*/device/name"):
        name = Path(filename).read_text().lower()
        if any(word in name for word in ("go2", "gamepad", "joypad", "rk3326", "retrogame")):
            devices.append("/dev/input/" + filename.split("/")[-3])
    if len(devices) != 1:
        raise RuntimeError("Set input_device in hardware.json to the handheld gamepad")
    return devices[0]


def stop_child(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def main():
    config = json.loads(Path("/opt/r36s-port/hardware.json").read_text())
    account = pwd.getpwnam("wallet")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    fb_path = config.get("framebuffer", "/dev/fb0")
    if not fb_path.startswith("/dev/fb"):
        raise ValueError("framebuffer must be a Linux fbdev device")
    fb_fd = os.open(fb_path, os.O_RDWR)
    input_fd = os.open(input_path(config), os.O_RDONLY | os.O_NONBLOCK)
    fcntl.ioctl(input_fd, 0x40044590, 1)  # EVIOCGRAB
    # No privileged code runs after this point. The open device descriptors are
    # retained only by this process; child processes have close_fds=True.
    os.setgroups([])
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ.update(HOME=account.pw_dir, USER="wallet", LOGNAME="wallet", LANG="C.UTF-8")
    os.chdir(account.pw_dir)
    screen = Framebuffer(fb_fd)
    width, height = int(config.get("desktop_width", 1280)), int(config.get("desktop_height", 960))
    if not (1024 <= width <= 1920 and 768 <= height <= 1440):
        raise ValueError("Desktop dimensions must be within 1024x768 and 1920x1440")
    mapping = {int(k): v for k, v in config.get("buttons", {}).items()} or BUTTONS
    state = Controls(width, height, mapping)
    xvfb = wm = app = None
    connection = None
    closed = False
    def request_stop(signum, frame):
        nonlocal closed
        closed = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        with tempfile.TemporaryDirectory(prefix="shrike-desktop-", dir="/run/user-wallet") as session:
            env = os.environ.copy()
            env["XAUTHORITY"] = session + "/Xauthority"
            # The rootfs has its own /tmp, so its X sockets are separate from ArkOS.
            env["DISPLAY"] = ":0"
            import secrets
            subprocess.run(["xauth", "-f", env["XAUTHORITY"], "add", ":0", ".", secrets.token_hex(16)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            xvfb = subprocess.Popen(["Xvfb", ":0", "-screen", "0", f"{width}x{height}x24", "-nolisten", "tcp",
                                     "-auth", env["XAUTHORITY"], "-noreset"], env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            from Xlib import display
            # python-xlib reads the cookie path from this process's environment.
            os.environ["XAUTHORITY"] = env["XAUTHORITY"]
            for attempt in range(100):
                if xvfb.poll() is not None:
                    raise RuntimeError("Virtual desktop failed to start")
                try:
                    connection = display.Display(env["DISPLAY"])
                    break
                except Exception:
                    time.sleep(0.1)
            if connection is None:
                raise RuntimeError("Virtual desktop startup timed out")
            if not connection.has_extension("XTEST"):
                raise RuntimeError("XTEST input extension is missing")
            wm = subprocess.Popen(["openbox", "--config-file", "/opt/r36s-port/openbox.xml"], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.3)
            env["JAVA_TOOL_OPTIONS"] = "-Xms64m -Xmx384m -XX:ActiveProcessorCount=2 -Dprism.order=sw -Dglass.gtk.uiScale=1 -Dprism.allowhidpi=false"
            app = subprocess.Popen(["/opt/Shrike/bin/Shrike", "--dir", account.pw_dir + "/.shrike", "--level", "ERROR"],
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            from desktop import Desktop
            desktop = Desktop(connection, state)
            desktop.apply([("move", (int(state.x), int(state.y)))])
            event = struct.Struct("@llHHi")
            previous = time.monotonic()
            fps = max(3, min(15, int(config.get("fps", 8))))
            next_render = previous
            while app.poll() is None and not closed:
                ready, _, _ = select.select([input_fd], [], [], 0.015)
                actions = []
                if ready:
                    data = os.read(input_fd, event.size * 64)
                    if not data or len(data) % event.size:
                        raise RuntimeError("Gamepad disconnected")
                    for _, _, kind, code, value in event.iter_unpack(data):
                        actions.extend(state.event(kind, code, value))
                now = time.monotonic()
                actions.extend(state.tick(now - previous))
                previous = now
                desktop.apply(actions)
                if now >= next_render:
                    screen.show_image(desktop.render(screen.var.xres, screen.var.yres))
                    next_render = now + 1 / fps
            desktop.apply([("release_all", None)])
            if app.poll() not in (None, 0):
                raise RuntimeError("Shrike exited with an error; see its own log in the wallet directory")
    finally:
        # Only session-owned children are stopped. Normal UI exit has already
        # let Shrike finish its wallet writes before this cleanup runs.
        for child in (app, wm, xvfb):
            stop_child(child)
        if connection is not None:
            connection.close()
        screen.cleanup()
        os.close(input_fd)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Avoid tracing wallet content or captured screen images to persistent logs.
        print("Desktop session failed: " + type(error).__name__ + ". Check hardware.json and the installed runtime.", flush=True)
        raise SystemExit(1)
