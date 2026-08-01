# NovaOS Architecture

This document describes the high-level architecture of NovaOS, the components
involved at boot time, and how the build pipeline produces the installable ISO.

## 1. Distribution choice and rationale

NovaOS is built on **Arch Linux** and ships **KDE Plasma 6** as its desktop
environment.  This combination was chosen after evaluating Debian, Fedora,
openSUSE, NixOS and Linux Mint Debian Edition against the NovaOS requirements.

Arch Linux was selected because its rolling-release model means the system
ships with the newest **linux** kernel, the newest **Mesa** stack (critical for
AMD and Intel GPUs), the newest **Nvidia** driver, and the newest **PipeWire**
audio stack - all of which materially affect hardware compatibility on
2026-era machines.  Arch's `archiso` tool is also the most CI-friendly ISO
builder in the Linux ecosystem: it runs entirely inside a Docker container, is
well-documented, and is the same tool the Arch project itself uses to produce
the official Arch install media.

KDE Plasma 6 was chosen as the desktop because it natively supports Wayland,
ships a first-class blur/glass effect through KWin, has a mature theme engine
(Kvantum + Plasma Look-and-Feel packages), supports animated video wallpapers
through the `smart-video-wallpaper-reborn` plugin, and integrates cleanly with
SDDM for a seamless boot-to-desktop transition.  Critically, it is neither
LXQt nor XFCE - both of which were explicitly excluded from consideration
because they lack the modern compositor features NovaOS requires.

## 2. The three UI layers

NovaOS defines the user experience as three distinct visual layers, each with
its own theme component:

### Layer 1 - Boot splash and greeting

The first thing the user sees after the firmware hands control to the OS is
the **KSplash** animation.  This is implemented as a QML file at
`/usr/share/plasma/look-and-feel/com.novaos.desktop/contents/splash/Splash.qml`.
It renders an animated blue nebula gradient, floating particles, the NovaOS
logo with a glowing drop-shadow, and the text "Hello. Just a moment..." with
a soft pulsing animation.  A thin progress bar at the bottom reflects the
actual boot progress reported by KSplashQML.

### Layer 2 - Login (SDDM)

Once the boot splash hands off to the display manager, SDDM loads the NovaOS
theme at `/usr/share/sddm/themes/novaos/`.  The theme is a single QML file
(`Main.qml`) that:

1. Plays an animated video wallpaper in the background.
2. Shows the NovaOS logo with a fade-in scale animation.
3. Displays a greeting ("Welcome to NovaOS") with a blinking subtext.
4. Auto-advances to the login card after 2.5 seconds (or on any user input).
5. Renders a glass card with a blurred snapshot of the wallpaper behind it.
6. Shows the current time (large, thin font) above the card.
7. Lets the user pick from a horizontal avatar strip at the bottom.
8. Accepts the password in a stylised TextField with focus-glow border.
9. Shakes the card horizontally on authentication failure.

SDDM is configured to run under Wayland via `kwin_wayland`, which means the
entire login experience runs on the same compositor that powers the desktop,
eliminating visual discontinuity.

### Layer 3 - Desktop (Plasma 6)

After login, the user lands on a KDE Plasma 6 desktop themed through three
overlapping components:

- **Kvantum theme** (`/usr/share/Kvantum/NovaOS/`): Provides the glass-morphism
  Qt widget style - translucent buttons, blurred menus, gradient highlights.
- **Plasma Look-and-Feel package** (`com.novaos.desktop`): Bundles the color
  scheme, icon theme, window decoration, KSplash and SDDM theme together so
  they can be applied as a single unit from System Settings.
- **Window decoration** (`org.kde.novaos`): A KDecoration3 implementation
  that renders borderless windows with a subtle accent line on the active
  window and a 36px titlebar.

The desktop uses an **animated video wallpaper** by default
(`/usr/share/wallpapers/NovaOS/CrystalAurora.mp4`), played by the
`smart-video-wallpaper-reborn` Plasma wallpaper plugin.

## 3. Boot sequence

The full boot sequence, from power-on to a usable desktop, is:

1. **Firmware (UEFI or BIOS)** loads the bootloader from the ISO.
2. **systemd-boot** (UEFI) or **syslinux** (BIOS) loads the `linux` kernel
   with the `initramfs.img` initial RAM disk.
3. **mkinitcpio** in the initramfs loads kernel modules for storage, mounts
   the squashfs live filesystem, and pivots to it.
4. **systemd** starts the default target (graphical).
5. **novaos-first-boot.service** (one-shot) runs on the very first boot of the
   installed system.  It probes hardware, picks the correct GPU driver
   (amdgpu / i915 / nvidia), enables core services, sets sysctls, and creates
   the default `novaos` user if missing.
6. **sddm.service** starts SDDM, which loads the NovaOS QML theme.
7. User logs in - SDDM launches the user's Plasma 6 session via `kwin_wayland`.
8. **novaos-hardware-optimizer.service** and
   **novaos-resource-maximizer.service** start in the background and
   continuously tune the system.

