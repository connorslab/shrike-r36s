#!/bin/bash
set -euo pipefail
umask 077
ulimit -c 0
PORT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/shrike-r36s"
INSTALL="$HOME/.local/share/shrike-r36s/v26"
WALLETS="$HOME/.shrike"
message() {
    if command -v dialog >/dev/null; then dialog --title 'Shrike R36S' --msgbox "$1" 16 68
    else printf '%s\n' "$1"; read -r -p 'Press Enter.' || true; fi
}
if [[ "$(uname -m)" != aarch64 ]]; then
    message 'This package needs 64-bit ARM ArkOS.'; exit 1
fi
if ! sudo -n true; then
    message 'ArkOS passwordless sudo is required to start the private runtime and open the screen/gamepad.'; exit 1
fi
for command_name in unshare chroot mount flock sha256sum tar; do
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
    command -v dialog >/dev/null && dialog --title 'Shrike R36S' --infobox 'First launch: preparing the desktop runtime. Internet is required. This may take several minutes; keep power connected.' 8 65 || true
fi
LOG="$(mktemp /dev/shm/shrike-start.XXXXXXXX)"
trap 'rm -f -- "$LOG"' EXIT
# A private mount namespace keeps runtime mounts out of the ArkOS desktop.
# The network namespace is shared: Wi-Fi and other ArkOS connections remain usable.
if ! sudo -n unshare --mount --propagation private -- /bin/bash "$PORT/runtime.sh" "$PORT" "$INSTALL" "$WALLETS" "$(id -u)" "$(id -g)" > "$LOG" 2>&1; then
    if command -v dialog >/dev/null; then
        dialog --title 'Shrike startup/session error (temporary log)' --textbox "$LOG" 20 74
    else cat "$LOG"; read -r -p 'Press Enter.' || true; fi
fi
