# Shrike for R36S / R36X — ArkOS port

An experimental handheld package for **[privkeyio/shrike](https://github.com/privkeyio/shrike)**, the Sparrow fork supporting BLAKE2b proof of work and unified opt-in signatures. This repository preserves its upstream source and history, adding the compatibility adapter in `ports/r36s/`.

**Status:** experimental; remote startup has reached the controls screen on an R36XS, while normal Ports launch and wallet acceptance remain outstanding. Begin with a disposable test wallet, not real funds.

## Install

Download the ZIP and checksum from [Releases](https://github.com/connorslab/shrike-r36s/releases). Extract into **ports** on the EASYROMS/game card, keeping `Shrike.sh` beside `shrike-r36s/`. Connect ArkOS to the internet, then launch **Ports → Shrike**.

First launch prepares a separate Linux runtime and installs desktop dependencies. Allow several minutes and keep external power connected. ArkOS libraries are not replaced. Later launches reuse the runtime.

## System requirements

| Requirement | Details |
| --- | --- |
| Device | ARM64 R36S or compatible R36X; revisions still require testing |
| OS | 64-bit ArkOS, passwordless sudo, framebuffer/input access, chroot and mount namespaces |
| Storage | At least 1.5 GB free on the system card, plus room for wallets and the ZIP |
| Network | Working internet via external Wi-Fi, built-in Wi-Fi or another ArkOS connection |
| Backend | Compatible Bitcoin Knots node, or an Electrum server indexing that chain |
| Screen | 16/32-bit true-color framebuffer; designed for 640×480 |

Shrike removed its preconfigured public Electrum servers. Internet access alone does not select a backend; configure yours in server settings. Keep the device clock correct.

## Compatibility changes

- A separate Ubuntu 24.04 userspace supplies glibc symbols as new as 2.38 required by Shrike's JavaFX build.
- A private virtual desktop uses software rendering and framebuffer presentation.
- D-pad mouse controls provide clicking, dragging, scrolling, precision movement, readable zoom and an ASCII keyboard.
- Java's heap is limited to 384 MB for the handheld memory budget.
- The helper opens hardware devices, then permanently drops privileges before starting the desktop and wallet.
- Internet access and persistent wallet storage remain enabled.

The upstream ARM64 wallet/JVM archive is unchanged. No signing algorithms, proof-of-work rules, replay-protection logic or wallet formats are modified. The separate userspace is a compatibility layer, not a security sandbox.

## Controls

| Control | Action |
| --- | --- |
| D-pad | Move pointer; select keyboard keys |
| A / B | Left click or drag / right click |
| X / Y | Enter / show or hide keyboard |
| L1 / R1 | Scroll up / down |
| L2 / hold R2 | Readable zoom / precision movement |
| Start / Select | Escape / help |
| Select + Start | Request normal close of the active window |

With the keyboard open, A types and B erases. Close the main Shrike window normally to return to ArkOS; normal confirmation prompts remain available. See [full controls and mapping](ports/r36s/README.md).

## Wallets and testing

Wallets, configuration and Shrike logs persist in **`~/.shrike`**, usually `/home/ark/.shrike`. The runtime is separate at `~/.local/share/shrike-r36s/v26/rootfs`. Back up wallets while Shrike is closed; copying Ports alone is not a wallet backup. Use wallet encryption for saved private keys.

30 adapter tests passed. Archive hashes, launcher syntax and native-library requirements were checked. A subsequent R36XS session completed runtime setup and reached the controls overlay with the wallet process running. Chain backend, camera, hardware wallet and signing checks remain outstanding. The upstream Java suite was not rerun for this packaging-only port. See [validation](ports/r36s/TESTING.md).

Performance will be lower than a PC. Desktop dependencies come from Ubuntu's signed repositories at first setup, so this is not a fully reproducible OS image.

## Source and build

- Upstream: [`v2.5.5-blake2b.26`](https://github.com/privkeyio/shrike/releases/tag/v2.5.5-blake2b.26), commit [`7a2d0f8`](https://github.com/privkeyio/shrike/commit/7a2d0f83dd6b6d953611ea1083021fae44c3784e).
- Handheld additions: `ports/r36s/`; upstream wallet code is unchanged.
- Build with Python 3.11+: `python ports/r36s/build.py`. Output: `ports/r36s/dist/`.
- [Detailed guide](ports/r36s/README.md), [changelog](CHANGELOG-R36S.md), [original upstream README](docs/UPSTREAM_README.md).
- Release ZIPs record the baseline in `UPSTREAM.txt` and the packaging commit in `PORT_SOURCE.txt`.

Upstream: Apache 2.0 [LICENSE](LICENSE). Adapter: MIT [LICENSE](ports/r36s/LICENSE). Ubuntu components retain their respective licenses.
