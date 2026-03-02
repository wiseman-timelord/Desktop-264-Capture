# scripts/configure.py
# Runtime state, option tables, and persistent configuration I/O.

import json
import os
import sys

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
is_recording         = False
is_paused            = False
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

resolution_labels = ["1920x1080 (1080p)", "1280x720 (720p)", "854x480 (480p)"]

fps_options = [30, 45, 60]

# ---------------------------------------------------------------------------
# Video compression profiles
# ---------------------------------------------------------------------------
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
audio_compression_options = ["Good Quality", "Optimal Performance", "High Compression"]

AUDIO_COMPRESSION = {
    "Good Quality": {
        "label":       "Good Quality",
        "description": "Full fidelity at selected bitrate.",
        "bitrate_cap": None,
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
# Container / output format options
# ---------------------------------------------------------------------------
container_format_options = ["MKV", "MP4"]

# ---------------------------------------------------------------------------
# Thread budget options  (% of logical cores given to the recorder)
# ---------------------------------------------------------------------------
thread_budget_options = [25, 50, 75]   # percent

# ---------------------------------------------------------------------------
# Max RAM usage options  (% of free RAM for video buffer)
# ---------------------------------------------------------------------------
max_ram_usage_options = [25, 50, 75]   # percent

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
    "container_format":  "MKV",
    "video_splits":      False,
    "thread_budget":     75,
    "max_ram_usage":     50,
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