# installer.py – one-shot, idempotent, Windows-only, Python 3.11
# Does everything the batch needs: venv → pip → deps → folders → json → report
import os, sys, subprocess, json, platform, shutil

VENV_DIR   = ".venv"
REQ_LIST   = [
    "Pillow>=8.3.0",          # <- add this line
    "av>=12.0.0",
    "d3dshot>=0.1.5",
    "numpy>=1.21.0",
    "comtypes>=1.1.14"
]
PY_VER_MIN = (3, 7)
PY_VER_MAX = (3, 11)                 # 3.12+ warned against

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def run(cmd, *, check=True, capture=False):
    """Run a command list, echo it, optional check/capture."""
    print("  " + " ".join(cmd))
    if capture:
        return subprocess.run(cmd, check=check, capture_output=True, text=True).stdout
    subprocess.run(cmd, check=check)

def get_base_python():
    """Return the Python interpreter that invoked this script."""
    return sys.executable

# ---------------------------------------------------------------------------
def destroy_old_venv():
    if os.path.isdir(VENV_DIR):
        print("\nDeleting previous virtual-environment ...")
        shutil.rmtree(VENV_DIR)

def create_venv():
    print("\nCreating virtual-environment ...")
    run([get_base_python(), "-m", "venv", VENV_DIR])

def python_in_venv():
    return os.path.join(VENV_DIR, "Scripts", "python.exe")

def pip_in_venv():
    return os.path.join(VENV_DIR, "Scripts", "pip.exe")

def upgrade_pip():
    print("\nUpgrading pip ...")
    run([python_in_venv(), "-m", "pip", "install", "--upgrade", "pip"])

def install_requirements():
    print("\nInstalling Python packages ...")

    # 1.  Force a modern Pillow wheel *before* anything else
    run([python_in_venv(), "-m", "pip", "install", "--upgrade", "--force-reinstall",
         "--no-deps", "--prefer-binary", "Pillow>=8.3.0,<11"])

    # 2.  Install D3DShot *without* its dependencies so it can't drag Pillow back
    run([python_in_venv(), "-m", "pip", "install", "--no-deps", "--prefer-binary",
         "d3dshot>=0.1.5"])

    # 3.  Install everything else (skip Pillow and d3dshot)
    for req in REQ_LIST:
        pkg_name = req.split(">=")[0].split("==")[0].lower()
        if pkg_name in ("pillow", "d3dshot"):
            continue
        run([python_in_venv(), "-m", "pip", "install", "--prefer-binary", req])

def make_dirs():
    for d in ("Output", "data", "scripts"):
        os.makedirs(d, exist_ok=True)
        print(f"  ensured {d}")

def write_json():
    cfg_path = os.path.join("data", "configuration.json")
    cfg = {
        "resolution": {"width": 1920, "height": 1080},
        "fps": 30,
        "codec": "h264_nvenc",  # Changed to NVENC by default
        "output_path": "Output",
        "bitrate": "5M",  # Added bitrate control
        "preset": "medium"  # NVENC preset: fast, medium, slow, hq, etc.
    }
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=4)
    print(f"  wrote {cfg_path}")

def verify_and_summary():
    print("\n" + "="*60)
    print("INSTALLATION SUMMARY")
    print("="*60)
    py = python_in_venv()
    if not os.path.isfile(py):
        print("  ✗  Virtual-environment python missing – install failed.")
        return False

    ok = True
    for r in REQ_LIST:
        pkg = r.split(">=")[0].split("==")[0]
        try:
            run([py, "-m", "pip", "show", pkg], capture=True)
            print(f"  ✓  {pkg} installed")
        except subprocess.CalledProcessError:
            print(f"  ✗  {pkg} NOT installed")
            ok = False

    if ok:
        print("\n  ✓  All packages installed successfully.")
    else:
        print("\n  ⚠  Some packages missing – review output above.")
    print("="*60)
    return ok

# ---------------------------------------------------------------------------
def main():
    # sanity-check host python
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
    make_dirs()
    write_json()

    if verify_and_summary():
        print("\nClean install complete – press ENTER to return to menu.")
    else:
        print("\nInstall finished with ERRORS – press ENTER to return.")
    input()

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print("\nA command failed – aborting.  (see output above)")
        input()
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        input()
        sys.exit(1)