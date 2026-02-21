# installer.py – Desktop-264-Capture  (Windows 8.1+ / Python 3.7-3.12)
# Installs all dependencies, creates folders & config.

import json
import os
import shutil
import struct
import subprocess
import sys
import time

# -------------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------------
VENV_DIR = ".venv"

REQ_LIST = [
    "mss>=9.0.0",              # GPU-agnostic DXGI Desktop Duplication capture
    "opencv-python>=4.5.0",    # VideoWriter (MJPG intermediate frame capture)
    "numpy>=1.21.0",           # frame array handling
    "pyaudiowpatch>=0.2.12",   # WASAPI loopback - system audio capture
    "imageio-ffmpeg>=0.4.7",   # bundled ffmpeg binary - mux + libx264 encode
]

PY_VER_MIN = (3, 7)
PY_VER_MAX = (3, 12)

DATA_DIR = "data"
CFG_PATH = os.path.join(DATA_DIR, "persistent.json")

HEADER_MAIN = (
    "===============================================================================\n"
    "   Desktop-264-Capture: Installer\n"
    "==============================================================================="
)

HEADER_MENU = (
    "===============================================================================\n"
    "   Desktop-264-Capture: Install Options\n"
    "==============================================================================="
)

# -------------------------------------------------------------------------------
# General helpers
# -------------------------------------------------------------------------------
def cls():
    os.system("cls" if os.name == "nt" else "clear")

def run(cmd, *, check=True, capture=False):
    print("  " + " ".join(str(c) for c in cmd))
    if capture:
        return subprocess.run(cmd, check=check, capture_output=True, text=True).stdout
    subprocess.run(cmd, check=check)

def python_in_venv():
    return os.path.join(VENV_DIR, "Scripts", "python.exe")

# -------------------------------------------------------------------------------
# Pre-flight detection  (silent - runs before the menu is shown)
# -------------------------------------------------------------------------------
def detect_state() -> dict:
    """Return a dict of what is already present on disk. Nothing is printed."""
    py    = python_in_venv()
    state = {
        "venv":     os.path.isfile(py),
        "packages": {},
        "config":   os.path.isfile(CFG_PATH),
    }
    for r in REQ_LIST:
        pkg = r.split(">=")[0].split("==")[0]
        if state["venv"]:
            result = subprocess.run(
                [py, "-m", "pip", "show", pkg],
                capture_output=True, text=True
            )
            state["packages"][pkg] = (result.returncode == 0)
        else:
            state["packages"][pkg] = False
    return state

# -------------------------------------------------------------------------------
# Install menu
# -------------------------------------------------------------------------------
def install_menu(state: dict) -> str:
    while True:
        cls()
        print(HEADER_MENU)
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print("   1) Clean Install (Purge + Install)")
        print()
        print("   2) Normal Install (Check + Complete)")
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print("-------------------------------------------------------------------------------")
        choice = input("Selection; Menu Options = 1-2, Abandon Install = A: ").strip()
        if choice == "1":
            print("Install continues...")
            time.sleep(2)
            return "1"
        if choice == "2":
            print("Install continues...")
            time.sleep(2)
            return "2"
        if choice.upper() == "A":
            print("\nInstall abandoned.")
            input("Press ENTER to return to menu.")
            sys.exit(0)

# -------------------------------------------------------------------------------
# Virtual environment
# -------------------------------------------------------------------------------
def destroy_old_venv():
    if os.path.isdir(VENV_DIR):
        print("  Deleting previous virtual-environment ...")
        shutil.rmtree(VENV_DIR)

def create_venv():
    print("\nCreating virtual-environment ...")
    run([sys.executable, "-m", "venv", VENV_DIR])

def upgrade_pip():
    print("\nUpgrading pip ...")
    run([python_in_venv(), "-m", "pip", "install", "--upgrade", "pip"])

def install_requirements():
    print("\nInstalling Python packages ...")
    for req in REQ_LIST:
        run([python_in_venv(), "-m", "pip", "install", "--prefer-binary", req])