## 4. Build pipeline

NovaOS is built entirely in GitHub Actions.  The pipeline has three workflows:

- **build-iso.yml** - Triggered on every push to `main`/`master`/`develop`, on
  every `v*` tag, and on a weekly Sunday cron.  Runs on an Ubuntu 22.04 runner,
  pulls the official `archlinux:latest` Docker image, mounts the repo into it,
  and runs `archiso` to produce the ISO.  On tag pushes, the ISO is published
  as a GitHub Release with a SHA256 sidecar.
- **auto-repair.yml** - Triggered automatically when `build-iso.yml` fails.
  Downloads the failed build logs, runs `.github/scripts/auto_fix.py` against
  them, and if a known pattern matches, opens a Pull Request with the patch and
  re-triggers the build.
- **sync-mirror.yml** - Triggered weekly.  Refreshes the Arch mirrorlist
  shipped inside the ISO so the live USB always has fast mirrors.

## 5. Software intelligence

Two Python daemons provide the "AI" piece of NovaOS:

### novaos-hardware-optimizer

Runs every 30 seconds.  Probes:

- CPU vendor, model, current load
- GPU vendor(s) (AMD / Intel / Nvidia / mixed)
- Power source (AC vs battery)
- Maximum thermal zone temperature
- Memory pressure

Then applies:

- CPU governor: `performance` on AC, `schedutil` on battery
- GPU performance level: `high` on AC, `auto` on battery (amdgpu + nvidia)
- Swappiness: `1` (minimise swapping to maximise RAM available to apps)
- I/O scheduler: `bfq` on battery (fairness), `mq-deadline` on AC (throughput)
- Safe GPU overclock: +80 MHz on Nvidia when thermal headroom > 25C

### novaos-resource-maximizer

Runs every 15 seconds.  Walks `psutil.process_iter()` and classifies every
process into one of four buckets:

- **foreground** - Known interactive apps (Firefox, Dolphin, VS Code, games,
  Wine processes).  Receives `nice=-8` and `ionice=best-effort/2`.
- **background** - Indexers, sync clients, build tools (`baloo`, `tracker`,
  `dockerd`).  Receives `nice=+5` and `ionice=best-effort/5`.
- **system** - systemd, NetworkManager, SDDM, PipeWire.  Receives `nice=-5`.
- **idle** - Processes with <0.5% CPU.  User-space ones can be SIGSTOPped
  (Android-style app freezing) to free memory.

Additionally, the daemon watches overall RAM pressure and dynamically
downgrades the KWin blur strength from 3 (high) to 1 (low) when memory
exceeds 88%, restoring it when pressure drops.

## 6. The NovaOS Store

The store is split into a backend daemon and a PyQt6 frontend.

### Backend (`novaos-store/backend/store_daemon.py`)

Listens on a UNIX socket at `/run/novaos/store.sock`.  Accepts JSON requests:

```json
{ "action": "install", "pkgid": "firefox", "backend": "pacman" }
```

Supports four backends:

1. **pacman** - The official Arch repositories.
2. **aur** - The Arch User Repository, via `paru`.
3. **flatpak** - Flathub, via the `flatpak` CLI.
4. **windows** - A curated catalog of popular Windows apps (Notepad++, 7-Zip,
   VLC, Microsoft Office via Bottles).  Each entry downloads the upstream
   `.exe` and runs it through a fresh Wine prefix.

### Frontend (`novaos-store/frontend/store.py`)

PyQt6 application with a glass-themed UI.  Four tabs:

1. **Search Results** - searches across all four backends in parallel.
2. **Discover** - a curated grid of recommended apps with one-click Install
   buttons.
3. **Installed** - lists every package installed via any backend.
4. **Run Windows App** - curated list of Windows apps + a tip about dragging
   `.exe` files into Bottles for one-click runners.

## 7. Filesystem layout

The installed system follows the standard Linux filesystem hierarchy with
two NovaOS-specific additions:

- `/usr/share/novaos/` - Branding assets (os-release, lsb-release, logos).
- `/var/lib/novaos/` - Runtime state (first-boot complete flag, hardware state
  JSON, resource-maximizer state JSON, store state JSON).
- `/var/log/novaos/` - Per-daemon log files.
- `/opt/novaos-store/` - The store backend + frontend Python scripts.
- `/run/novaos/` - Runtime sockets (e.g. `store.sock`).

## 8. Security model

- The `root` account is locked after first-boot (`passwd -l root`).
- The default `novaos` user is in the `wheel` group (sudo-capable).
- SSH daemon is disabled by default.
- The store daemon runs as root (so it can install packages) but only accepts
  connections from the local machine via a UNIX socket with mode `0660`.
- The auto-repair bot only commits to `auto-repair/*` branches and opens PRs -
  it never pushes directly to `main`.
