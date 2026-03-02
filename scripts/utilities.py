# scripts/utilities.py
# System-level helpers: file listing, size formatting, path resolution,
# purge operations, and system info gathering.

import glob
import os
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
        "ffmpeg":         "not found",
        "encoding":       "mss DXGI -> libx264 via ffmpeg pipe -> RAM buffer",
        "segments":       "pipelined – mux runs in background",
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
        info["ffmpeg_path"] = ffmpeg_path if ffmpeg_path else "not found"
    except Exception:
        info["ffmpeg_status"] = "Missing"
        info["ffmpeg_path"] = "not found"

    return info