def ensure_requirements(state: dict):
    """Install only the packages that are currently missing."""
    py      = python_in_venv()
    missing = [r for r in REQ_LIST
               if not state["packages"].get(r.split(">=")[0].split("==")[0], False)]
    if not missing:
        print("\n  All Python packages already present.")
        return
    print(f"\nInstalling {len(missing)} missing package(s) ...")
    for req in missing:
        run([py, "-m", "pip", "install", "--prefer-binary", req])

# -------------------------------------------------------------------------------
# Folders & config
# -------------------------------------------------------------------------------
def make_dirs():
    print()
    for d in ("Output", DATA_DIR, "scripts"):
        os.makedirs(d, exist_ok=True)
        print(f"  ensured  .\\{d}\\")

def write_default_config():
    if os.path.exists(CFG_PATH):
        print(f"  kept     {CFG_PATH}  (already exists)")
        return
    cfg = {
        "resolution": {"width": 1920, "height": 1080},
        "fps": 30,
        "codec": "X264",
        "output_path": "Output",
        "video_compression": "Optimal Performance",
        "audio_compression": "Optimal Performance",
        "audio_bitrate": 192,
        "container_format": "MKV",
    }
    with open(CFG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)
    print(f"  wrote    {CFG_PATH}")

# -------------------------------------------------------------------------------
# Purge helpers
# -------------------------------------------------------------------------------
def purge_data_dir():
    """Remove the entire .\\data\\ directory (config + any other data)."""
    if os.path.isdir(DATA_DIR):
        shutil.rmtree(DATA_DIR)
        print(f"  Purged {DATA_DIR}\\")

# -------------------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------------------
def verify_and_summary() -> bool:
    print("\n" + "=" * 60)
    print("INSTALLATION SUMMARY")
    print("=" * 60)
    py = python_in_venv()
    if not os.path.isfile(py):
        print("  x  Virtual-environment python missing - install failed.")
        return False

    all_ok = True
    for r in REQ_LIST:
        pkg = r.split(">=")[0].split("==")[0]
        try:
            run([py, "-m", "pip", "show", pkg], capture=True)
            print(f"  ok  {pkg}")
        except subprocess.CalledProcessError:
            print(f"  x   {pkg}  NOT installed")
            all_ok = False

    if all_ok:
        print("\n  All components installed successfully.")
    else:
        print("\n  Some components missing - review output above.")
    print("=" * 60)
    return all_ok

# -------------------------------------------------------------------------------
# Install paths
# -------------------------------------------------------------------------------
def do_clean_install():
    """Option 1 - purge everything, then build from scratch."""
    print("\nPurging previous installation ...")
    destroy_old_venv()
    purge_data_dir()

    create_venv()
    upgrade_pip()
    install_requirements()
    make_dirs()
    write_default_config()


def do_normal_install(state: dict):
    """Option 2 - check each component, complete only what is missing."""
    if not state["venv"]:
        create_venv()
        upgrade_pip()
    else:
        print("\n  Virtual-environment already present.")

    ensure_requirements(state)
    make_dirs()
    write_default_config()

# -------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------
def main():
    print("Installing...")
    time.sleep(2)
    cls()
    print(HEADER_MAIN)
    print()

    v = sys.version_info[:2]
    if v < PY_VER_MIN:
        print(f"ERROR: Python {PY_VER_MIN[0]}.{PY_VER_MIN[1]}+ required.")
        sys.exit(1)
    if v > PY_VER_MAX:
        print("WARNING: Python 3.13+ may give compatibility issues; continuing ...")

    print("  Detecting existing installation ...")
    state = detect_state()
    time.sleep(2)

    choice = install_menu(state)

    method = "Clean Install" if choice == "1" else "Normal Install"
    cls()
    print(HEADER_MAIN)
    print()
    print(f"Install Method: {method}")

    if choice == "1":
        do_clean_install()
    else:
        do_normal_install(state)

    ok = verify_and_summary()
    print()
    if ok:
        print("Install complete - press ENTER to return to menu.")
    else:
        print("Install finished with ERRORS - press ENTER to return.")
    input()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        input()
        sys.exit(1)