# NovaOS Hardware Compatibility

NovaOS targets a broad hardware envelope, from 2009-era Intel Core 2 Duo
machines through 2026 flagship hardware.  This document describes what is
supported and how the system auto-tunes itself for each class of hardware.

## Supported CPUs

### Intel

| Family                            | First released | Status        | Notes                                            |
|-----------------------------------|----------------|---------------|--------------------------------------------------|
| Core 2 (Merom, Penryn)            | 2006-2008      | Best-effort   | Boot works; some SSE4.1 apps may not run.        |
| Core i (1st gen, Nehalem)         | 2009           | Supported     | Full support, `intel_pstate=active`.             |
| Core i (2nd-7th gen)              | 2011-2017      | Supported     | Full support.                                    |
| Core i (8th-14th gen)             | 2017-2023      | Supported     | Full support, hybrid CPU scheduling.             |
| Core Ultra (Meteor Lake, Arrow Lake) | 2023-2024   | Supported     | Full support, NPU power management.              |
| Xeon (all)                        | 2009+          | Supported     | Same as the consumer equivalent.                 |
| Atom (all)                        | 2008+          | Best-effort   | Works but may be slow.                           |

### AMD

| Family                            | First released | Status        | Notes                                            |
|-----------------------------------|----------------|---------------|--------------------------------------------------|
| Phenom II                         | 2008           | Supported     | Full support.                                    |
| FX (Bulldozer, Piledriver)        | 2011-2015      | Supported     | Works but per-thread performance is low.         |
| Ryzen (all)                       | 2017+          | Supported     | `amd-pstate=active`, CPPC enabled.               |
| Threadripper (all)                | 2017+          | Supported     | Full support.                                    |
| EPYC (all)                        | 2017+          | Supported     | Full support.                                    |

### ARM (preview)

NovaOS includes cross-compilation hooks for ARM but does not yet ship ARM ISOs
in CI.  ARM support is planned for NovaOS 2026.2.

## Supported GPUs

### Intel integrated

| Family            | Driver        | Status        | Notes                                            |
|-------------------|---------------|---------------|--------------------------------------------------|
| Gen4 (i965)       | `i915`        | Supported     | Hardware video decode via `intel-media-driver`.  |
| Gen5 (Ironlake)   | `i915`        | Best-effort   | Software rendering for some workloads.           |
| Gen6-7 (Sandy-Ivy)| `i915`        | Supported     | Full support.                                    |
| Gen8-9 (Broadwell-Skylake) | `i915` | Supported     | Full support.                                    |
| Gen11 (Ice Lake)  | `i915`        | Supported     | Full support.                                    |
| Gen12 (Tiger Lake, Xe-LP) | `i915` | Supported     | Full support, hardware AV1 decode on Xe-LP+.     |
| Xe-HPG (ARC A-Series) | `i915` + `xe` | Supported  | Both drivers ship; `xe` is default for ARC.      |
| Xe2 (Meteor Lake, Battlemage) | `xe` | Supported   | Default driver is `xe` for Xe2+.                 |

Module options applied by `novaos-first-boot.service`:

```
options i915 enable_guc=3 enable_fbc=1 fastboot=1 enable_psr=1
options i915 enable_dc=2 disable_power_well=0
```

### AMD

| Family            | Driver        | Status        | Notes                                            |
|-------------------|---------------|---------------|--------------------------------------------------|
| Radeon HD 5000-7000 (TeraScale) | `radeon` | Supported | `si_support=1 cik_support=0`.                |
| Radeon HD 8000+ (GCN) | `amdgpu`  | Supported     | `si_support=1 cik_support=1`.                    |
| Radeon RX 400-7000 (Polaris-RDNA3) | `amdgpu` | Supported | Full support, Vulkan via `vulkan-radeon`.    |
| Radeon RX 9000 (RDNA4) | `amdgpu` | Supported     | Full support.                                    |

Module options applied by `novaos-first-boot.service`:

```
options amdgpu si_support=1 cik_support=1
options amdgpu vm_size=64
options radeon si_support=1 cik_support=0
```

### NVIDIA

| Family            | Driver        | Status        | Notes                                            |
|-------------------|---------------|---------------|--------------------------------------------------|
| GeForce 400-700   | `nvidia-dkms` | Supported     | Use `nvidia-470xx-dkms` if mainline drops support. |
| GeForce 900-1000  | `nvidia-dkms` | Supported     | Full support.                                    |
| GeForce 1600-3000 | `nvidia-dkms` | Supported     | Full support, hardware video decode.             |
| GeForce 4000-5000 | `nvidia-dkms` | Supported     | Full support.                                    |

Module options applied by `novaos-first-boot.service`:

```
options nvidia NVreg_PreserveVideoMemoryAllocations=1
options nvidia modeset=1
options nvidia_drm modeset=1 fbdev=1
```

The following systemd services are enabled for Nvidia suspend/resume:

- `nvidia-suspend.service`
- `nvidia-hibernate.service`
- `nvidia-resume.service`

## Supported Wi-Fi

| Vendor     | Driver                  | Status        |
|------------|-------------------------|---------------|
| Intel      | `iwlwifi`               | Supported     |
| Realtek    | `rtl8xxxu`, `rtw89`     | Supported     |
| Atheros    | `ath9k`, `ath10k`, `ath11k`, `ath12k` | Supported |
| Broadcom   | `brcmfmac`, `wl`        | Supported (wl from AUR) |
| MediaTek   | `mt76`                  | Supported     |

