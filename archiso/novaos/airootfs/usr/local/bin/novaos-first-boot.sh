#!/usr/bin/env bash
#
# novaos-first-boot.service - runs once at first boot of the installed system
# Performs:
#   1. Hardware probe (CPU/GPU/storage)
#   2. Auto-selects best Mesa / Nvidia driver
#   3. Enables Bluetooth, NetworkManager, Bluetooth, CUPS, fwupd
#   4. Configures mirrorlist with rate-mirrors
#   5. Sets up reflector timer
#   6. Optimizes swappiness, I/O scheduler, CPU governor
#   7. Locks root, creates initial user if missing
#   8. Touches /var/lib/novaos/.first-boot-complete
#
set -euo pipefail

LOG_TAG="novaos-first-boot"
LOG_FILE=/var/log/novaos/first-boot.log
STATE_DIR=/var/lib/novaos
mkdir -p /var/log/novaos "$STATE_DIR"

log()  { logger -t "$LOG_TAG" "$*"; echo "[$(date -Is)] $*" | tee -a "$LOG_FILE" >&2 ; }
err()  { logger -t "$LOG_TAG" -p user.err "$*"; echo "[$(date -Is)] ERROR: $*" | tee -a "$LOG_FILE" >&2 ; }

if [[ -f "$STATE_DIR/.first-boot-complete" ]]; then
    log "First-boot already done. Skipping."
    exit 0
fi

log "===== NovaOS first-boot starting ====="

# 1) Mirrorlist (rate-mirrors prefers fast, fresh mirrors)
if command -v rate-mirrors >/dev/null 2>&1; then
    log "Refreshing Arch mirrorlist with rate-mirrors…"
    rate-mirrors --allow-root arch | tee /etc/pacman.d/mirrorlist > /dev/null || \
        err "rate-mirrors failed; keeping default mirrorlist"
fi

# 2) Init pacman keyring + sync dbs
log "Initialising pacman keyring and syncing databases…"
pacman-key --init
pacman-key --populate archlinux
pacman -Sy --noconfirm --noprogressbar || err "pacman -Sy returned non-zero"

# 3) Enable essential services
log "Enabling core services…"
systemctl enable --now NetworkManager 2>/dev/null || true
systemctl enable --now bluetooth     2>/dev/null || true
systemctl enable --now cups           2>/dev/null || true
systemctl enable --now reflector.timer 2>/dev/null || true
systemctl enable --now fwupd          2>/dev/null || true
systemctl enable --now systemd-timesyncd 2>/dev/null || true
systemctl enable --now tlp            2>/dev/null || true
systemctl enable --now thermald       2>/dev/null || true
systemctl enable --now sddm           2>/dev/null || true
systemctl enable --now novaos-hardware-optimizer 2>/dev/null || true
systemctl enable --now novaos-resource-maximizer 2>/dev/null || true
systemctl enable --now novaos-store-daemon 2>/dev/null || true

# 4) Hardware probe - choose GPU driver
log "Probing GPU hardware…"
GPU_VENDORS=$(lspci -nnk | grep -iE 'vga|3d|display' || true)
log "Detected GPU(s):\n$GPU_VENDORS"

if echo "$GPU_VENDORS" | grep -qi 'nvidia'; then
    log "Nvidia GPU detected - enabling nvidia-dkms + nvidia-suspend services…"
    pacman -S --needed --noconfirm --noprogressbar nvidia-dkms nvidia-utils lib32-nvidia-utils || \
        err "Failed to install Nvidia driver packages"
    systemctl enable nvidia-suspend.service   nvidia-hibernate.service \
                     nvidia-resume.service     2>/dev/null || true
    echo "options nvidia NVreg_PreserveVideoMemoryAllocations=1" > /etc/modprobe.d/novaos-nvidia.conf
    echo "options nvidia modeset=1"                          >> /etc/modprobe.d/novaos-nvidia.conf
    echo "options nvidia_drm modeset=1 fbdev=1"              >> /etc/modprobe.d/novaos-nvidia.conf
    mkinitcpio -P || err "mkinitcpio failed after nvidia enable"
fi

if echo "$GPU_VENDORS" | grep -qiE 'amd|ati|radeon'; then
    log "AMD GPU detected - ensuring amdgpu/radeon early-load…"
    install -m644 /dev/stdin /etc/modprobe.d/novaos-amd.conf <<'EOF'
options amdgpu si_support=1 cik_support=1
options amdgpu vm_size=64
options radeon si_support=1 cik_support=0
EOF
    echo "amdgpu" >> /etc/mkinitcpio.conf.d/novaos-gpu.conf 2>/dev/null || \
        echo "MODULES=(amdgpu radeon)" > /etc/mkinitcpio.conf.d/novaos-gpu.conf
    mkinitcpio -P || err "mkinitcpio failed after amd enable"
fi

