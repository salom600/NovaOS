#!/usr/bin/env bash
#
# NovaOS - airootfs customization script
# Called by archiso during the build process.
# Installs NovaOS themes, services, store, wallpapers into the live ISO.
#
set -euo pipefail

REPO_ROOT="${NOVAOS_REPO_ROOT:-/novaos}"
AIROOTFS="${REPO_ROOT}/archiso/novaos/airootfs"

echo "[novaos] Installing NovaOS customisations into airootfs..."

# 1) Make scripts executable
find "${AIROOTFS}/usr/local/bin" -type f -exec chmod 0755 {} \;
find "${AIROOTFS}" -name "*.sh" -exec chmod 0755 {} \;
chmod 0755 "${AIROOTFS}/usr/local/bin/novaos-first-boot.sh" 2>/dev/null || true

# 2) Install NovaOS Python scripts (store + daemons)
mkdir -p "${AIROOTFS}/opt/novaos-store/backend" "${AIROOTFS}/opt/novaos-store/frontend"
cp -v "${REPO_ROOT}/novaos-store/backend/store_daemon.py" \
      "${AIROOTFS}/opt/novaos-store/backend/store_daemon.py"
cp -v "${REPO_ROOT}/novaos-store/frontend/store.py" \
      "${AIROOTFS}/opt/novaos-store/frontend/store.py"
chmod 0755 "${AIROOTFS}/opt/novaos-store/backend/store_daemon.py"
chmod 0755 "${AIROOTFS}/opt/novaos-store/frontend/store.py"

# Make store.py executable directly
ln -sf /opt/novaos-store/frontend/store.py "${AIROOTFS}/usr/local/bin/novaos-store"

# 3) Generate logo + wallpapers placeholders if missing
if [[ ! -f "${AIROOTFS}/usr/share/sddm/themes/novaos/Assets/novaos-logo.svg" ]]; then
    mkdir -p "${AIROOTFS}/usr/share/sddm/themes/novaos/Assets"
    cp -v "${REPO_ROOT}/themes/novaos-icons/novaos-logo.svg" \
          "${AIROOTFS}/usr/share/sddm/themes/novaos/Assets/" 2>/dev/null || true
fi

# 4) Install icon theme skeleton
if [[ -d "${REPO_ROOT}/themes/novaos-icons" ]]; then
    mkdir -p "${AIROOTFS}/usr/share/icons/NovaOS-Crystal"
    cp -rv "${REPO_ROOT}/themes/novaos-icons/." \
           "${AIROOTFS}/usr/share/icons/NovaOS-Crystal/" 2>/dev/null || true
fi

# 5) Install Kvantum theme source
if [[ -d "${REPO_ROOT}/themes/kvantum-novaos" ]]; then
    mkdir -p "${AIROOTFS}/usr/share/Kvantum/NovaOS"
    cp -rv "${REPO_ROOT}/themes/kvantum-novaos/." \
           "${AIROOTFS}/usr/share/Kvantum/NovaOS/" 2>/dev/null || true
fi

# 6) Install SDDM theme source (override default if newer)
if [[ -d "${REPO_ROOT}/themes/sddm-novaos" ]]; then
    mkdir -p "${AIROOTFS}/usr/share/sddm/themes/novaos"
    cp -rv "${REPO_ROOT}/themes/sddm-novaos/." \
           "${AIROOTFS}/usr/share/sddm/themes/novaos/" 2>/dev/null || true
fi

# 7) Install animated wallpapers (placeholder generator)
mkdir -p "${AIROOTFS}/usr/share/wallpapers/NovaOS"
if [[ -f "${REPO_ROOT}/themes/wallpapers/CrystalAurora.mp4" ]]; then
    cp -v "${REPO_ROOT}/themes/wallpapers/CrystalAurora.mp4" \
          "${AIROOTFS}/usr/share/wallpapers/NovaOS/CrystalAurora.mp4"
else
    # Generate a 5-second placeholder MP4 (solid color)
    if command -v ffmpeg >/dev/null 2>&1; then
        ffmpeg -y -f lavfi -i \
            "color=c=0x0E1422:s=1920x1080:d=5:r=30" \
            -c:v libx264 -pix_fmt yuv420p \
            "${AIROOTFS}/usr/share/wallpapers/NovaOS/CrystalAurora.mp4" 2>/dev/null || true
    fi
fi

# 8) Install NovaOS sounds
if [[ -d "${REPO_ROOT}/themes/sounds" ]]; then
    mkdir -p "${AIROOTFS}/usr/share/sounds/NovaOS"
    cp -rv "${REPO_ROOT}/themes/sounds/." \
           "${AIROOTFS}/usr/share/sounds/NovaOS/" 2>/dev/null || true
fi

# 9) Enable NovaOS services by default (in the live ISO)
for svc in novaos-first-boot \
           novaos-hardware-optimizer \
           novaos-resource-maximizer \
           novaos-store-daemon; do
    if [[ -f "${AIROOTFS}/usr/lib/systemd/system/${svc}.service" ]]; then
        ln -sf "/usr/lib/systemd/system/${svc}.service" \
               "${AIROOTFS}/etc/systemd/system/multi-user.target.wants/${svc}.service"
        mkdir -p "${AIROOTFS}/etc/systemd/system/multi-user.target.wants"
        echo "[novaos] enabled ${svc}"
    fi
done

# 10) Set SDDM theme
mkdir -p "${AIROOTFS}/etc/sddm.conf.d"
cat > "${AIROOTFS}/etc/sddm.conf.d/novaos-theme.conf" <<'EOF'
[Theme]
Current=novaos
ThemeDir=/usr/share/sddm/themes
CursorTheme=breeze_cursors
CursorSize=24

[Wayland]
CompositorCommand=kwin_wayland --no-global-shortcuts --no-lockscreen
EOF

# 11) Make NovaOS-default look-and-feel the system default
mkdir -p "${AIROOTFS}/etc/skel/.config"
cat > "${AIROOTFS}/etc/skel/.config/kdeglobals" <<'EOF'
[General]
ColorScheme=NovaOSCrystal
LookAndFeelPackage=com.novaos.desktop
widgetStyle=kvantum

[KDE]
LookAndFeelPackage=com.novaos.desktop
widgetStyle=kvantum
ColorScheme=NovaOSCrystal

[Icons]
Theme=NovaOS-Crystal

[WM]
activeFont=Inter,13,-1,5,600,0,0,0,0,0,0,0,0,0,0,1
EOF

# 12) Set Plasma shell to use animated wallpaper by default
mkdir -p "${AIROOTFS}/etc/skel/.local/share/plasma_wallpapers"
cat > "${AIROOTFS}/etc/skel/.config/plasma-org.kde.plasma.shell-appletsrc" <<'EOF'
[Containments][1][Wallpaper][org.kde.image][General]
Image=file:///usr/share/wallpapers/NovaOS/CrystalAurora.mp4
FillMode=2
EOF

echo "[novaos] Done."
exit 0
