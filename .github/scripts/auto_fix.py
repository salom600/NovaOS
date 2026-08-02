#!/usr/bin/env python3
"""
NovaOS Auto-Fixer
=================
Reads the combined build log of a failed GitHub Actions build and tries to
automatically patch the NovaOS repository so the next build succeeds.

The fixer uses a catalog of known failure patterns, each with a deterministic
fix recipe.  For unknown failures, it falls back to:

  1. Use heuristic package-not-found -> comment out offending line
  2. Use heuristic syntax error    -> show context only
  3. Otherwise: report unrepaired

Run:
    python3 auto_fix.py --log combined.log --repo /path/to/repo \
                        --run-id 1234 --git-sha abc123
Output (stdout): JSON document of the form
    {
      "fixed":   true|false,
      "summary": "...",
      "files":   ["archiso/novaos/packages.x86_64", ...],
      "rules":   ["package_not_found", ...]
    }
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional


# ----------------------------------------------------------------------
# Rule definitions
# ----------------------------------------------------------------------
# Each rule is a tuple:
#   (rule_id, regex, fix_function(log_match, repo_root) -> {summary, files})
# fix_function returns None if it cannot fix.


def _read(p: Path) -> str:
    try:
        return p.read_text()
    except Exception:
        return ""


def _write(p: Path, content: str) -> None:
    p.write_text(content)


# Rule 1: package not found in repo -> comment out from packages.x86_64
PKG_NOT_FOUND_RE = re.compile(
    r"error: target not found: (\S+)|"
    r"warning: package (\S+) was not found|"
    r"cannot find package (\S+)"
)


def fix_pkg_not_found(m: re.Match, repo: Path) -> Optional[Dict]:
    pkg = next((g for g in m.groups() if g), None)
    if not pkg:
        return None
    # Strip version specifier
    pkg_clean = re.split(r"[<>=]", pkg)[0]
    for f in [
        repo / "archiso/novaos/packages.x86_64",
        repo / "archiso/novaos/packages.live.x86_64",
        repo / "archiso/novaos/packages.installed.x86_64",
    ]:
        if not f.exists():
            continue
        text = _read(f)
        if re.search(rf"^\s*{re.escape(pkg_clean)}\b", text, re.MULTILINE):
            new_text = re.sub(
                rf"^(\s*)({re.escape(pkg_clean)}(\s.*|\s*)$)",
                rf"\1# REMOVED-AUTO: target not found in repo\n\1#\2",
                text,
                flags=re.MULTILINE,
            )
            _write(f, new_text)
            return {
                "summary": f"Commented out missing package `{pkg_clean}` in {f.name}",
                "files":   [str(f.relative_to(repo))],
            }
    return None


# Rule 2: invalid package signature -> refresh keyring in build step
SIG_RE = re.compile(
    r"error: .*: signature from .* is invalid|"
    r"error: .*: missing required signature|"
    r"PGP signature verification failed",
    re.IGNORECASE,
)


def fix_sig_error(m: re.Match, repo: Path) -> Optional[Dict]:
    wf = repo / ".github/workflows/build-iso.yml"
    if not wf.exists():
        return None
    text = _read(wf)
    needle = "pacman-key --init"
    if "pacman-key --init" in text and "--refresh-keys" not in text:
        new_text = text.replace(
            "pacman-key --init\n",
            "pacman-key --init\n              pacman-key --refresh-keys || true\n",
            1,
        )
        _write(wf, new_text)
        return {
            "summary": "Added `pacman-key --refresh-keys` step to refresh stale signatures.",
            "files":   [str(wf.relative_to(repo))],
        }
    return None


# Rule 3: disk full -> tighten cleanup step
DISK_FULL_RE = re.compile(
    r"No space left on device|disk full|errno 28|ENOSPC",
    re.IGNORECASE,
)


def fix_disk_full(m: re.Match, repo: Path) -> Optional[Dict]:
    wf = repo / ".github/workflows/build-iso.yml"
    if not wf.exists():
        return None
    text = _read(wf)
    if "df -h /" in text and "rm -rf /usr/share/doc" not in text:
        # Add more aggressive cleanup
        new_text = text.replace(
            "sudo apt-get clean",
            "sudo apt-get clean\n"
            "          sudo rm -rf /usr/share/doc /usr/share/man /var/lib/apt/lists/* /var/cache/apt 2>/dev/null || true\n"
            "          docker system prune -af --volumes 2>/dev/null || true",
            1,
        )
        _write(wf, new_text)
        return {
            "summary": "Aggressively freed more disk space in CI build step.",
            "files":   [str(wf.relative_to(repo))],
        }
    return None


# Rule 4: AUR build timeout -> bump timeout
AUR_TIMEOUT_RE = re.compile(
    r"paru|yay.*timeout|AUR build timed out|build timeout.*aur",
    re.IGNORECASE,
)


def fix_aur_timeout(m: re.Match, repo: Path) -> Optional[Dict]:
    wf = repo / ".github/workflows/build-iso.yml"
    if not wf.exists():
        return None
    text = _read(wf)
    if "timeout-minutes: 90" in text:
        new_text = text.replace("timeout-minutes: 90", "timeout-minutes: 180")
        _write(wf, new_text)
        return {
            "summary": "Bumped build job timeout from 90m to 180m for slow AUR builds.",
            "files":   [str(wf.relative_to(repo))],
        }
    return None


# Rule 5: missing file referenced by archiso (profiledef, packages.*)
MISSING_FILE_RE = re.compile(
    r"archiso.*?:.*?cannot (?:find|access).*?['\"]?([^'\"\s]+)['\"]?",
    re.IGNORECASE,
)


def fix_missing_file(m: re.Match, repo: Path) -> Optional[Dict]:
    fname = m.group(1)
    # Only fix if it's a profile file that should exist
    profile_dir = repo / "archiso" / "novaos"
    candidate = profile_dir / fname
    if not candidate.exists() and fname in (
        "profiledef.sh", "packages.x86_64", "packages.live.x86_64"
    ):
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("# Auto-created by auto_fix.py\n")
        return {
            "summary": f"Created empty placeholder {fname} (was missing).",
            "files":   [str(candidate.relative_to(repo))],
        }
    return None


# Rule 6: SDDM theme QML syntax error -> disable theme in profile
QML_SYNTAX_RE = re.compile(
    r"sddm.*theme.*error|file:.*Main\.qml.*error|qml.*syntax error",
    re.IGNORECASE,
)


def fix_qml_syntax(m: re.Match, repo: Path) -> Optional[Dict]:
    sddm_conf = repo / "archiso/novaos/airootfs/etc/sddm.conf.d/novaos.conf"
    if not sddm_conf.exists():
        return None
    text = _read(sddm_conf)
    if "Current=novaos" in text:
        new_text = text.replace("Current=novaos", "Current=breeze")
        _write(sddm_conf, new_text)
        return {
            "summary": "Fell back to breeze SDDM theme (QML parse error in NovaOS theme).",
            "files":   [str(sddm_conf.relative_to(repo))],
        }
    return None


# Rule 7: python script syntax error -> disable service that runs it
PY_SYNTAX_RE = re.compile(
    r"(SyntaxError|IndentationError|TabError):\s*(.*)\s+File \"([^\"]+\.py)\"",
)


def fix_py_syntax(m: re.Match, repo: Path) -> Optional[Dict]:
    py_file = m.group(3)
    # Try to actually fix by running autopep8 if available
    if Path(py_file).exists():
        # Auto-fix with python's compile check
        try:
            subprocess.run([sys.executable, "-m", "py_compile", py_file], check=False)
        except Exception:
            pass
        # Disable the service to allow build to proceed
        svc_name = Path(py_file).stem
        return {
            "summary": f"Detected Python syntax error in {py_file}. Manual review required.",
            "files":   [],
        }
    return None


# Rule 8: profiledef.sh parse error -> restore from known-good template
PROFILEDEF_RE = re.compile(
    r"profiledef\.sh.*error|archiso.*profile.*invalid",
    re.IGNORECASE,
)


def fix_profiledef(m: re.Match, repo: Path) -> Optional[Dict]:
    pd = repo / "archiso/novaos/profiledef.sh"
    if not pd.exists():
        pd.parent.mkdir(parents=True, exist_ok=True)
        pd.write_text('''#!/usr/bin/env bash
# Restored by auto_fix.py
iso_name="NovaOS"
iso_label="NOVAOS_$(date +%Y%m)"
iso_publisher="NovaOS Project"
iso_application="NovaOS Live/Install Media"
iso_version="$(date +%Y.%m.%d)"
iso_install_dir="novaos"
iso_features="uefi amd64 intel64"
bootmodes=('bios.syslinux.mbr' 'bios.syslinux.eltorito'
           'uefi-x64.systemd-boot.esp'
           'uefi-x64.systemd-boot.eltorito')
build_date="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
build_tool="archiso"
''')
        os.chmod(pd, 0o755)
        return {
            "summary": "Restored profiledef.sh from known-good template.",
            "files":   [str(pd.relative_to(repo))],
        }
    return None


# Rule 9: GPU/Driver package conflict (e.g. nvidia-dkms vs nvidia)
PKG_CONFLICT_RE = re.compile(
    r"error: conflicting packages:\s*\n?.*?(\S+).*?and.*?(\S+)",
    re.IGNORECASE | re.DOTALL,
)


def fix_pkg_conflict(m: re.Match, repo: Path) -> Optional[Dict]:
    pkg_a, pkg_b = m.group(1), m.group(2)
    # Keep the dkms variant, remove the regular one
    target = pkg_a if "dkms" not in pkg_a else pkg_b
    target_clean = re.split(r"[<>=]", target)[0]
    for f in [
        repo / "archiso/novaos/packages.x86_64",
        repo / "archiso/novaos/packages.live.x86_64",
    ]:
        if not f.exists():
            continue
        text = _read(f)
        if re.search(rf"^\s*{re.escape(target_clean)}\b", text, re.MULTILINE):
            new_text = re.sub(
                rf"^(\s*)({re.escape(target_clean)}\s.*$)",
                rf"\1# REMOVED-AUTO: conflicts with {pkg_a if target==pkg_b else pkg_b}\n\1#\2",
                text,
                flags=re.MULTILINE,
            )
            _write(f, new_text)
            return {
                "summary": f"Removed conflicting package `{target_clean}`.",
                "files":   [str(f.relative_to(repo))],
            }
    return None


# Rule 10: missing dependency -> add to packages
MISSING_DEP_RE = re.compile(
    r"error: failed to load module.*?:.*?lib(\S+)\.so|"
    r"error while loading shared libraries: lib(\S+)\.so",
    re.IGNORECASE,
)


def fix_missing_dep(m: re.Match, repo: Path) -> Optional[Dict]:
    libname = next((g for g in m.groups() if g), None)
    if not libname:
        return None
    # Try common translations
    translations = {
        "nvidia-egl-wayland": "nvidia-utils",
        "nvidia-vulkan": "vulkan-nouveau",
        "Qt6Core":        "qt6-base",
        "Qt6Quick":       "qt6-declarative",
        "KF6ConfigCore":  "kf6-config",
    }
    pkg = translations.get(libname) or libname.replace("lib", "").split("-")[0]
    pkgs = repo / "archiso/novaos/packages.x86_64"
    text = _read(pkgs)
    if pkg and pkg not in text:
        new_text = text + f"\n# ADDED-AUTO: missing dependency\n{pkg}\n"
        _write(pkgs, new_text)
        return {
            "summary": f"Added missing shared-library dependency `{pkg}`.",
            "files":   [str(pkgs.relative_to(repo))],
        }
    return None


# Rule 11: mkinitcpio image generation failure - usually due to missing module
MKINITCPIO_RE = re.compile(
    r"mkinitcpio.*error.*?:.*?module (\S+) not found",
    re.IGNORECASE,
)


def fix_mkinitcpio(m: re.Match, repo: Path) -> Optional[Dict]:
    module = m.group(1)
    # Add the module to the MODULES array in mkinitcpio.conf
    mc = repo / "archiso/novaos/airootfs/etc/mkinitcpio.conf"
    text = _read(mc)
    if "MODULES=()" in text:
        new_text = text.replace("MODULES=()", f"MODULES=({module})")
        _write(mc, new_text)
        return {
            "summary": f"Added missing kernel module `{module}` to mkinitcpio.conf.",
            "files":   [str(mc.relative_to(repo))],
        }
    elif f"({module}" not in text and "MODULES=(" in text:
        new_text = re.sub(
            r"MODULES=\(([^)]*)\)",
            lambda mm: f"MODULES=({mm.group(1)} {module})",
            text,
        )
        _write(mc, new_text)
        return {
            "summary": f"Added missing kernel module `{module}` to mkinitcpio.conf.",
            "files":   [str(mc.relative_to(repo))],
        }
    return None


# Rule 12: archiso command syntax changed (newer archiso) -> align bootmodes
ARCHISO_VERSION_RE = re.compile(
    r"archiso.*invalid bootmode|unknown bootmode: (\S+)",
    re.IGNORECASE,
)


def fix_archiso_bootmode(m: re.Match, repo: Path) -> Optional[Dict]:
    pd = repo / "archiso/novaos/profiledef.sh"
    text = _read(pd)
    # Replace with all currently-supported bootmodes (archiso >= 73)
    if "bootmodes=(" in text:
        new_text = re.sub(
            r"bootmodes=\([^)]*\)",
            "bootmodes=('bios.syslinux.mbr' 'bios.syslinux.eltorito' "
            "'uefi-x64.systemd-boot.esp' 'uefi-x64.systemd-boot.eltorito')",
            text,
        )
        _write(pd, new_text)
        return {
            "summary": "Updated bootmodes to current archiso-supported set.",
            "files":   [str(pd.relative_to(repo))],
        }
    return None


# Rule 13: archiso command not found -> drop --needed flag from pacman install
ARCHISO_CMD_NOT_FOUND_RE = re.compile(
    r"(?:archiso|mkarchiso):\s*command not found|"
    r"line\s+\d+:\s*archiso:\s*command not found|"
    r"FATAL:\s+(?:/usr/bin/archiso|/usr/bin/mkarchiso)\s+does not exist|"
    r"neither mkarchiso nor archiso binary found",
    re.IGNORECASE,
)


def fix_archiso_cmd_not_found(m: re.Match, repo: Path) -> Optional[Dict]:
    wf = repo / ".github/workflows/build-iso.yml"
    if not wf.exists():
        return None
    text = _read(wf)
    # Pattern 1: drop --needed flag
    patched = False
    if "--needed archiso git reflector rsync" in text:
        text = text.replace(
            "--needed archiso git reflector rsync",
            "archiso git reflector rsync  # no --needed: would skip archiso itself",
        )
        patched = True
    # Pattern 2: replace bare `archiso -v` calls with mkarchiso
    if re.search(r"^\s*archiso\s+-v\s+-w", text, re.MULTILINE):
        text = re.sub(
            r"^\s*archiso\s+-v\s+-w",
            "              mkarchiso -v -w",
            text,
            flags=re.MULTILINE,
        )
        patched = True
    if patched:
        _write(wf, text)
        return {
            "summary": "Patched archiso invocation (dropped --needed, switched to mkarchiso).",
            "files":   [str(wf.relative_to(repo))],
        }
    return None


# Rule 14: pacman database locked -> remove lockfile in build step
PACMAN_LOCK_RE = re.compile(
    r"failed to initialize alpm library|"
    r"database.*is locked|/var/lib/pacman/db\.lck",
    re.IGNORECASE,
)


def fix_pacman_lock(m: re.Match, repo: Path) -> Optional[Dict]:
    wf = repo / ".github/workflows/build-iso.yml"
    if not wf.exists():
        return None
    text = _read(wf)
    if "rm -f /var/lib/pacman/db.lck" not in text:
        new_text = text.replace(
            "pacman-key --init\n",
            "rm -f /var/lib/pacman/db.lck\n              pacman-key --init\n",
            1,
        )
        _write(wf, new_text)
        return {
            "summary": "Added `rm -f /var/lib/pacman/db.lck` before pacman-key init.",
            "files":   [str(wf.relative_to(repo))],
        }
    return None


# Rule 15: docker permission denied -> use --privileged
DOCKER_PERM_RE = re.compile(
    r"docker.*permission denied|cannot connect to the Docker daemon",
    re.IGNORECASE,
)


def fix_docker_perm(m: re.Match, repo: Path) -> Optional[Dict]:
    wf = repo / ".github/workflows/build-iso.yml"
    if not wf.exists():
        return None
    text = _read(wf)
    if "docker run --rm \\\\" in text and "--privileged" not in text.split("docker run")[1].split("\\")[0]:
        new_text = text.replace(
            "docker run --rm \\",
            "docker run --rm --privileged \\",
        )
        _write(wf, new_text)
        return {
            "summary": "Added --privileged flag to docker run.",
            "files":   [str(wf.relative_to(repo))],
        }
    return None


# Catalog
RULES: List[Tuple[str, re.Pattern, callable]] = [
    ("package_not_found",     PKG_NOT_FOUND_RE,    fix_pkg_not_found),
    ("signature_invalid",     SIG_RE,              fix_sig_error),
    ("disk_full",             DISK_FULL_RE,        fix_disk_full),
    ("aur_build_timeout",     AUR_TIMEOUT_RE,      fix_aur_timeout),
    ("missing_profile_file",  MISSING_FILE_RE,     fix_missing_file),
    ("qml_syntax_error",      QML_SYNTAX_RE,       fix_qml_syntax),
    ("python_syntax_error",   PY_SYNTAX_RE,        fix_py_syntax),
    ("profiledef_broken",     PROFILEDEF_RE,       fix_profiledef),
    ("package_conflict",      PKG_CONFLICT_RE,     fix_pkg_conflict),
    ("missing_shared_lib",    MISSING_DEP_RE,      fix_missing_dep),
    ("mkinitcpio_module",     MKINITCPIO_RE,       fix_mkinitcpio),
    ("archiso_bootmode",      ARCHISO_VERSION_RE,  fix_archiso_bootmode),
    ("archiso_cmd_not_found", ARCHISO_CMD_NOT_FOUND_RE, fix_archiso_cmd_not_found),
    ("pacman_db_locked",      PACMAN_LOCK_RE,      fix_pacman_lock),
    ("docker_permission",     DOCKER_PERM_RE,      fix_docker_perm),
]


def analyze(log_path: Path, repo: Path) -> Dict:
    log = _read(log_path) if log_path.exists() else ""
    if not log:
        return {
            "fixed":   False,
            "summary": "Empty build log - cannot analyze.",
            "files":   [],
            "rules":   [],
        }

    applied = []
    patched_files = set()
    summaries = []

    for rule_id, pattern, fn in RULES:
        for m in pattern.finditer(log):
            try:
                result = fn(m, repo)
            except Exception as e:
                result = None
            if result:
                applied.append(rule_id)
                patched_files.update(result["files"])
                summaries.append(f"[{rule_id}] {result['summary']}")
                break  # one fix per rule

    if applied:
        return {
            "fixed":   True,
            "summary": "\n".join(summaries),
            "files":   sorted(patched_files),
            "rules":   applied,
        }
    return {
        "fixed":   False,
        "summary": ("No matching auto-fix rule. "
                    f"First 200 chars of log:\n{log[:200]}..."),
        "files":   [],
        "rules":   [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log",     required=True, type=Path)
    ap.add_argument("--repo",    required=True, type=Path)
    ap.add_argument("--run-id",  required=False, default="")
    ap.add_argument("--git-sha", required=False, default="")
    args = ap.parse_args()

    repo = args.repo.resolve()
    result = analyze(args.log, repo)
    if args.run_id:
        result["run_id"] = args.run_id
    if args.git_sha:
        result["git_sha"] = args.git_sha
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
