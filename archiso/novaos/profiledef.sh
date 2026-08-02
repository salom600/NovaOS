#!/usr/bin/env bash
# shellcheck disable=SC2034
#
# NovaOS ISO profile definition
# Builds a modern, hardware-agnostic KDE Plasma 6 live ISO
#

iso_name="NovaOS"
iso_label="NOVAOS_$(date +%Y%m)"
iso_publisher="NovaOS Project <https://github.com/salom600/NovaOS>"
iso_application="NovaOS Live/Install Media"
iso_version="$(date +%Y.%m.%d)"
iso_install_dir="novaos"
# NOTE: iso_features is optional in modern archiso - do not append to an
# unbound variable, that breaks under set -u (which mkarchiso uses).
iso_features="uefi amd64 intel64"
# pacman_conf MUST be set here - _read_profile() in mkarchiso sources this
# file then calls realpath on pacman_conf before _set_overrides runs.
# Without this line, pacman_conf is empty and realpath fails with:
#   realpath: empty argument
pacman_conf="pacman.conf"
bootmodes=('bios.syslinux.mbr' 'bios.syslinux.eltorito'
           'uefi-x64.systemd-boot.esp'
           'uefi-x64.systemd-boot.eltorito')
build_date="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
build_tool="archiso"
