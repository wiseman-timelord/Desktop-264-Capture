# scripts/utilities.py
# System-level helpers: file listing, size formatting, path resolution,
# purge operations, system info gathering, and hardware detection.

import glob
import os
import subprocess
import sys
import time

import scripts.configure as configure

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT = "Output"
VIDEO_PREFIX   = "Desktop_Video_"

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def fmt_bytes(n: int) -> str:
    """Human-readable file size."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    else:
        return f"{n / 1024 ** 3:.2f} GB"


def fmt_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    return time.strftime("%H:%M:%S", time.gmtime(int(seconds)))


# ---------------------------------------------------------------------------
# Output path resolution
# ---------------------------------------------------------------------------
def resolve_output_path(user_input: str):
    """
    Accept any valid directory path the user provides.
    - Absolute paths are accepted directly.
    - Relative paths are resolved relative to .\\Output\\.
    - Blank input returns None.
    """
    if not user_input:
        return None

    raw  = user_input.strip()
    norm = os.path.normpath(raw)

    if os.path.isabs(norm):
        return norm

    parts = norm.split(os.sep)
    if parts[0].lower() == DEFAULT_OUTPUT.lower():
        return norm
    return os.path.join(DEFAULT_OUTPUT, norm)


def display_path(out_path: str) -> str:
    """Friendly display: relative with .\\ prefix when inside cwd, else full."""
    try:
        rel = os.path.relpath(out_path)
        if not rel.startswith(".."):
            return f".\\{rel}"
    except ValueError:
        pass
    return out_path


# ---------------------------------------------------------------------------
# File listing
# ---------------------------------------------------------------------------
def list_videos(output_path: str) -> list:
    """
    Return a list of dicts for Desktop_Video_* files in output_path,
    sorted newest-first by modification time.
    Each dict: {"name": str, "size": int, "size_str": str, "mtime": float,
                "path": str, "date": str}
    """
    if not os.path.isdir(output_path):
        return []

    pattern = os.path.join(output_path, f"{VIDEO_PREFIX}*")
    files   = glob.glob(pattern)

    entries = []
    for fp in files:
        if os.path.isfile(fp):
            stat = os.stat(fp)
            entries.append({
                "name":     os.path.basename(fp),
                "size":     stat.st_size,
                "size_str": fmt_bytes(stat.st_size),
                "mtime":    stat.st_mtime,
                "path":     fp,
                "date":     time.strftime(
                    "%Y-%m-%d  %H:%M", time.localtime(stat.st_mtime)
                ),
            })

    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries


# ---------------------------------------------------------------------------
# Purge recordings
# ---------------------------------------------------------------------------
def purge_recordings(output_path: str) -> tuple:
    """
    Delete all Desktop_Video_* files in output_path.
    Returns (deleted_count, total_count, error_messages).
    """
    videos = list_videos(output_path)
    if not videos:
        return 0, 0, []

    deleted = 0
    errors  = []
    for v in videos:
        try:
            os.remove(v["path"])
            deleted += 1
        except OSError as e:
            errors.append(f"Could not delete {v['name']}: {e}")

    return deleted, len(videos), errors


# ---------------------------------------------------------------------------
# System information
# ---------------------------------------------------------------------------
def get_system_info() -> dict:
    """Gather system information for display in the GUI."""
    info = {
        "python_version": sys.version.split()[0],
        "cpu_name":       "Unknown",
        "logical_cores":  os.cpu_count() or 1,
        "simd_flags":     "none detected",
        "thread_cap":     0,
        "reserved":       0,
        "opencv":         "not installed",
        "mss":            "not installed",
    }

    try:
        from scripts import recorder
        ci = recorder.get_cpu_info()
        info["cpu_name"]     = ci.get("name", "Unknown")
        info["logical_cores"] = ci.get("logical_cores", os.cpu_count() or 1)
        info["thread_cap"]    = ci.get("thread_cap", recorder._thread_cap)
        info["reserved"]      = info["logical_cores"] - info["thread_cap"]

        simd_parts = []
        if ci.get("sse2"):    simd_parts.append("SSE2")
        if ci.get("avx"):     simd_parts.append("AVX")
        if ci.get("avx2"):    simd_parts.append("AVX2")
        if ci.get("avx512f"): simd_parts.append("AVX-512F")
        if simd_parts:
            info["simd_flags"] = ", ".join(simd_parts)
    except Exception:
        pass

    try:
        import cv2
        info["opencv"] = cv2.__version__
    except ImportError:
        pass

    try:
        import mss as _mss
        info["mss"] = "available"
    except ImportError:
        pass

    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        info["ffmpeg_status"] = "Present" if ffmpeg_path else "Missing"
        info["ffmpeg_path"]   = ffmpeg_path if ffmpeg_path else "not found"
    except Exception:
        info["ffmpeg_status"] = "Missing"
        info["ffmpeg_path"]   = "not found"

    return info


# ===========================================================================
# Live resource monitoring
# ===========================================================================
def get_cpu_usage_percent() -> float:
    """Return current CPU usage percentage."""
    try:
        import psutil
        return psutil.cpu_percent(interval=0.1)
    except ImportError:
        return -1.0
    except Exception:
        return -1.0


def get_ram_assignment_info(config: dict) -> tuple:
    """
    Return (assigned_mb, used_mb, free_assigned_mb, percent_used).
    assigned_mb = Free RAM * (max_ram_usage% / 100)
    used_mb = Current segment buffer size (from recorder)
    free_assigned_mb = assigned_mb - used_mb
    percent_used = (used_mb / assigned_mb) * 100
    """
    try:
        import psutil
        from scripts import recorder

        mem = psutil.virtual_memory()
        free_ram_mb = mem.available / (1024 * 1024)

        max_ram_pct = config.get("max_ram_usage", 50)
        assigned_mb = (free_ram_mb * max_ram_pct) / 100

        used_mb = 0.0
        if hasattr(recorder, '_current_video_buf') and recorder._current_video_buf:
            used_mb = recorder._current_video_buf.ram_size_mb

        free_assigned_mb = max(0, assigned_mb - used_mb)
        percent_used = (used_mb / assigned_mb * 100) if assigned_mb > 0 else 0

        return (assigned_mb, used_mb, free_assigned_mb, percent_used)
    except ImportError:
        return (-1.0, -1.0, -1.0, -1.0)
    except Exception:
        return (-1.0, -1.0, -1.0, -1.0)


# ===========================================================================
# Hardware detection  (displays + GPUs)
# ===========================================================================
def detect_gpus() -> list:
    """
    Enumerate display adapters via PowerShell Get-CimInstance (preferred)
    with a WMIC fallback.  Returns a list of unique adapter names.
    Filters out obvious virtual / remote adapters.
    """
    names = []
    skip_keywords = (
        "remote", "microsoft basic", "virtual", "mirror", "rdp",
        "teamviewer", "vnc", "parsec",
    )

    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_VideoController | "
            "Select-Object -ExpandProperty Name"
        ]
        out = subprocess.check_output(
            cmd, text=True, timeout=15, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            name = line.strip()
            if not name:
                continue
            low = name.lower()
            if any(k in low for k in skip_keywords):
                continue
            if name not in names:
                names.append(name)
    except Exception:
        pass

    if not names:
        try:
            out = subprocess.check_output(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                text=True, timeout=15, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                name = line.strip()
                if not name or name.lower() == "name":
                    continue
                low = name.lower()
                if any(k in low for k in skip_keywords):
                    continue
                if name not in names:
                    names.append(name)
        except Exception:
            pass

    return names


def detect_displays() -> list:
    """
    Return a list of monitor dicts using mss.
    Indices 1..N are physical monitors (index 0 is the virtual desktop and
    is skipped for the selection list).
    Each entry: {
        "index": int, "label": str, "width": int, "height": int,
        "left": int, "top": int, "is_primary": bool
    }
    """
    result = []
    try:
        import mss
        with mss.mss() as sct:
            for idx, mon in enumerate(sct.monitors):
                if idx == 0:
                    continue  # skip combined virtual desktop
                w = mon.get("width", 0)
                h = mon.get("height", 0)
                left = mon.get("left", 0)
                top  = mon.get("top", 0)
                is_primary = mon.get("is_primary", False) or (left == 0 and top == 0)
                primary_tag = " (Primary)" if is_primary else ""
                label = f"Monitor {idx}: {w}x{h}{primary_tag}"
                result.append({
                    "index":      idx,
                    "label":      label,
                    "width":      w,
                    "height":     h,
                    "left":       left,
                    "top":        top,
                    "is_primary": is_primary,
                })
    except Exception:
        result.append({
            "index": 1, "label": "Monitor 1: 1920x1080 (Primary)",
            "width": 1920, "height": 1080, "left": 0, "top": 0,
            "is_primary": True,
        })
    return result


def get_display_labels() -> list:
    """Return just the human-readable labels for the Configure dropdown."""
    return [d["label"] for d in detect_displays()]


def display_index_from_label(label: str) -> int:
    """Map a dropdown label back to the mss monitor index (default 1)."""
    for d in detect_displays():
        if d["label"] == label:
            return d["index"]
    try:
        if label and label.lower().startswith("monitor "):
            part = label.split(":")[0].strip()
            return int(part.split()[-1])
    except Exception:
        pass
    return 1