if echo "$GPU_VENDORS" | grep -qi 'intel'; then
    log "Intel GPU detected - configuring i915 module options…"

    # CRITICAL: enable_guc=3 requires GuC firmware which only exists for
    # Gen 12+ (Tiger Lake, 2020+). On Gen 9-11 (Skylake, Kaby Lake, Coffee
    # Lake, Ice Lake - 2015-2019), enable_guc=3 causes DRM init failure
    # and a BLANK SCREEN at SDDM startup.
    #
    # Probe the Intel GPU generation via lspci + PCI device IDs.
    # Intel Gen 12+ iGPUs have PCI device IDs starting from 0x9A (Tiger Lake)
    # and 0x46 (Alder Lake) / 0xA7 (Raptor Lake) / 0x7D (Meteor Lake).
    INTEL_GEN12=0
    INTEL_PCI=$(lspci -nn | grep -iE 'vga|3d|display' | grep -i 'intel' | \
                grep -oE '\[0x[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]' | head -1)
    INTEL_DEV_ID=$(echo "$INTEL_PCI" | sed -n 's/.*:0x\([0-9a-fA-F]\{4\}\)]/\1/p')

    if [[ -n "$INTEL_DEV_ID" ]]; then
        INTEL_DEV_DEC=$((16#$INTEL_DEV_ID))
        log "Intel GPU PCI device ID: 0x$INTEL_DEV_ID ($INTEL_DEV_DEC)"
        # Tiger Lake (Gen12) starts at 0x9A00, Ice Lake (Gen11) at 0x8A00
        if (( INTEL_DEV_DEC >= 0x9A00 )); then
            INTEL_GEN12=1
            log "  -> Gen 12+ detected - enabling GuC submission"
        else
            log "  -> Gen 11 or older - GuC disabled (would break display)"
        fi
    fi

    if [[ "$INTEL_GEN12" == "1" ]]; then
        install -m644 /dev/stdin /etc/modprobe.d/novaos-intel.conf <<'EOF'
# Written by novaos-first-boot - Intel Gen 12+ (Tiger Lake and newer)
options i915 enable_guc=3 enable_fbc=1 fastboot=1 enable_psr=1
options i915 enable_dc=2 disable_power_well=0
EOF
    else
        install -m644 /dev/stdin /etc/modprobe.d/novaos-intel.conf <<'EOF'
# Written by novaos-first-boot - Intel Gen 11 or older (Skylake, Kaby Lake, etc.)
# enable_guc=3 is OMITTED - GuC firmware does not exist for these generations
# and would cause a blank screen at SDDM startup.
options i915 enable_fbc=1 fastboot=1
options i915 enable_dc=2 disable_power_well=0
EOF
    fi
    mkinitcpio -P || err "mkinitcpio failed after intel enable"
fi

# 5) CPU governor
CPU_VENDOR=$(grep -m1 'vendor_id' /proc/cpuinfo | awk '{print $3}')
log "CPU vendor: $CPU_VENDOR"
case "$CPU_VENDOR" in
    GenuineIntel)
        log "Intel CPU - enabling thermald + intel_pstate=powersave"
        install -m644 /dev/stdin /etc/modprobe.d/novaos-cpu.conf <<'EOF'
options intel_pstate=active
EOF
        ;;
    AuthenticAMD)
        log "AMD CPU - enabling amd-pstate-epp"
        install -m644 /dev/stdin /etc/modprobe.d/novaos-cpu.conf <<'EOF'
options amd-pstate shared_mem=1
EOF
        ;;
esac

# 6) I/O + memory tunables for "maximize RAM/CPU/disk utilisation"
log "Applying NovaOS sysctl tuning…"
install -m644 /dev/stdin /etc/sysctl.d/99-novaos.conf <<'EOF'
# Maximise responsiveness
vm.swappiness=10
vm.vfs_cache_pressure=50
vm.dirty_background_ratio=5
vm.dirty_ratio=15
vm.dirty_expire_centisecs=1500
vm.dirty_writeback_centisecs=3000

# Bigger IO queues (good for SSD/NVMe; harmless on HDD)
kernel.sched_latency_ns=24000000
kernel.sched_min_granularity_ns=3000000
kernel.sched_wakeup_granularity_ns=4000000

# Network
net.core.default_qdisc=cake
net.ipv4.tcp_congestion_control=bbr
net.ipv4.tcp_fastopen=3
net.core.rmem_max=67108864
net.core.wmem_max=67108864
net.ipv4.tcp_rmem=4096 87380 67108864
net.ipv4.tcp_wmem=4096 65536 67108864
EOF

# 7) Set IO scheduler to bfq/mq for desktop responsiveness
for dev in /sys/block/sd*/queue/scheduler /sys/block/nvme*n*/queue/scheduler /sys/block/mmcblk*/queue/scheduler /sys/block/vd*/queue/scheduler; do
    [[ -w "$dev" ]] || continue
    if grep -q 'bfq' "$dev"; then
        echo 'bfq' > "$dev"
    elif grep -q 'mq-deadline' "$dev"; then
        echo 'mq-deadline' > "$dev"
    fi
done

# 8) Disable ssh server on first boot (security)
systemctl disable sshd 2>/dev/null || true

# 9) Lock root, create 'novaos' user if missing
if ! id -u novaos >/dev/null 2>&1; then
    log "Creating default 'novaos' user…"
    useradd -m -G wheel,audio,video,input,storage,optical,network,lp,scanner,wireshark,kvm,libvirt,docker -s /bin/bash novaos
    echo 'novaos:novaos' | chpasswd
    passwd -l root
fi

# 10) Persist state
date -Is > "$STATE_DIR/.first-boot-complete"

log "===== NovaOS first-boot complete ====="

# 11) Disable ourselves (one-shot)
systemctl disable novaos-first-boot.service

exit 0
