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
# Only x264vfw is supported (VFW codec, software, GPU-agnostic).
codecs = ["X264"]

resolutions = [
    {"width": 1920, "height": 1080},   # 1080p
    {"width": 1280, "height": 720},    # 720p
    {"width": 854,  "height": 480},    # 480p
]

fps_options = [30, 45, 60]

# ---------------------------------------------------------------------------
# Persistent configuration  (.\data\persistent.json)
# ---------------------------------------------------------------------------
PERSISTENT_PATH = os.path.join("data", "persistent.json")

DEFAULT_CONFIG = {
    "resolution": {"width": 1920, "height": 1080},
    "fps": 30,
    "codec": "X264",
    "output_path": "Output",
}


def load_configuration() -> dict:
    """
    Load and return the configuration from persistent.json.
    Exits with an error message if the file is missing.
    """
    try:
        with open(PERSISTENT_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {PERSISTENT_PATH} not found.  Please run the installer.")
        sys.exit(1)


def save_configuration(config: dict):
    """Write the configuration dictionary back to persistent.json."""
    os.makedirs(os.path.dirname(PERSISTENT_PATH), exist_ok=True)
    with open(PERSISTENT_PATH, "w") as f:
        json.dump(config, f, indent=4)