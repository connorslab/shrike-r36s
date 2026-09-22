# Shrike for R36S / R36X on ArkOS

Experimental handheld launcher for **Shrike v2.5.5-blake2b.26**. Uses the
upstream ARM64 desktop application and bundled Java unchanged, with a private
Ubuntu 24.04 userspace and handheld display/input adapter. Networking remains
enabled through ArkOS's Wi-Fi adapter, built-in Wi-Fi, or other working connection.

On the R36XS, normal Ports launch has reached the help page; usable wallet
interaction remains unverified. Hardware revisions may need mapping changes.

## Install

1. Connect ArkOS to the internet and confirm it works. Set its date/time correctly.
2. Extract `Shrike-R36S-ArkOS.zip` into **ports** on your EASYROMS/game card.
   Keep `Shrike.sh` beside the `shrike-r36s` folder. Both `/roms/ports` and
   `/roms2/ports` are supported. From Linux, make the launcher executable.
3. Have **at least 1.5 GB free on the ArkOS system card**. The first launch
   installs desktop dependencies in its own runtime directory and may take
   several minutes. Keep external power connected during setup.
4. Select **Ports -> Shrike**. The first screen explains the controls; press A.
5. In Shrike's server settings, connect your compatible Bitcoin Knots node or
   an Electrum server indexing that chain. This fork removed the preconfigured
   public Electrum servers; internet access alone does not select a server.

The desktop uses software rendering, so opening windows, wallet derivation and
QR scanning can be slower than on a PC. No Wi-Fi drivers or settings are changed.

## Controls

| Button | Action |
| --- | --- |
| D-pad | Move pointer; choose keys when the keyboard is open |
| A | Left click; hold while moving to drag; type selected keyboard key |
| B | Right click; Backspace when the keyboard is open |
| X | Enter |
| Y | Show/hide on-screen keyboard |
| L1 / R1 | Scroll up/down |
| L2 | Toggle full-window overview / readable 1:1 zoom |
| Hold R2 | Move pointer slowly for precision |
| Start | Escape (on release) |
| Select | Show/hide controls help |
| Select + Start | Request normal close of the active window |

Default layout is a 1280x960 virtual desktop scaled to 640x480. In zoom mode,
the viewport follows the pointer. Shrike and its dialogs keep their normal
desktop layouts. The keyboard supports all printable ASCII characters,
uppercase, punctuation, Tab, Enter, Space, and Backspace. It sends individual
keystrokes directly; it does not save typed text or use the clipboard.

To exit, close the main Shrike window normally (or Select+Start) and answer any
Shrike prompts. Closing a dialog only closes that dialog. Closing the wallet
application returns to ArkOS. Do not remove either SD card while ArkOS runs.

Button labeling varies between revisions. Configure device paths and button
actions in `shrike-r36s/app/hardware.json`. The default mappings use Linux codes:
304=click, 305=right, 307=enter, 308=keyboard, 310=scroll_up, 311=scroll_down,
312=zoom, 313=slow, 314=select, 315=start. A `buttons` override replaces the
whole button map, so include every button you want. D-pad support covers
ABS_HAT0X/Y and BTN_DPAD events. Analog sticks and external mouse/keyboard
passthrough are not implemented by this adapter.

## Wallet storage and networking

Wallets, configuration and Shrike's own logs persist in **`~/.shrike`** on the
ArkOS system card (usually `/home/ark/.shrike`). Back up that directory while
Shrike is closed, and keep your ordinary wallet seed backups. Copying the
Ports folder alone does not back up wallets. Use Shrike's wallet encryption
when saving a wallet with private keys.

The replaceable runtime lives at `~/.local/share/shrike-r36s/v26/rootfs`.
It mounts the wallet directory into its own `/home/wallet/.shrike` for the
session. The wallet runs as a non-root user, with normal network access.
The startup helper needs ArkOS passwordless sudo to prepare temporary mounts
and open the display/input devices, then permanently drops privileges before
starting the desktop and wallet.

This is an online desktop wallet on a general-purpose gaming OS. The private
userspace is for compatibility, not a security sandbox. It uses the same
kernel and network as ArkOS. It does not apply SeedSigner's offline behavior.

