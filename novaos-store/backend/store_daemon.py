#!/usr/bin/env python3
"""
NovaOS Store - Backend Daemon
==============================
A single daemon that exposes a D-Bus / HTTP API for:
  - Listing installable applications (AppStream data + curated catalog)
  - Installing apps via pacman / paru / flatpak / snap
  - Running Windows apps via Wine/Bottles/Proton with one click
  - Tracking updates and notifying the desktop

The frontend (PyQt6 GUI) talks to this daemon over a UNIX socket.
"""
from __future__ import annotations

import os
import sys
import json
import time
import socket
import shutil
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

LOG = logging.getLogger("novaos-store")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/novaos/store.log"),
    ],
)

SOCK = Path("/run/novaos/store.sock")
CATALOG = Path("/usr/share/novaos/store/catalog.json")
STATE = Path("/var/lib/novaos/store-state.json")
STATE.parent.mkdir(parents=True, exist_ok=True)

UPDATE_INTERVAL = 600  # 10 minutes


# ---------- package backends ----------
class Backend:
    name = "abstract"

    def search(self, query: str) -> List[Dict]:
        return []

    def install(self, pkgid: str) -> bool:
        return False

    def remove(self, pkgid: str) -> bool:
        return False

    def list_installed(self) -> List[Dict]:
        return []


class PacmanBackend(Backend):
    name = "pacman"

    def search(self, query: str) -> List[Dict]:
        out = subprocess.run(
            ["pacman", "-Ss", "^" + query],
            capture_output=True, text=True, timeout=15
        ).stdout
        results = []
        for line in out.splitlines():
            if not line or line.startswith(" "):
                continue
            try:
                repo, rest = line.split("/", 1)
                name, ver = rest.split(" ", 1)
                desc = ""
                # next line is the description
                results.append({"id": name, "name": name, "version": ver,
                                "repo": repo, "backend": self.name,
                                "description": desc})
            except Exception:
                continue
        return results

    def install(self, pkgid: str) -> bool:
        r = subprocess.run(
            ["pacman", "-S", "--noconfirm", "--needed", pkgid],
            capture_output=True, text=True, timeout=600
        )
        return r.returncode == 0

    def remove(self, pkgid: str) -> bool:
        r = subprocess.run(
            ["pacman", "-R", "--noconfirm", pkgid],
            capture_output=True, text=True, timeout=120
        )
        return r.returncode == 0

    def list_installed(self) -> List[Dict]:
        out = subprocess.run(
            ["pacman", "-Q"], capture_output=True, text=True
        ).stdout
        return [{"id": l.split()[0], "version": l.split()[1] if len(l.split()) > 1 else "",
                 "backend": self.name} for l in out.splitlines() if l]


class AURBackend(Backend):
    name = "aur"

    def search(self, query: str) -> List[Dict]:
        if not shutil.which("paru"):
            return []
        out = subprocess.run(
            ["paru", "-Ss", query, "--aur"],
            capture_output=True, text=True, timeout=30
        ).stdout
        results = []
        for line in out.splitlines():
            if line.startswith(" ") or not line:
                continue
            try:
                repo, rest = line.split("/", 1)
                name, ver = rest.split(" ", 1)
                results.append({"id": name, "name": name, "version": ver,
                                "repo": "aur", "backend": self.name})
            except Exception:
                continue
        return results

    def install(self, pkgid: str) -> bool:
        if not shutil.which("paru"):
            return False
        r = subprocess.run(
            ["paru", "-S", "--noconfirm", "--needed", pkgid],
            capture_output=True, text=True, timeout=1200,
            input="y\ny\ny\ny\n"
        )
        return r.returncode == 0

    def remove(self, pkgid: str) -> bool:
        if not shutil.which("paru"):
            return False
        r = subprocess.run(
            ["paru", "-R", "--noconfirm", pkgid],
            capture_output=True, text=True, timeout=120
        )
        return r.returncode == 0


class FlatpakBackend(Backend):
    name = "flatpak"

    def search(self, query: str) -> List[Dict]:
        if not shutil.which("flatpak"):
            return []
        out = subprocess.run(
            ["flatpak", "search", query],
            capture_output=True, text=True, timeout=30
        ).stdout
        results = []
        for line in out.splitlines()[1:]:  # skip header
            parts = [p.strip() for p in line.split("\t")]
            if len(parts) >= 4:
                results.append({"id": parts[1], "name": parts[0], "version": parts[2],
                                "repo": parts[3], "backend": self.name})
        return results

    def install(self, pkgid: str) -> bool:
        if not shutil.which("flatpak"):
            return False
        r = subprocess.run(
            ["flatpak", "install", "-y", "--noninteractive", "flathub", pkgid],
            capture_output=True, text=True, timeout=900
        )
        return r.returncode == 0

    def remove(self, pkgid: str) -> bool:
        if not shutil.which("flatpak"):
            return False
        r = subprocess.run(
            ["flatpak", "uninstall", "-y", pkgid],
            capture_output=True, text=True, timeout=120
        )
        return r.returncode == 0


