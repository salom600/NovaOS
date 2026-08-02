#!/bin/bash
# novaos-sddm-session.sh
#
# Wrapper around kwin_wayland for SDDM's Wayland compositor command.
# Reads /proc/cmdline for the 'novaos.session=' parameter and falls back
# to X11 if it equals 'x11'. This fixes the blank-screen issue on 2016-era
# GPUs where kwin_wayland fails to initialize KMS.
#
# SDDM invokes this as: /usr/share/novaos/sddm-session.sh wayland
# (or via DisplayServer=wayland in sddm.conf)

set -e

# Read the kernel cmdline
CMDLINE=$(cat /proc/cmdline 2>/dev/null || echo "")

# Extract novaos.session= value
SESSION=$(echo "$CMDLINE" | grep -oE 'novaos\.session=[a-zA-Z0-9]+' | cut -d= -f2)

if [[ "$SESSION" == "x11" ]]; then
    # Switch SDDM to X11 mode by writing a runtime override
    # SDDM reads /etc/sddm.conf.d/*.conf at startup, so we create a drop-in
    cat > /etc/sddm.conf.d/00-runtime-session.conf <<EOF
[General]
DisplayServer=x11
EOF
    echo "[novaos-sddm-session] Switched to X11 mode (novaos.session=x11)" >&2
    # Exit 0 - SDDM will restart and pick up the new config
    exec /usr/bin/sddm-greeter --test-mode 2>/dev/null || exit 0
fi

# Default: launch kwin_wayland as the SDDM greeter compositor
echo "[novaos-sddm-session] Starting kwin_wayland for SDDM" >&2
exec /usr/bin/kwin_wayland --no-global-shortcuts --no-lockscreen --locale C
