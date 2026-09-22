#!/bin/bash
set -euo pipefail
# Undo ArkOS's nice -19 Ports wrapper before starting the desktop runtime.
renice -n 0 -p "$$" >/dev/null
umask 077
ulimit -c 0
PORT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/shrike-r36s"
INSTALL="$HOME/.local/share/shrike-r36s/v26"
WALLETS="$HOME/.shrike"
message() {
    if command -v dialog >/dev/null; then dialog --timeout 15 --title 'Shrike R36S' --msgbox "$1" 16 68 || true
    else printf '%s\n' "$1"; read -r -t 15 -p 'Press Enter.' || true; fi
}
if [[ "$(uname -m)" != aarch64 ]]; then
    message 'This package needs 64-bit ARM ArkOS.'; exit 1
fi
if ! sudo -n true; then
    message 'ArkOS passwordless sudo is required to start the private runtime and open the screen/gamepad.'; exit 1
fi
for command_name in unshare chroot mount flock sha256sum tar python3; do
    if ! command -v "$command_name" >/dev/null; then
        message "ArkOS is missing a required system tool: $command_name"; exit 1
    fi
done
mkdir -p "$INSTALL" "$WALLETS"
exec 9> "$INSTALL/session.lock"
if ! flock -n 9; then message 'Shrike is already running.'; exit 1; fi
if [[ ! -e "$INSTALL/rootfs/.desktop-ready" ]]; then
    if [[ $(df -Pk "$INSTALL" | awk 'NR==2 {print $4}') -lt 1572864 ]]; then
        message 'Allow at least 1.5 GB free on the ArkOS system card for the desktop runtime.'; exit 1
    fi
    command -v dialog >/dev/null && dialog --timeout 15 --title 'Shrike R36S' --infobox 'First launch: preparing the desktop runtime. Internet is required. This may take several minutes; keep power connected.' 8 65 || true
fi
LOG="$(mktemp /dev/shm/shrike-start.XXXXXXXX)"
CONSOLE_MODE=""
restore_console() {
    if [[ -n "$CONSOLE_MODE" ]]; then
        sudo -n python3 -B "$PORT/console.py" "$CONSOLE_MODE" || true
        CONSOLE_MODE=""
    fi
}
cleanup() { restore_console; rm -f -- "$LOG"; }
trap cleanup EXIT
CONSOLE_MODE="$(sudo -n python3 -B "$PORT/console.py" enter)"
# A private mount namespace keeps runtime mounts out of the ArkOS desktop.
# The network namespace is shared: Wi-Fi and other ArkOS connections remain usable.
if ! sudo -n unshare --mount --propagation private -- /bin/bash "$PORT/runtime.sh" "$PORT" "$INSTALL" "$WALLETS" "$(id -u)" "$(id -g)" > "$LOG" 2>&1; then
    restore_console
    if command -v dialog >/dev/null; then
        dialog --timeout 15 --title 'Shrike startup/session error (temporary log)' --textbox "$LOG" 20 74 || true
    else cat "$LOG"; read -r -t 15 -p 'Press Enter.' || true; fi
fi
