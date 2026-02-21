# scripts/configure.py
# Runtime state, option tables, and persistent configuration I/O.

import json
import os
import sys

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
is_recording         = False
recording_start_time = None

# ---------------------------------------------------------------------------
# Option tables
# ---------------------------------------------------------------------------
codecs = ["X264"]

resolutions = [
    {"width": 1920, "height": 1080},   # 1080p
    {"width": 1280, "height": 720},    # 720p
    {"width": 854,  "height": 480},    # 480p
]

fps_options = [30, 45, 60]

# ---------------------------------------------------------------------------
# Video compression profiles
# ---------------------------------------------------------------------------
# Each profile maps to libx264 params passed to ffmpeg during mux.
# Research-backed: CRF controls quality/size, preset controls CPU/speed,
# mpdecimate + vfr drop duplicate frames (huge savings on static screens),
# zerolatency eliminates buffering delay, yuv420p ensures compatibility.
#
# Key: "good_quality" / "optimal_performance" / "high_compression"
video_compression_options = ["Good Quality", "Optimal Performance", "High Compression"]

VIDEO_COMPRESSION = {
    "Good Quality": {
        "label":       "Good Quality",
        "description": "Near-lossless, crisp text/UI detail. Larger files.",
        "preset":      "veryfast",
        "crf":         "18",
        "tune":        "zerolatency",
        "pix_fmt":     "yuv420p",
    },
    "Optimal Performance": {
        "label":       "Optimal Performance",
        "description": "Balanced quality and file size. Recommended default.",
        "preset":      "veryfast",
        "crf":         "22",
        "tune":        "zerolatency",
        "pix_fmt":     "yuv420p",
    },
    "High Compression": {
        "label":       "High Compression",
        "description": "Smallest files, fastest CPU. Minor artifacts possible.",
        "preset":      "ultrafast",
        "crf":         "25",
        "tune":        "zerolatency",
        "pix_fmt":     "yuv420p",
    },
}

# ---------------------------------------------------------------------------
# Audio compression profiles
# ---------------------------------------------------------------------------
# AAC encoder via ffmpeg.  Profile controls the bitrate floor/ceiling
# applied on top of the user-selected audio bitrate.
# "Good Quality"          -> user bitrate as-is (highest fidelity)
# "Optimal Performance"   -> user bitrate (balanced, same numeric but
#                            flagged so UI can advise; no extra penalty)
# "High Compression"      -> caps bitrate to save space
audio_compression_options = ["Good Quality", "Optimal Performance", "High Compression"]

AUDIO_COMPRESSION = {
    "Good Quality": {
        "label":       "Good Quality",
        "description": "Full fidelity at selected bitrate.",
        "bitrate_cap": None,        # no cap – use selected bitrate as-is
    },
    "Optimal Performance": {
        "label":       "Optimal Performance",
        "description": "Balanced. Caps at 192 kbps if higher is selected.",
        "bitrate_cap": 192,
    },
    "High Compression": {
        "label":       "High Compression",
        "description": "Smallest audio. Caps at 128 kbps.",
        "bitrate_cap": 128,
    },
}

# ---------------------------------------------------------------------------
# Audio bitrate options (kbps)
# ---------------------------------------------------------------------------
audio_bitrate_options = [96, 128, 160, 192, 256]

# ---------------------------------------------------------------------------
# Helper: resolve effective audio bitrate
# ---------------------------------------------------------------------------
def effective_audio_bitrate(config: dict) -> int:
    """Return the actual audio bitrate after applying the compression cap."""
    selected = config.get("audio_bitrate", 192)
    profile  = config.get("audio_compression", "Optimal Performance")
    cap      = AUDIO_COMPRESSION.get(profile, {}).get("bitrate_cap")
    if cap is not None:
        return min(selected, cap)
    return selected


def get_video_params(config: dict) -> list:
    """
    Build the list of ffmpeg output args for video encoding based on
    the active video-compression profile.
    Returns a list like ['-preset', 'veryfast', '-crf', '22', ...].
    """
    profile = config.get("video_compression", "Optimal Performance")
    vp      = VIDEO_COMPRESSION.get(profile, VIDEO_COMPRESSION["Optimal Performance"])
    return [
        "-preset",  vp["preset"],
        "-crf",     vp["crf"],
        "-tune",    vp["tune"],
        "-pix_fmt", vp["pix_fmt"],
    ]

# ---------------------------------------------------------------------------
# Persistent configuration  (.\data\persistent.json)
# ---------------------------------------------------------------------------
PERSISTENT_PATH = os.path.join("data", "persistent.json")

DEFAULT_CONFIG = {
    "resolution":        {"width": 1920, "height": 1080},
    "fps":               30,
    "codec":             "X264",
    "output_path":       "Output",
    "video_compression": "Optimal Performance",
    "audio_compression": "Optimal Performance",
    "audio_bitrate":     192,
}


def load_configuration() -> dict:
    """
    Load and return the configuration from persistent.json.
    Missing keys are filled from DEFAULT_CONFIG so older configs
    still work after an update.
    Exits with an error message if the file is missing entirely.
    """
    try:
        with open(PERSISTENT_PATH, "r") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print(f"Error: {PERSISTENT_PATH} not found.  Please run the installer.")
        sys.exit(1)

    changed = False
    for key, default_val in DEFAULT_CONFIG.items():
        if key not in cfg:
            cfg[key] = default_val
            changed = True

    if changed:
        save_configuration(cfg)

    return cfg


def save_configuration(config: dict):
    """Write the configuration dictionary back to persistent.json."""
    os.makedirs(os.path.dirname(PERSISTENT_PATH), exist_ok=True)
    with open(PERSISTENT_PATH, "w") as f:
        json.dump(config, f, indent=4)