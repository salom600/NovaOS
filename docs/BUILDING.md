# Building NovaOS

This document describes how to build the NovaOS ISO, both locally and in CI.

## Prerequisites

### Local build

- A Linux host (any recent distribution works).
- Docker installed and running.
- Approximately 8 GB of free disk space.
- A reasonably fast internet connection (the build downloads ~3 GB of
  Arch packages).

### CI build

GitHub Actions provides everything.  No local setup is required.

## Local build

### Quick start

```bash
git clone https://github.com/salom600/NovaOS.git
cd NovaOS

# Build the ISO
docker run --rm --privileged \
  -v "$(pwd)":/novaos \
  -v "$(pwd)/out":/out \
  archlinux:latest \
  /bin/bash -c '
    pacman-key --init && pacman-key --populate archlinux
    pacman -Sy --noconfirm archiso
    cd /novaos/archiso/novaos
    mkdir -p /tmp/work /out
    archiso -v -w /tmp/work -o /out run .
  '

# Verify
ls -lh out/*.iso
sha256sum out/*.iso
```

### Step-by-step

1. **Clone the repository:**

   ```bash
   git clone https://github.com/salom600/NovaOS.git
   cd NovaOS
   ```

2. **Make the build directories:**

   ```bash
   mkdir -p out work
   ```

3. **Pull the official Arch Linux Docker image:**

   ```bash
   docker pull archlinux:latest
   ```

4. **Run archiso inside the container:**

   The container needs `--privileged` because archiso creates loop devices,
   mounts squashfs images, and writes to raw block devices.  It also needs
   `/dev` mounted so it can access loop devices.

   ```bash
   docker run --rm --privileged \
     -v /dev:/dev \
     -v "$(pwd)":/novaos \
     -v "$(pwd)/out":/out \
     archlinux:latest \
     /bin/bash -c '
       set -euo pipefail
       pacman-key --init
       pacman-key --populate archlinux
       echo "Server = https://geo.mirror.pkgbuild.com/\$repo/os/\$arch" \
         > /etc/pacman.d/mirrorlist
       pacman -Sy --noconfirm --noprogressbar archiso git reflector
       reflector --latest 30 --protocol https --sort rate \
         --save /etc/pacman.d/mirrorlist || true
       cd /novaos/archiso/novaos
       find airootfs/usr/local/bin -type f -exec chmod 0755 {} \;
       mkdir -p /tmp/work /out
       archiso -v -w /tmp/work -o /out run .
     '
   ```

5. **Find your ISO:**

   ```bash
   ls -lh out/
   # NovaOS-2026.01.15-x86_64.iso
   ```

### Verifying the build

```bash
sha256sum out/NovaOS-*.iso
# Compare against the value published in the GitHub Release notes
```

### Writing the ISO to a USB stick

```bash
# Replace /dev/sdX with your USB device (use lsblk to find it)
sudo dd if=out/NovaOS-*.iso of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

### Booting

Most modern firmware will boot NovaOS directly from the USB stick.  If your
machine does not, you may need to:

- Disable Secure Boot (NovaOS does not currently ship signed bootloaders).
- Enable UEFI mode (CSM/Legacy is supported but slower).
- Boot from the USB device using the firmware boot menu (usually F12, F8,
  or Esc).

## CI build

### Triggering a build

The build workflow runs automatically on:

- Push to `main`, `master`, or `develop` branches.
- Any tag matching `v*` (e.g. `v2026.1`, `v2026.1-rc1`).
- A weekly cron job (Sundays at 02:00 UTC).
- Manual dispatch via the Actions tab in GitHub.

To trigger a build manually:

1. Go to https://github.com/salom600/NovaOS/actions/workflows/build-iso.yml
2. Click "Run workflow".
3. Select the branch and (optionally) the profile.
4. Click "Run workflow".

### Producing a release

Pushing a tag `v*` will:

1. Build the ISO.
2. Create a GitHub Release with the ISO attached.
3. Generate release notes automatically from commits since the last tag.

```bash
git tag v2026.1
git push origin v2026.1
```

### Build artifacts

After a successful build, the following artifacts are available:

- `NovaOS-x86_64-iso/` - The ISO itself + manifest + SHA256 sidecar.
  Retained for 14 days.
- `novaos-build-logs-<run-id>/` - Only on failure.  Retained for 30 days.

## Troubleshooting

### "No space left on device"

The GitHub Actions runner has limited disk space.  If you see this error:

1. The `build-iso.yml` workflow already aggressively frees space.
2. If it persists, reduce the package list in `packages.x86_64`.
3. The auto-repair bot will detect this and tighten the cleanup step.

### "target not found: <package>"

A package listed in `packages.x86_64` is not in the Arch repos.  Either:

1. Remove the line (the auto-repair bot will do this automatically).
2. Move it to a custom repo (e.g. the NovaOS overlay repo).
3. Replace it with an AUR equivalent and add it to a `paru` install step.

### "signature from <key> is invalid"

The local pacman keyring is stale.  Run:

```bash
pacman-key --refresh-keys
```

The auto-repair bot will add this step to the build workflow if it detects
the error.

### "archiso: unknown bootmode"

The Arch `archiso` package changed its supported bootmodes.  Compare your
`profiledef.sh` `bootmodes=` array against the current `archiso` documentation
at https://wiki.archlinux.org/title/Archiso.  The auto-repair bot will
automatically align the bootmodes with the current archiso-supported set.

### Build succeeds but ISO does not boot

1. Verify the SHA256 matches.
2. Re-flash the USB stick with `conv=fsync` and `sync` afterwards.
3. Try a different USB stick - some sticks have weird firmware.
4. Try booting with `nomodeset` on the kernel command line (press `e` in the
   bootloader).  If that works, you have a GPU driver issue - the NovaOS
   first-boot service should fix this on the installed system.

### Slow builds

The first build downloads ~3 GB of packages.  Subsequent builds are faster
because Docker caches the `archlinux:latest` image, but archiso itself does
not cache packages between runs.  To cache packages locally, you can mount a
host directory into the container as the pacman cache:

```bash
mkdir -p pacman-cache
docker run --rm --privileged \
  -v "$(pwd)":/novaos \
  -v "$(pwd)/out":/out \
  -v "$(pwd)/pacman-cache":/var/cache/pacman/pkg \
  archlinux:latest ...
```
