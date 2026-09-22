"""Assemble the ArkOS ZIP from pinned upstream archives and local adapters."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
OUT = ROOT / "dist"


def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def fetch(item):
    target = CACHE / item["name"]
    if target.exists() and sha256(target) == item["sha256"]:
        return target
    partial = CACHE / (item["name"] + ".partial")
    print("Downloading", item["name"], flush=True)
    with urllib.request.urlopen(item["url"], timeout=60) as source, partial.open("wb") as dest:
        shutil.copyfileobj(source, dest)
    if sha256(partial) != item["sha256"]:
        raise RuntimeError("Download checksum mismatch: " + item["name"])
    partial.replace(target)
    return target


def main():
    CACHE.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    lock = json.loads((ROOT / "downloads.json").read_text())
    inputs = [(item, fetch(item)) for item in lock]
    release = OUT / "Shrike-R36S-ArkOS.zip"
    with zipfile.ZipFile(release, "w", compression=zipfile.ZIP_STORED) as z:
        for item, path in inputs:
            z.write(path, "shrike-r36s/" + item["name"])
        files = [ROOT / name for name in ("Shrike.sh", "runtime.sh", "mdns.py", "console.py", "README.md", "TESTING.md", "downloads.json", "LICENSE", "UPSTREAM-LICENSE", "build.py")]
        files += sorted((ROOT / "app").glob("*"))
        files += sorted((ROOT / "tests").glob("test_*.py"))
        for path in files:
            if not path.is_file():
                continue
            name = path.relative_to(ROOT).as_posix()
            target = name if name in ("Shrike.sh", "README.md", "TESTING.md") else "shrike-r36s/" + name
            info = zipfile.ZipInfo(target, (2026, 9, 21, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if path.suffix == ".sh" else 0o100644) << 16
            z.writestr(info, path.read_text(encoding="utf-8").replace("\r\n", "\n").encode())
            if name in ("README.md", "TESTING.md"):
                z.writestr("shrike-r36s/" + name, path.read_text(encoding="utf-8").encode())
        checks = "".join(f"{item['sha256']}  {item['name']}\n" for item, path in inputs)
        z.writestr("shrike-r36s/archives.sha256", checks)
        z.writestr("shrike-r36s/UPSTREAM.txt", "https://github.com/privkeyio/shrike\n7a2d0f83dd6b6d953611ea1083021fae44c3784e\nv2.5.5-blake2b.26\n")
        try:
            revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
        except (OSError, subprocess.CalledProcessError):
            revision = "standalone build; source revision unavailable"
        z.writestr("shrike-r36s/PORT_SOURCE.txt", revision + "\n")
    (OUT / (release.name + ".sha256")).write_text(sha256(release) + "  " + release.name + "\n")
    print(release, flush=True)


if __name__ == "__main__":
    main()
