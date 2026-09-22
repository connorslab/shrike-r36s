#!/bin/bash
# Runs as root inside a PRIVATE mount namespace, not as the wallet user.
set -euo pipefail
umask 077
PORT="$1"
INSTALL="$2"
WALLETS="$3"
USER_ID="$4"
GROUP_ID="$5"
ROOT="$INSTALL/rootfs"
[[ "$USER_ID" =~ ^[0-9]+$ && "$GROUP_ID" =~ ^[0-9]+$ && "$USER_ID" -ne 0 ]]
(cd "$PORT" && sha256sum -c archives.sha256)
mkdir -p "$ROOT"
if [[ ! -f "$ROOT/.base-unpacked" ]]; then
    echo 'Unpacking private Ubuntu userspace (ArkOS system files are not replaced).'
    tar --numeric-owner -xpf "$PORT/ubuntu-base-24.04.5-base-arm64.tar.gz" -C "$ROOT"
    chmod 755 "$ROOT"
    touch "$ROOT/.base-unpacked"
fi
mkdir -p "$ROOT/opt" "$ROOT/dev" "$ROOT/proc" "$ROOT/sys" "$ROOT/run" "$ROOT/tmp"
mount --bind /dev "$ROOT/dev"
mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs "$ROOT/dev/shm"
mount -t devpts -o newinstance,ptmxmode=0666,mode=0620 devpts "$ROOT/dev/pts"
mount -t proc proc "$ROOT/proc"
mount --bind /sys "$ROOT/sys"
mount -o remount,bind,ro "$ROOT/sys"
mount -t tmpfs -o mode=755,nosuid,nodev tmpfs "$ROOT/run"
mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs "$ROOT/tmp"
mkdir -p "$ROOT/tmp/.X11-unix"
chmod 1777 "$ROOT/tmp/.X11-unix"
# Follow the host resolver, including a local systemd stub on the shared network.
if [[ -L "$ROOT/etc/resolv.conf" ]]; then rm -- "$ROOT/etc/resolv.conf"; fi
cp -L /etc/resolv.conf "$ROOT/etc/resolv.conf"
cp /etc/hosts "$ROOT/etc/hosts"
# Don't start desktop daemons or services in a runtime without systemd.
printf '#!/bin/sh\nexit 101\n' > "$ROOT/usr/sbin/policy-rc.d"
chmod 755 "$ROOT/usr/sbin/policy-rc.d"
if [[ ! -f "$ROOT/.desktop-ready" ]]; then
    echo 'Installing the private desktop components from Ubuntu signed repositories.'
    chroot "$ROOT" /usr/bin/env DEBIAN_FRONTEND=noninteractive /bin/bash -c '
        set -e
        apt-get update
        dpkg --configure -a
        apt-get install -y --no-install-recommends ca-certificates xvfb xauth openbox \
            python3 python3-pil python3-numpy python3-xlib fonts-dejavu-core \
            libgtk-3-0t64 libasound2t64 libgl1 libxtst6 libxi6 libxrender1 \
            libfreetype6 libfontconfig1 libudev1 libusb-1.0-0 passwd
        apt-get clean
    '
    tar --numeric-owner -xpf "$PORT/shrike-2.5.5-26-aarch64.tar.gz" -C "$ROOT/opt"
    chown -R 0:0 "$ROOT/opt/Shrike"
    if ! chroot "$ROOT" getent group "$GROUP_ID" >/dev/null; then
        chroot "$ROOT" groupadd -g "$GROUP_ID" wallet
    fi
    if ! chroot "$ROOT" id wallet >/dev/null 2>&1; then
        chroot "$ROOT" useradd -m -u "$USER_ID" -g "$GROUP_ID" -s /bin/bash wallet
    fi
    [[ "$(chroot "$ROOT" id -u wallet)" == "$USER_ID" ]]
    touch "$ROOT/.desktop-ready"
fi
mkdir -p "$ROOT/opt/r36s-port" "$ROOT/home/wallet/.shrike" "$ROOT/run/user-wallet"
cp -r "$PORT/app/." "$ROOT/opt/r36s-port/"
chown -R 0:0 "$ROOT/opt/r36s-port"
chmod -R a+rX "$ROOT/opt/r36s-port"
chown "$USER_ID:$GROUP_ID" "$ROOT/run/user-wallet" "$ROOT/home/wallet"
mount --bind "$WALLETS" "$ROOT/home/wallet/.shrike"
echo 'Starting Shrike. The gamepad help screen will appear.'
# session.py opens the two device descriptors, then permanently becomes the
# unprivileged wallet account BEFORE launching Xvfb, Openbox, or Shrike.
chroot "$ROOT" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C.UTF-8 /usr/bin/python3 -B /opt/r36s-port/session.py
# Mounts vanish automatically when this private namespace's processes exit.
