#!/usr/bin/env python3
"""
NovaOS Hardware Optimizer
=========================
A long-running daemon that continuously tunes the system based on:
  - Detected hardware (CPU/GPU/storage)
  - Live load (CPU%, RAM%, GPU%)
  - Power source (AC vs battery)
  - Thermal headroom

Implements "maximize RAM, CPU, GPU utilisation" requirement.
Designed to run as a systemd service.
"""
from __future__ import annotations

import os
import re
import sys
import time
import json
import subprocess
import logging
import psutil
from pathlib import Path
from typing import Dict, List, Optional

LOG = logging.getLogger("novaos-hw-optim")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/novaos/hardware-optimizer.log"),
    ],
)

STATE = Path("/var/lib/novaos/hw-state.json")
STATE.parent.mkdir(parents=True, exist_ok=True)


# ---------- helpers ----------
def sh(cmd: str, check: bool = False) -> str:
    """Run shell command, return stdout."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        if check and r.returncode != 0:
            raise RuntimeError(f"{cmd!r} failed: {r.stderr.strip()}")
        return r.stdout.strip()
    except Exception as e:
        LOG.warning(f"command failed: {cmd!r} -> {e}")
        return ""


def read_int(path: Path) -> Optional[int]:
    try:
        return int(path.read_text().strip())
    except Exception:
        return None


def write(path: Path, val: str) -> bool:
    try:
        path.write_text(val)
        return True
    except Exception as e:
        LOG.debug(f"cannot write {path}: {e}")
        return False


# ---------- probes ----------
def probe_cpu() -> Dict:
    info = {"vendor": "unknown", "model": "unknown", "cores": os.cpu_count()}
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("vendor_id"):
                    info["vendor"] = line.split(":")[1].strip()
                if line.startswith("model name"):
                    info["model"] = line.split(":")[1].strip()
                    break
    except Exception:
        pass
    return info


def probe_gpus() -> List[Dict]:
    out = sh("lspci -nnk")
    gpus = []
    for block in out.split("\n\n"):
        if not re.search(r"(VGA|3D controller|Display controller)", block, re.I):
            continue
        vendor = "unknown"
        if "AMD" in block or "ATI" in block: vendor = "amd"
        elif "NVIDIA" in block: vendor = "nvidia"
        elif "Intel" in block: vendor = "intel"
        gpus.append({"vendor": vendor, "raw": block.split("\n")[0]})
    return gpus


def probe_power() -> str:
    """Return 'AC' or 'BATTERY'."""
    for path in Path("/sys/class/power_supply").glob("*"):
        try:
            online = (path / "online").read_text().strip()
            if online == "1":
                return "AC"
            if online == "0":
                return "BATTERY"
        except Exception:
            continue
    return "AC"


def probe_thermal() -> float:
    """Return max temperature across all thermal zones in deg-C."""
    max_t = 0.0
    for tz in Path("/sys/class/thermal").glob("thermal_zone*"):
        try:
            t = int((tz / "temp").read_text().strip()) / 1000.0
            if t > max_t:
                max_t = t
        except Exception:
            continue
    return max_t


# ---------- tuners ----------
def set_cpu_governor(profile: str) -> None:
    """profile in {performance, powersave, balanced, schedutil}."""
    target = {
        "performance": "performance",
        "powersave":   "powersave",
        "balanced":    "schedutil" if Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors").read_text().find("schedutil") >= 0 else "powersave",
    }.get(profile, "schedutil")
    for cpu in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor"):
        write(cpu, target)


def set_gpu_performance_level(level: str) -> None:
    """level in {auto, high, low} - works for amdgpu and nvidia."""
    # AMD
    for card in Path("/sys/class/drm").glob("card[0-9]/device/power_dpm_force_performance_level"):
        write(card, level)
    # Nvidia
    if shutil_which("nvidia-smi"):
        sh(f"nvidia-smi -ac {5000},{5000} >/dev/null 2>&1 || true")
        sh(f"nvidia-smi --persistence-mode=1 >/dev/null 2>&1 || true")


def set_swap_preference(enable: bool) -> None:
    """Reduce swappiness to maximise RAM usage (we want max RAM utilisation)."""
    target = "1" if enable else "60"
    write(Path("/proc/sys/vm/swappiness"), target)


def set_io_scheduler() -> None:
    """Pick best scheduler per device."""
    for sched_path in list(Path("/sys/block").glob("sd*/queue/scheduler")) + \
                      list(Path("/sys/block").glob("nvme*n*/queue/scheduler")) + \
                      list(Path("/sys/block").glob("vd*/queue/scheduler")):
        try:
            avail = sched_path.read_text()
        except Exception:
            continue
        if "bfq" in avail and probe_power() == "BATTERY":
            write(sched_path, "bfq")
        elif "mq-deadline" in avail:
            write(sched_path, "mq-deadline")
        elif "kyber" in avail:
            write(sched_path, "kyber")


def set_gpu_clock_offset(offset_mhz: int) -> None:
    """Apply small GPU OC when on AC and thermal headroom is sufficient."""
    if not shutil_which("nvidia-smi"):
        return
    # Safe offset only
    if offset_mhz > 0:
        sh(f"nvidia-smi -ac {5000},{5000} >/dev/null 2>&1 || true")
        sh(f"nvidia-settings -a '[gpu:0]/GPUGraphicsClockOffsetAllPerformanceLevels={offset_mhz}' >/dev/null 2>&1 || true")


def shutil_which(cmd: str) -> bool:
    return bool(sh(f"command -v {cmd}"))


# ---------- main loop ----------
def optimize_once() -> Dict:
    cpu = probe_cpu()
    gpus = probe_gpus()
    power = probe_power()
    thermal = probe_thermal()
    load = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    mem_pct = mem.percent
    mem_avail_gb = mem.available / 1024**3

    LOG.info(f"CPU={cpu['vendor']} load={load:.1f}%  "
             f"GPU={[g['vendor'] for g in gpus]}  "
             f"power={power}  thermal={thermal:.1f}C  "
             f"mem={mem_pct:.1f}% (avail {mem_avail_gb:.1f}GB)")

    # Decide profile
    if power == "AC":
        # Maximise performance on AC
        set_cpu_governor("performance")
        set_gpu_performance_level("high")
        set_swap_preference(enable=True)   # minimises swapping -> max RAM for apps
        if thermal < 75:
            set_gpu_clock_offset(80)       # safe OC
    else:
        # Battery: balanced
        set_cpu_governor("balanced")
        set_gpu_performance_level("auto")
        set_swap_preference(enable=True)
        set_gpu_clock_offset(0)

    set_io_scheduler()

    state = {
        "timestamp": time.time(),
        "cpu": cpu,
        "gpus": gpus,
        "power": power,
        "thermal": thermal,
        "load": load,
        "mem_pct": mem_pct,
        "mem_avail_gb": mem_avail_gb,
    }
    STATE.write_text(json.dumps(state, indent=2))
    return state


def main():
    LOG.info("NovaOS Hardware Optimizer starting…")
    while True:
        try:
            optimize_once()
        except Exception as e:
            LOG.exception(f"loop error: {e}")
        time.sleep(30)


if __name__ == "__main__":
    main()