## Why a private runtime?

The shipped JavaFX libraries require glibc symbols as new as **2.38**. Standard
ArkOS's older libraries cannot satisfy that requirement. Ubuntu 24.04 supplies
glibc 2.39 without replacing ArkOS libraries. A local Xvfb display supplies the
desktop; it accepts no TCP connections. The adapter displays it on `/dev/fb0`
and turns the handheld's input into pointer and keyboard events.

## Troubleshooting

If first-time installation fails, check the internet connection, clock and
free system-card space, then relaunch. Setup can resume. The launcher shows a
temporary startup log on failure; it is removed when the launcher exits.

If gamepad detection fails, find its name under
`/sys/class/input/event*/device/name`, then set `input_device` in `hardware.json`
to the matching `/dev/input/eventN`. `framebuffer`, desktop dimensions and frame
rate are also configurable. Missing kernel framebuffer, mount-namespace or USB
support cannot be fixed by this package. It targets 64-bit ARM ArkOS, not Android.

USB camera and hardware-wallet support are provided by upstream Shrike and the
device's existing kernel. They have not been verified on this port. The actual
graphics, input mapping, networking, and wallet save/reopen cycle still require
testing on your device; see `TESTING.md`.

## Build and provenance

From the repository root run `python ports/r36s/build.py` using Python 3.11+ (or
run `python build.py` inside this port directory). Downloads are
locked by URL and SHA256 in `downloads.json`. Output goes to `dist/`.
The full upstream source and history are preserved in this repository; the
handheld adapters and packaging live in `ports/r36s/`.

The upstream Shrike archive is unchanged and matches its release manifest.
The upstream manifest, detached signature and release key are included for
verification. The private desktop's Ubuntu dependencies are installed from
Ubuntu's signed repositories on first launch, so their exact versions depend
on when setup runs. This is not a fully reproducible OS image.

Source and release: https://github.com/privkeyio/shrike/releases/tag/v2.5.5-blake2b.26

Ubuntu Base: https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/

Shrike retains its upstream Apache 2.0 license; Ubuntu components retain their
individual licenses. The local adapter is MIT licensed; see `LICENSE`.


## R36XS compatibility follow-up

The GO-Super gamepad layout is detected by its Linux device name. It uses
A=305, B=304, Select=704 and Start=705, rather than the adapter's original
304/305 and 314/315 assumptions. Explicit button mappings still take priority.
The matching ArkOS layout is documented in the [ArkOS key-code reference](https://github.com/christianhaitian/arkos/wiki/Key-codes-and-Global-Hotkey-config-file-locations).
The saved R36XS device report contains 704/705 and does not expose 314/315.
Other controller names retain the original mapping.

Startup error dialogs return automatically after 15 seconds because the ports
do not provide a gamepad-to-terminal keyboard translator. Display output uses direct writes by default because the R36XS driver can
hang inside framebuffer memory mapping before a fallback can run.

To update without SSH, overwrite the launcher and its matching folder on the
game card with the new ZIP contents. Keep existing wallet data and runtime
folders. These changes have host test coverage but still need device acceptance.


## Local server names (.local / mDNS)

Names such as `umbrel-knots.local` are supported. On the first launch after this
update, the private Ubuntu runtime installs `libnss-mdns` and `avahi-daemon`;
internet access is needed for that one-time upgrade. Later launches reuse them.
If ArkOS already provides an Avahi lookup socket, the runtime reuses it.
Otherwise it starts a private resolver for the session and stops it on exit.
It publishes no services and does not change ArkOS resolver settings.

The handheld and server must be on a LAN that permits multicast discovery.
Choose the SSL setting advertised by your server; a port number alone does not
specify whether TLS is enabled. The tested `umbrel-knots.local:50004` endpoint
responded using plain TCP (SSL off).

For a resolver-only test, run `runtime.sh` with its normal five arguments plus
`--check-mdns HOSTNAME PORT` inside the normal private mount namespace. This
checks lookup and TCP connectivity as the wallet user, without opening a wallet.
