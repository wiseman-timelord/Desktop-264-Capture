# installer.py – one-shot, idempotent, Windows-only, Python 3.11
# Installs dependencies, checks for x264vfw VFW codec, creates folders & config.

import os
import sys
import subprocess
import json
import shutil
import tempfile

VENV_DIR   = ".venv"
REQ_LIST   = [
    "mss>=9.0.0",              # GPU-agnostic Desktop Duplication / DXGI screen capture
    "opencv-python>=4.5.0",    # VideoWriter → x264vfw via VFW interface
    "numpy>=1.21.0",           # frame array handling
    "pyaudiowpatch>=0.2.12",   # PyAudio fork with WASAPI loopback (system audio capture)
    "imageio-ffmpeg>=0.4.7",   # bundles a static ffmpeg binary – used for muxing audio+video
]
PY_VER_MIN = (3, 7)
PY_VER_MAX = (3, 11)

X264VFW_DOWNLOAD = "https://sourceforge.net/projects/x264vfw/"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def run(cmd, *, check=True, capture=False):
    print("  " + " ".join(str(c) for c in cmd))
    if capture:
        return subprocess.run(cmd, check=check, capture_output=True, text=True).stdout
    subprocess.run(cmd, check=check)

def python_in_venv():
    return os.path.join(VENV_DIR, "Scripts", "python.exe")

# ---------------------------------------------------------------------------
# venv
# ---------------------------------------------------------------------------
def destroy_old_venv():
    if os.path.isdir(VENV_DIR):
        print("\nDeleting previous virtual-environment ...")
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

# ---------------------------------------------------------------------------
# x264vfw codec detection
# ---------------------------------------------------------------------------
def check_x264vfw_installed():
    """
    Ask OpenCV (running inside the venv) to open a tiny test VideoWriter
    with fourcc X264.  Returns True only if the codec is present and working.
    """
    py = python_in_venv()
    probe_script = (
        "import cv2, tempfile, os\n"
        "tmp = tempfile.mktemp(suffix='.avi')\n"
        "fourcc = cv2.VideoWriter_fourcc(*'X264')\n"
        "w = cv2.VideoWriter(tmp, fourcc, 30, (320,240))\n"
        "ok = w.isOpened()\n"
        "w.release()\n"
        "try:\n"
        "    os.remove(tmp)\n"
        "except:\n"
        "    pass\n"
        "exit(0 if ok else 1)\n"
    )
    result = subprocess.run([py, "-c", probe_script])
    return result.returncode == 0

def require_x264vfw():
    """
    Loop until the user has x264vfw installed.
    Each iteration checks the codec; on failure it shows the download URL
    and waits for the user to press ENTER before re-checking.
    """
    print("\n" + "="*60)
    print("Checking for x264vfw codec ...")
    print("="*60)

    while True:
        if check_x264vfw_installed():
            print("  ✓  x264vfw detected – continuing.")
            break
        else:
            print("\n  ✗  x264vfw codec NOT found on this system.")
            print()
            print("  Please download and install x264vfw from:")
            print(f"  --> {X264VFW_DOWNLOAD}")
            print()
            print("  Install the codec (run the installer, accept defaults),")
            print("  then press ENTER here to re-check.")
            input("  [Press ENTER after installing x264vfw] ")
            print("\n  Re-checking x264vfw ...")

# ---------------------------------------------------------------------------
# folders & config
# ---------------------------------------------------------------------------
def make_dirs():
    print()
    for d in ("Output", "data", "scripts"):
        os.makedirs(d, exist_ok=True)
        print(f"  ensured  .\\{d}\\")

def write_default_config():
    cfg_path = os.path.join("data", "persistent.json")
    # Only write if it doesn't already exist to preserve user settings.
    if os.path.exists(cfg_path):
        print(f"  kept     {cfg_path}  (already exists)")
        return
    cfg = {
        "resolution": {"width": 1920, "height": 1080},
        "fps": 30,
        "codec": "X264",
        "output_path": "Output"
    }
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=4)
    print(f"  wrote    {cfg_path}")

# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------
def verify_and_summary():
    print("\n" + "="*60)
    print("INSTALLATION SUMMARY")
    print("="*60)
    py = python_in_venv()
    if not os.path.isfile(py):
        print("  ✗  Virtual-environment python missing – install failed.")
        return False

    all_ok = True
    for r in REQ_LIST:
        pkg = r.split(">=")[0].split("==")[0]
        try:
            run([py, "-m", "pip", "show", pkg], capture=True)
            print(f"  ✓  {pkg}")
        except subprocess.CalledProcessError:
            print(f"  ✗  {pkg}  NOT installed")
            all_ok = False

    print(f"  ✓  x264vfw codec  (pre-verified)")

    if all_ok:
        print("\n  ✓  All packages installed successfully.")
    else:
        print("\n  ⚠  Some packages missing – review output above.")
    print("="*60)
    return all_ok

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    v = sys.version_info[:2]
    if v < PY_VER_MIN:
        print(f"ERROR: Python {PY_VER_MIN[0]}.{PY_VER_MIN[1]}+ required.")
        sys.exit(1)
    if v > PY_VER_MAX:
        print("WARNING: Python 3.12+ may give compatibility issues; continuing ...")

    destroy_old_venv()
    create_venv()
    upgrade_pip()
    install_requirements()

    # x264vfw must be present before we proceed
    require_x264vfw()

    make_dirs()
    write_default_config()

    if verify_and_summary():
        print("\nClean install complete – press ENTER to return to menu.")
    else:
        print("\nInstall finished with ERRORS – press ENTER to return.")
    input()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        print("\nA command failed – aborting.  (see output above)")
        input()
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        input()
        sys.exit(1)