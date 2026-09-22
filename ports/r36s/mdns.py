"""Configure name lookup inside the private Shrike root filesystem only."""
from pathlib import Path
import sys

HOSTS = "hosts: files mdns4_minimal [NOTFOUND=return] dns"
AVAHI = """[server]
use-ipv4=yes
use-ipv6=no
enable-dbus=no
[publish]
disable-publishing=yes
[reflector]
enable-reflector=no
"""


def configure(root):
    root = Path(root)
    path = root / "etc/nsswitch.conf"
    lines = path.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("hosts:"):
            lines[i] = HOSTS
            found = True
    if not found:
        lines.append(HOSTS)
    path.write_text("\n".join(lines) + "\n")
    config = root / "etc/avahi/shrike-mdns.conf"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(AVAHI)


if __name__ == "__main__":
    configure(sys.argv[1])