class WindowsBackend(Backend):
    """Run Windows programs via Wine/Bottles/Proton."""
    name = "windows"

    def search(self, query: str) -> List[Dict]:
        # Curated list of popular Windows apps users want one-click install
        catalog = [
            {"id": "notepad++",  "name": "Notepad++",  "category": "Editor",
             "exe_url": "https://github.com/notepad-plus-plus/notepad-plus-plus/releases/latest/download/npp.8.x.x.Installer.x64.exe"},
            {"id": "7zip",       "name": "7-Zip",      "category": "Utility",
             "exe_url": "https://www.7-zip.org/a/7z2407-x64.exe"},
            {"id": "vlc-win",    "name": "VLC (Win)",  "category": "Media",
             "exe_url": "https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.exe"},
            {"id": "office",     "name": "Microsoft Office (via Bottles)", "category": "Office",
             "exe_url": "manual"},
        ]
        return [c for c in catalog if query.lower() in c["name"].lower()]

    def install(self, pkgid: str) -> bool:
        """Downloads the .exe and sets up a Bottles runner."""
        if not shutil.which("bottles"):
            subprocess.run(["pacman", "-S", "--noconfirm", "--needed", "bottles"], check=False)
        if pkgid in ("notepad++", "7zip", "vlc-win"):
            # Use wine directly with a fresh prefix
            prefix = Path.home() / ".novaos" / "wine" / pkgid
            prefix.mkdir(parents=True, exist_ok=True)
            # Use the curated URL
            catalog = {c["id"]: c for c in self.search("")}
            entry = catalog.get(pkgid)
            if not entry:
                return False
            exe = prefix / "installer.exe"
            subprocess.run(["curl", "-fsSL", "-o", str(exe), entry["exe_url"]], check=False)
            env = {**os.environ, "WINEPREFIX": str(prefix)}
            subprocess.run(["wine", str(exe)], env=env, check=False)
            return True
        if pkgid == "office":
            subprocess.run(["bottles"], check=False)
            return True
        return False


# ---------- store daemon ----------
class StoreDaemon:
    def __init__(self):
        self.backends = [
            PacmanBackend(),
            AURBackend(),
            FlatpakBackend(),
            WindowsBackend(),
        ]

    def search(self, query: str) -> List[Dict]:
        results = []
        for b in self.backends:
            try:
                results.extend(b.search(query))
            except Exception as e:
                LOG.warning(f"backend {b.name} search failed: {e}")
        return results

    def install(self, pkgid: str, backend: str = "auto") -> bool:
        for b in self.backends:
            if backend == "auto" or b.name == backend:
                try:
                    ok = b.install(pkgid)
                    if ok:
                        LOG.info(f"installed {pkgid} via {b.name}")
                        return True
                except Exception as e:
                    LOG.warning(f"backend {b.name} install failed: {e}")
        return False

    def remove(self, pkgid: str, backend: str) -> bool:
        for b in self.backends:
            if b.name == backend:
                try:
                    return b.remove(pkgid)
                except Exception as e:
                    LOG.warning(f"backend {b.name} remove failed: {e}")
        return False

    def list_installed(self) -> List[Dict]:
        out = []
        for b in self.backends:
            try:
                out.extend(b.list_installed())
            except Exception:
                continue
        return out

    def update_all(self) -> Dict:
        results = {"pacman": None, "aur": None, "flatpak": None}
        if shutil.which("pacman"):
            r = subprocess.run(["pacman", "-Syu", "--noconfirm"],
                               capture_output=True, text=True, timeout=900)
            results["pacman"] = r.returncode == 0
        if shutil.which("paru"):
            r = subprocess.run(["paru", "-Syu", "--noconfirm", "--needed"],
                               capture_output=True, text=True, timeout=1800,
                               input="y\ny\ny\ny\n")
            results["aur"] = r.returncode == 0
        if shutil.which("flatpak"):
            r = subprocess.run(["flatpak", "update", "-y"],
                               capture_output=True, text=True, timeout=900)
            results["flatpak"] = r.returncode == 0
        return results

    def handle_request(self, req: Dict) -> Dict:
        action = req.get("action")
        if action == "search":
            return {"ok": True, "results": self.search(req.get("query", ""))}
        if action == "install":
            ok = self.install(req.get("pkgid", ""), req.get("backend", "auto"))
            return {"ok": ok}
        if action == "remove":
            ok = self.remove(req.get("pkgid", ""), req.get("backend", "pacman"))
            return {"ok": ok}
        if action == "list_installed":
            return {"ok": True, "results": self.list_installed()}
        if action == "update_all":
            return {"ok": True, "results": self.update_all()}
        return {"ok": False, "error": "unknown action"}


def serve(daemon: StoreDaemon):
    SOCK.parent.mkdir(parents=True, exist_ok=True)
    if SOCK.exists():
        SOCK.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(SOCK))
    srv.listen(8)
    SOCK.chmod(0o660)
    LOG.info(f"listening on {SOCK}")
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_client, args=(daemon, conn), daemon=True).start()


def handle_client(daemon: StoreDaemon, conn: socket.socket):
    try:
        conn.settimeout(1800)  # 30-min for installs
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(65536)
            if not chunk:
                return
            buf += chunk
        req = json.loads(buf.decode("utf-8"))
        LOG.info(f"req: {req.get('action')}")
        resp = daemon.handle_request(req)
        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
    except Exception as e:
        LOG.exception(f"client error: {e}")
        try:
            conn.sendall((json.dumps({"ok": False, "error": str(e)}) + "\n").encode("utf-8"))
        except Exception:
            pass
    finally:
        conn.close()


def auto_update_thread(daemon: StoreDaemon):
    """Periodically check for updates."""
    while True:
        time.sleep(UPDATE_INTERVAL)
        try:
            daemon.update_all()
        except Exception as e:
            LOG.warning(f"auto-update failed: {e}")


def main():
    daemon = StoreDaemon()
    threading.Thread(target=auto_update_thread, args=(daemon,), daemon=True).start()
    serve(daemon)


if __name__ == "__main__":
    main()