## Supported audio

| Class                          | Driver              | Status    |
|--------------------------------|---------------------|-----------|
| Intel HDA                      | `snd_hda_intel`     | Supported |
| Realtek ALC codecs             | (via HDA)           | Supported |
| AMD ACP                        | `snd_pci_acp5x` etc | Supported |
| USB DACs                       | `snd_usb_audio`     | Supported |
| Bluetooth headsets             | (via PipeWire)      | Supported |
| Sound Open Firmware devices    | `sof-firmware`      | Supported |

PipeWire + WirePlumber is the default audio stack.  PulseAudio clients are
supported via the `pipewire-pulse` compatibility layer.

## Supported storage

| Type        | Driver             | Status    |
|-------------|--------------------|-----------|
| SATA HDD/SSD| `ahci`             | Supported |
| NVMe        | `nvme`             | Supported |
| eMMC        | `sdhci`            | Supported |
| SD card     | `rtsx_pci`         | Supported |
| USB         | `uas`, `usb-storage` | Supported |
| SAS         | `mpt3sas`          | Supported |
| Software RAID | `mdadm`          | Supported |
| LVM         | `lvm2`             | Supported |
| LUKS        | `cryptsetup`       | Supported |
| Btrfs       | `btrfs`            | Supported |
| ext4        | `ext4`             | Supported |
| XFS         | `xfs`              | Supported |
| F2FS        | `f2fs`             | Supported |
| exFAT       | `exfatprogs`       | Supported |
| NTFS        | `ntfs-3g`          | Supported (read/write) |
| FAT32       | `dosfstools`       | Supported |

## Auto-tuning behavior

The `novaos-hardware-optimizer.service` daemon probes hardware every 30
seconds and applies the following tunings:

### On AC power

- CPU governor: `performance`
- GPU performance level: `high` (amdgpu + nvidia)
- I/O scheduler: `mq-deadline` (throughput-optimised)
- Safe GPU overclock: +80 MHz on Nvidia (when thermal headroom > 25C)
- Swappiness: 1 (minimise swapping, maximise RAM available to apps)
- TCP congestion: `bbr`
- Network queue discipline: `cake`

### On battery

- CPU governor: `schedutil` (or `powersave` if schedutil unavailable)
- GPU performance level: `auto` (let the driver decide)
- I/O scheduler: `bfq` (latency-optimised for interactive workloads)
- No GPU overclock
- Swappiness: 1
- TCP congestion: `bbr`
- Network queue discipline: `cake`

### Thermal throttling

If any thermal zone exceeds 85C, the daemon:

1. Switches the CPU governor to `powersave`.
2. Drops the GPU performance level to `auto`.
3. Logs a warning to `/var/log/novaos/hardware-optimizer.log`.

When the temperature drops below 75C for 60 seconds, the previous profile is
restored.

## Kernel

NovaOS ships the standard Arch `linux` kernel (currently 6.x).  The
`linux-zen` kernel is available as an alternative and is recommended for
desktop use - it has lower latency and better scheduler tuning for
interactive workloads.  To switch:

```bash
sudo pacman -S linux-zen linux-zen-headers
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

## Firmware

NovaOS ships `linux-firmware`, `intel-ucode`, `amd-ucode`, `sof-firmware`,
`alsa-firmware`, and the Broadcom `brcmfmac` firmwares.  The
`linux-firmware-blob` package (containing some proprietary firmwares) is
available from the AUR if needed.

## Tested hardware matrix

The following hardware has been explicitly tested with NovaOS (in CI on
QEMU and on physical test rigs):

### Laptops

- ThinkPad X220 (Intel i5-2520M, Intel HD 3000) - works perfectly.
- ThinkPad T480 (Intel i5-8350U, Intel UHD 620) - works perfectly.
- ThinkPad X1 Carbon Gen 11 (Intel i7-1365U, Intel Iris Xe) - works perfectly.
- Dell XPS 13 9320 (Intel i7-1260P, Intel Iris Xe) - works perfectly.
- MacBook Pro 14" 2023 (Apple M2 Pro) - not yet supported (ARM).
- ASUS ROG Strix G16 (Intel i9-13980HX, RTX 4070) - works perfectly with Nvidia.
- Lenovo Legion 7 (Ryzen 9 7945HX, RTX 4090) - works perfectly with hybrid graphics.

### Desktops

- Intel NUC 13 (Intel i5-1340P) - works perfectly.
- Custom AM5 (Ryzen 9 7950X3D, RX 7900 XTX) - works perfectly.
- Custom LGA1700 (Intel i9-14900K, RTX 4090) - works perfectly.
- Custom AM4 (Ryzen 7 5800X, ARC A770) - works perfectly.

### Single-board computers

- Raspberry Pi 5 - not yet supported (ARM).
- Pinebook Pro - not yet supported (ARM).

## Reporting hardware issues

If your hardware does not work with NovaOS, please file an issue at
https://github.com/salom600/NovaOS/issues with:

1. The output of `inxi -Fxxxz` (run from the live ISO or installed system).
2. The output of `journalctl -b -p err` (errors from the current boot).
3. The output of `dmesg | grep -iE 'firmware|error|failed'`.
4. A description of what works and what doesn't.

The NovaOS first-boot log is at `/var/log/novaos/first-boot.log` and contains
detailed information about what hardware was detected and what drivers were
applied.
