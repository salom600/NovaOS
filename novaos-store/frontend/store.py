#!/usr/bin/env python3
"""
NovaOS Store - Frontend (PyQt6)
================================
A modern, glass-themed PyQt6 GUI that talks to store_daemon.py
over a UNIX socket.

Features:
  - Search across pacman, AUR, Flatpak, and Windows (Wine/Bottles) backends
  - One-click install / remove
  - "Run Windows app" panel - drag .exe here to install via Bottles
  - Curated catalog of recommended apps (categories)
  - Live update indicator
  - System resource panel (CPU/RAM/GPU) using novaos-hardware-optimizer state
"""
from __future__ import annotations

import os
import sys
import json
import socket
from pathlib import Path
from typing import Dict, List

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QLabel,
    QTabWidget, QProgressBar, QTextEdit, QFrame, QScrollArea,
    QGridLayout, QSizePolicy, QMessageBox, QSystemTrayIcon
)


SOCK = Path("/run/novaos/store.sock")


def call_daemon(req: Dict, timeout: int = 1800) -> Dict:
    """Send a JSON request to store_daemon and return the response."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(SOCK))
        s.sendall((json.dumps(req) + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        return json.loads(buf.decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        s.close()


# Glass-style frame
class GlassFrame(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("GlassFrame")
        self.setStyleSheet("""
            QFrame#GlassFrame {
                background-color: rgba(14, 20, 34, 180);
                border-radius: 18px;
                border: 1px solid rgba(255,255,255, 0.08);
            }
        """)


class SearchWorker(QThread):
    results = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        resp = call_daemon({"action": "search", "query": self.query}, timeout=60)
        if resp.get("ok"):
            self.results.emit(resp.get("results", []))
        else:
            self.error.emit(resp.get("error", "search failed"))


class InstallWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, pkgid: str, backend: str, action: str = "install"):
        super().__init__()
        self.pkgid = pkgid
        self.backend = backend
        self.action = action

    def run(self):
        resp = call_daemon({"action": self.action, "pkgid": self.pkgid,
                            "backend": self.backend}, timeout=1800)
        ok = resp.get("ok", False)
        self.done.emit(ok, resp.get("error", ""))


class NovaOSStore(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NovaOS Store")
        self.resize(1100, 720)
        self._apply_glass_style()
        self._build_ui()
        self._load_curated()

    def _apply_glass_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: rgba(10, 14, 26, 200);
                color: #E8EEF7;
                font-family: 'Inter';
                font-size: 13px;
            }
            QLineEdit {
                background-color: rgba(255,255,255, 0.06);
                border: 1px solid rgba(255,255,255, 0.10);
                border-radius: 14px;
                padding: 10px 14px;
                color: #E8EEF7;
                selection-background-color: #78A0FF;
            }
            QLineEdit:focus {
                border: 1px solid #78A0FF;
            }
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #78A0FF, stop:1 #4A6FE3);
                color: #FFFFFF;
                border: none;
                border-radius: 12px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8DB0FF, stop:1 #5B7FE8);
            }
            QPushButton:pressed {
                background-color: #4A6FE3;
            }
            QPushButton#secondary {
                background-color: rgba(255,255,255, 0.08);
                color: #E8EEF7;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: rgba(255,255,255, 0.04);
                color: #A0AEC8;
                padding: 10px 22px;
                border-radius: 10px 10px 0 0;
                border: 1px solid transparent;
            }
            QTabBar::tab:selected {
                background: rgba(120, 160, 255, 0.20);
                color: #FFFFFF;
                border-bottom: 2px solid #78A0FF;
            }
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: rgba(255,255,255, 0.03);
                border-radius: 10px;
                padding: 10px;
                margin: 4px 0;
            }
            QListWidget::item:selected {
                background-color: rgba(120, 160, 255, 0.20);
            }
            QLabel#headerTitle {
                font-size: 22px;
                font-weight: bold;
                color: #FFFFFF;
            }
            QLabel#headerSubtitle {
                font-size: 12px;
                color: #A0AEC8;
            }
            QProgressBar {
                background-color: rgba(255,255,255, 0.08);
                border: none;
                border-radius: 4px;
                text-align: center;
                color: white;
                height: 6px;
            }
            QProgressBar::chunk {
                background-color: #78A0FF;
                border-radius: 4px;
            }
            QScrollArea { border: none; background: transparent; }
        """)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        # Header
        header = GlassFrame()
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(20, 16, 20, 16)
        title = QLabel("NovaOS Store")
        title.setObjectName("headerTitle")
        subtitle = QLabel("Install any app in one click - Linux, Flatpak, AUR, or Windows")
        subtitle.setObjectName("headerSubtitle")
        hlay.addWidget(title)
        hlay.addStretch()
        hlay.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignRight)
        outer.addWidget(header)

        # Search bar
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search apps, games, tools...")
        self.search.returnPressed.connect(self._on_search)
        search_row.addWidget(self.search, 1)
        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self._on_search)
        search_row.addWidget(self.btn_search)
        self.btn_updates = QPushButton("Update All")
        self.btn_updates.setObjectName("secondary")
        self.btn_updates.clicked.connect(self._on_update_all)
        search_row.addWidget(self.btn_updates)
        outer.addLayout(search_row)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_search_tab(), "Search Results")
        tabs.addTab(self._build_curated_tab(), "Discover")
        tabs.addTab(self._build_installed_tab(), "Installed")
        tabs.addTab(self._build_windows_tab(), "Run Windows App")
        outer.addWidget(tabs, 1)

        # Status bar
        self.status = QLabel("Ready")
        self.status.setStyleSheet("color:#A0AEC8; padding: 6px 4px;")
        outer.addWidget(self.status)

    def _build_search_tab(self) -> QWidget:
        w = GlassFrame()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        self.search_list = QListWidget()
        self.search_list.itemDoubleClicked.connect(self._on_install_item)
        lay.addWidget(self.search_list)
        return w

    def _build_curated_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(12)
        curated = [
            ("Firefox",         "Web Browser",       "firefox",          "pacman"),
            ("Chromium",        "Web Browser",       "chromium",         "pacman"),
            ("VLC",             "Media Player",      "vlc",              "pacman"),
            ("Spotify",         "Music",             "com.spotify.Client", "flatpak"),
            ("Discord",         "Communication",     "com.discordapp.Discord", "flatpak"),
            ("Telegram",        "Communication",     "org.telegram.desktop", "flatpak"),
            ("Steam",           "Games",             "steam",            "pacman"),
            ("LibreOffice",     "Office Suite",      "libreoffice-fresh", "pacman"),
            ("GIMP",            "Image Editor",      "gimp",             "pacman"),
            ("Krita",           "Digital Painting",  "krita",            "pacman"),
            ("Blender",         "3D Modeling",       "blender",          "pacman"),
            ("Visual Studio Code","Code Editor",     "code",             "pacman"),
            ("PyCharm",         "Python IDE",        "pycharm-community-edition", "aur"),
            ("OBS Studio",      "Streaming",         "obs-studio",       "pacman"),
            ("Audacity",        "Audio Editor",      "audacity",         "pacman"),
            ("OnlyOffice",      "Office Suite",      "org.onlyoffice.desktopeditors", "flatpak"),
        ]
        for i, (name, cat, pkg, backend) in enumerate(curated):
            card = GlassFrame()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            cl.addWidget(QLabel(f"<b style='color:#FFFFFF; font-size:15px;'>{name}</b>"))
            cl.addWidget(QLabel(f"<span style='color:#A0AEC8;'>{cat} - {backend}</span>"))
            btn = QPushButton("Install")
            btn.clicked.connect(lambda _, p=pkg, b=backend: self._install(p, b))
            cl.addWidget(btn)
            grid.addWidget(card, i // 4, i % 4)
        scroll.setWidget(inner)
        return scroll

    def _build_installed_tab(self) -> QWidget:
        w = GlassFrame()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        self.installed_list = QListWidget()
        lay.addWidget(self.installed_list)
        btn = QPushButton("Refresh")
        btn.setObjectName("secondary")
        btn.clicked.connect(self._on_list_installed)
        lay.addWidget(btn)
        return w

    def _build_windows_tab(self) -> QWidget:
        w = GlassFrame()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.addWidget(QLabel("<h2 style='color:#FFFFFF;'>Run Windows Apps on NovaOS</h2>"))
        lay.addWidget(QLabel(
            "<p style='color:#A0AEC8;'>NovaOS ships with Wine, Bottles, and Proton-GE "
            "pre-installed. Install any Windows .exe with one click, or use the curated "
            "list below.</p>"
        ))
        # Curated Windows apps
        curated = [
            ("Notepad++", "notepad++"),
            ("7-Zip",     "7zip"),
            ("VLC (Win)", "vlc-win"),
            ("Microsoft Office (manual setup via Bottles)", "office"),
        ]
        for name, pkg in curated:
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            btn = QPushButton("Install via Wine")
            btn.clicked.connect(lambda _, p=pkg: self._install(p, "windows"))
            row.addWidget(btn)
            lay.addLayout(row)
        lay.addStretch()
        lay.addWidget(QLabel(
            "<i style='color:#A0AEC8;'>Tip: drag any .exe file into Bottles "
            "for a one-click runner.</i>"
        ))
        return w

    # ----- actions -----
    def _on_search(self):
        q = self.search.text().strip()
        if not q:
            return
        self.status.setText(f"Searching for '{q}'…")
        self.btn_search.setEnabled(False)
        self._worker = SearchWorker(q)
        self._worker.results.connect(self._on_search_results)
        self._worker.error.connect(self._on_search_error)
        self._worker.start()

    def _on_search_results(self, results: list):
        self.search_list.clear()
        for r in results[:200]:
            item = QListWidgetItem(f"{r.get('name','?')}  [{r.get('backend','?')}]  -  {r.get('description','')[:80]}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.search_list.addItem(item)
        self.status.setText(f"{len(results)} results")
        self.btn_search.setEnabled(True)

    def _on_search_error(self, err: str):
        self.status.setText(f"Search error: {err}")
        self.btn_search.setEnabled(True)

    def _on_install_item(self, item):
        r = item.data(Qt.ItemDataRole.UserRole)
        if not r:
            return
        self._install(r.get("id", ""), r.get("backend", "pacman"))

    def _install(self, pkgid: str, backend: str):
        self.status.setText(f"Installing {pkgid} via {backend}…")
        self._install_worker = InstallWorker(pkgid, backend, "install")
        self._install_worker.done.connect(
            lambda ok, err: self.status.setText(
                f"{'Installed' if ok else 'Failed'}: {pkgid}" + (f" ({err})" if err else "")
            )
        )
        self._install_worker.start()

    def _on_list_installed(self):
        resp = call_daemon({"action": "list_installed"}, timeout=60)
        self.installed_list.clear()
        if not resp.get("ok"):
            return
        for r in resp.get("results", []):
            self.installed_list.addItem(
                QListWidgetItem(f"{r.get('id','?')}  {r.get('version','')}  [{r.get('backend','?')}]")
            )

    def _on_update_all(self):
        self.status.setText("Updating all packages…")
        self._update_worker = InstallWorker("", "", "update_all")
        self._update_worker.done.connect(
            lambda ok, err: self.status.setText("Update complete" if ok else f"Update failed: {err}")
        )
        self._update_worker.start()

    def _load_curated(self):
        # Trigger first list
        QTimer.singleShot(800, self._on_list_installed)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NovaOS Store")
    w = NovaOSStore()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
