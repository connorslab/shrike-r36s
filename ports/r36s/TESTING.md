# Shrike R36S validation — 2026-09-21

Shrike release: `v2.5.5-blake2b.26`, source commit
`7a2d0f83dd6b6d953611ea1083021fae44c3784e`.

## Performed on the Windows build host

* 30 Python tests cover button press/release, click-and-drag, event overflow,
  exit-chord ordering, keyboard navigation, all printable ASCII characters,
  shifted characters/modifier release, pointer limits and diagonal speed,
  precision movement, zoom bounds, custom mappings, virtual desktop capture
  conversion, help/keyboard rendering, and 16/32-bit framebuffer pixels.
* Both Bash scripts parse without errors using the tree-sitter Bash grammar.
* Upstream Shrike ARM64 archive SHA256 matches the upstream release manifest.
* The manifest's signature mathematically verifies with the key published in
  the same release, fingerprint `A47D99B6DB0D715D40C59A2023AE8A8EA7E24E38`.
  The README footer names a different key. This check uses the release
  key; it does not independently authenticate the publisher or establish
  revocation status. Signature verification used PGPy on the build host.
* Ubuntu Base archive SHA256 matches Canonical's published manifest.
* ELF inspection identified JavaFX's glibc 2.38 requirement, motivating the
  separate Ubuntu 24.04 userspace instead of directly launching on ArkOS.
* The wallet/JVM archive is packaged without modification. Cryptographic code
  is not rebuilt or patched by this port.

## Not yet performed

At initial release, no physical R36S/R36X, ARM Linux emulator, camera, hardware
wallet, or chain backend was connected. See the follow-up below for subsequent
R36XS runtime setup and startup checks. Full interaction, memory consumption,
performance and signing acceptance remain outstanding.
These host tests do not prove the package boots or signs correctly on a device.
The upstream Java wallet test suite was not run for this packaging-only port.

## Device acceptance checks

1. Install from Ports while connected to Wi-Fi; verify setup completes and the
   help screen appears. Reboot and check the second launch needs no setup.
2. Check pointer movement, drag, scroll, keyboard, shifted punctuation and zoom
   with a disposable wallet. Verify Select+Start allows normal close prompts.
3. Connect a compatible node/Electrum backend and verify the network/height.
4. Save an encrypted test wallet, close Shrike, reopen and confirm it reloads.
5. Compare a derived address against a trusted independent implementation.
6. Exercise the unified-signing workflow on the appropriate test network,
   verifying the transaction details, replay-protection status and signature.
7. Check wallet backups outside the runtime and graceful return to ArkOS.

## Repeat adapter tests

From this port's source directory, install `pytest`, `Pillow`, `numpy` and
`python-xlib`, then run `python -m pytest tests -q`. Hardware-independent tests
use simulated X/input/framebuffer interfaces; they do not access wallet files.

## R36XS troubleshooting follow-up

On the user's ARM64 ArkOS R36XS, the runtime files verified successfully.
The SeedSigner display/gamepad/import preflight passed, and the user confirmed
that a timed remote test displayed a usable SeedSigner UI. Camera operations
reported the expected missing-UVC-camera error. Shrike reached its controls
screen and its wallet process remained running during a timed test.

Remote tests must pause EmulationStation to prevent competing screen updates.
A diagnostic timeout is not evidence of an application crash. The launchers now
enter Linux console graphics mode for framebuffer rendering and restore the
previous mode on exit, including before displaying a session error. Normal Ports
launches subsequently failed; see the framebuffer follow-up below. No signing or funds
validation was performed.


### Framebuffer failure observed on 2026-09-22

A normal SeedSigner Ports launch failed in `mmap` with `EINVAL`, after all
application imports completed. The requested and reported framebuffer sizes
were both 1,228,800 bytes (640 x 480, 32-bit pixels, 2,560-byte stride), so
reducing the mapping to the visible extent did not resolve that failure.
The underlying reason for the difference from SSH startup is not yet known.

Both framebuffer adapters now fall back to positional framebuffer writes when
the driver rejects mapping with EINVAL, ENODEV or ENOSYS. The fallback preserves
row padding and offsets, handles partial writes, and fails on a stalled write.
Contiguous surfaces are written in one operation when possible. Other mapping
errors still propagate. Both launchers also reset the inherited ArkOS Ports
nice priority to normal; this change alone did not fix the black screen.

On the R36XS, a forced-fallback diagnostic rewrote all 1,228,800 existing display
bytes and read back identical bytes. The combined host adapter suites passed
57 tests, including partial writes and descriptor cleanup after write failure.
This confirms the fallback transport, not a successful normal Ports launch.
User-visible launch, controls, exit and wallet acceptance remain pending.
