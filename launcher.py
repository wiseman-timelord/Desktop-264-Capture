# launcher.py – Main entry point for Desktop-264-Capture.

import msvcrt
import os
import sys
import time

import scripts.configure as configure
import scripts.recorder as recorder
from scripts.recorder import init_capture_system, start_capture, stop_capture, cleanup

# Output root – all recordings must live inside this folder.
OUTPUT_ROOT = "Output"

# UI constants
BAR  = "=" * 79
SEP  = "-" * 79
W    = 79   # total console width

# ---------------------------------------------------------------------------
# UI primitives
# ---------------------------------------------------------------------------
def cls():
    os.system("cls")

def _header(subtitle=""):
    """Print the standard 3-line header block."""
    print(BAR)
    if subtitle:
        title = f"   Desktop-264-Capture : {subtitle}"
    else:
        title = "   Desktop-264-Capture"
    print(title)
    print(BAR)

def _footer():
    print(SEP)

def _blank(n=1):
    for _ in range(n):
        print()

def _fmt_bytes(n):
    """Human-readable file size."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n/1024:.1f} KB"
    elif n < 1024 ** 3:
        return f"{n/1024**2:.1f} MB"
    else:
        return f"{n/1024**3:.2f} GB"

def _fmt_time(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(int(seconds)))

# ---------------------------------------------------------------------------
# Output path helper
# ---------------------------------------------------------------------------
def _resolve_output_path(user_input):
    """
    Ensure the output path is always inside OUTPUT_ROOT (.\\Output\\).
    Returns resolved path string, or None if invalid.
    """
    if not user_input:
        return OUTPUT_ROOT
    norm = os.path.normpath(user_input)
    if os.path.isabs(norm):
        return None
    parts = norm.split(os.sep)
    if parts[0].lower() == OUTPUT_ROOT.lower():
        resolved = norm
    else:
        resolved = os.path.join(OUTPUT_ROOT, norm)
    final = os.path.normpath(resolved)
    if not final.lower().startswith(OUTPUT_ROOT.lower()):
        return None
    return final

# ---------------------------------------------------------------------------
# Recording control
# ---------------------------------------------------------------------------
def _do_start_recording(config):
    if configure.is_recording:
        return
    start_capture(config)
    configure.is_recording         = True
    configure.recording_start_time = time.time()


def _do_stop_recording():
    if not configure.is_recording:
        return
    stop_capture()
    configure.is_recording         = False
    configure.recording_start_time = None

# ---------------------------------------------------------------------------
# Recording monitor screen
# ---------------------------------------------------------------------------
def recording_monitor(config):
    """
    Full-screen live status loop while recording.
    Press ENTER to stop.  Blocks until mux is complete, then shows results.
    """
    res  = config["resolution"]
    fps  = config["fps"]
    out  = config["output_path"]

    # Drain any buffered keypress so the loop doesn't exit immediately
    while msvcrt.kbhit():
        msvcrt.getwch()

    while configure.is_recording:
        elapsed   = time.time() - configure.recording_start_time
        tmp       = recorder.current_temp_video
        tmp_size  = os.path.getsize(tmp) if (tmp and os.path.exists(tmp)) else 0

        cls()
        _header("Recording")
        _blank(5)
        print(f"   Status     : RECORDING  [{_fmt_time(elapsed)}]")
        _blank()
        print(f"   Resolution : {res['width']}x{res['height']}")
        print(f"   FPS Target : {fps}")
        print(f"   Temp Size  : {_fmt_bytes(tmp_size)}")
        print(f"   Output Dir : {out}")
        _blank(8)
        print(f"   Press ENTER to stop recording ...")
        _blank(3)
        _footer()

        # Poll for ENTER (~1 s in 100 ms slices so display refreshes)
        for _ in range(10):
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in ("\r", "\n"):
                    configure.is_recording = False
                    break
            time.sleep(0.1)

    # Signal the capture thread and wait for mux
    cls()
    _header("Recording")
    _blank(5)
    print("   Stopping capture ...")
    print("   Muxing audio + video – please wait ...")
    _blank()
    _footer()

    stop_capture()
    configure.is_recording         = False
    configure.recording_start_time = None

    # Results screen
    output_file = recorder.last_output_file
    duration    = 0
    file_size   = 0
    if output_file and os.path.exists(output_file):
        file_size = os.path.getsize(output_file)

    cls()
    _header("Recording Complete")
    _blank(7)
    if output_file:
        print(f"   File    : {output_file}")
        print(f"   Size    : {_fmt_bytes(file_size)}")
    else:
        print("   WARNING : Output file not found – check Output folder.")
    _blank(10)
    _footer()
    input("   Press ENTER to return to menu ... ")

# ---------------------------------------------------------------------------
# Configure settings screen
# ---------------------------------------------------------------------------
def configure_settings_screen(config):
    res_index = 0
    for i, r in enumerate(configure.resolutions):
        if r["width"] == config["resolution"]["width"] and \
                r["height"] == config["resolution"]["height"]:
            res_index = i
            break

    fps_index = 0
    if config.get("fps") in configure.fps_options:
        fps_index = configure.fps_options.index(config["fps"])

    while True:
        res = configure.resolutions[res_index]
        cls()
        _header("Configure Settings")
        _blank(5)
        print(f"   1) Resolution : {res['width']}x{res['height']}"
              f"   (cycles: 1080p / 720p / 480p)")
        _blank()
        print(f"   2) FPS        : {config['fps']}"
              f"   (cycles: 30 / 45 / 60)")
        _blank()
        print(f"   3) Output Dir : {config['output_path']}")
        _blank(10)
        _footer()
        choice = input("   Selection; Options = 1-3, Back = B: ").strip()

        if choice == "1":
            res_index = (res_index + 1) % len(configure.resolutions)
            config["resolution"] = configure.resolutions[res_index]
            configure.save_configuration(config)

        elif choice == "2":
            fps_index = (fps_index + 1) % len(configure.fps_options)
            config["fps"] = configure.fps_options[fps_index]
            configure.save_configuration(config)

        elif choice == "3":
            cls()
            _header("Configure Settings")
            _blank(5)
            print(f"   Current output folder : {config['output_path']}")
            _blank()
            print(f"   Enter a name or subfolder path relative to .\\Output\\")
            print(f"   Leave blank to keep current.")
            _blank(12)
            _footer()
            raw = input("   New output folder: ").strip()
            if raw:
                resolved = _resolve_output_path(raw)
                if resolved is None:
                    cls()
                    _header("Configure Settings")
                    _blank(10)
                    print("   ERROR: Path must be inside .\\Output\\ – unchanged.")
                    _blank(10)
                    _footer()
                    time.sleep(2)
                else:
                    os.makedirs(resolved, exist_ok=True)
                    config["output_path"] = resolved
                    configure.save_configuration(config)

        elif choice.upper() == "B":
            break

# ---------------------------------------------------------------------------
# System information screen
# ---------------------------------------------------------------------------
def system_info_screen():
    cls()
    _header("System Information")
    _blank(5)

    print(f"   Python   : {sys.version.split()[0]}")

    try:
        import cv2
        print(f"   OpenCV   : {cv2.__version__}")
    except ImportError:
        print("   OpenCV   : not installed")

    try:
        import mss
        print(f"   mss      : available")
    except ImportError:
        print("   mss      : not installed")

    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"   ffmpeg   : {ffmpeg_path}")
    except Exception:
        print("   ffmpeg   : not found")

    print(f"   Encoding : MJPG intermediate -> libx264 via ffmpeg")
    print(f"   Output   : .\\{OUTPUT_ROOT}\\")

    _blank(10)
    _footer()
    input("   Press ENTER to continue ... ")

# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------
def main_menu(config):
    while True:
        status_line = "OFF"
        if configure.is_recording:
            elapsed = time.time() - configure.recording_start_time
            status_line = f"RECORDING  [{_fmt_time(elapsed)}]"

        cls()
        _header()
        _blank(7)
        print(f"   Recording Status : {status_line}")
        _blank()
        print("   1) Start Recording")
        _blank()
        print("   2) Configure Settings")
        _blank()
        print("   3) System Information")
        _blank()
        print("   4) Exit")
        _blank(4)
        _footer()
        choice = input("   Selection; Menu Options = 1-4, Quit = Q: ").strip()

        if choice == "1":
            if configure.is_recording:
                # Already recording – jump straight to monitor
                recording_monitor(config)
            else:
                _do_start_recording(config)
                recording_monitor(config)
            config = configure.load_configuration()

        elif choice == "2":
            if configure.is_recording:
                cls()
                _header()
                _blank(10)
                print("   Cannot configure while recording is active.")
                _blank(10)
                _footer()
                time.sleep(2)
            else:
                configure_settings_screen(config)
                config = configure.load_configuration()

        elif choice == "3":
            system_info_screen()

        elif choice in ("4", "Q", "q"):
            if configure.is_recording:
                cls()
                _header()
                _blank(10)
                print("   Stopping recording before exit ...")
                _blank(10)
                _footer()
                _do_stop_recording()
            cleanup()
            cls()
            _header()
            _blank(12)
            print("   Goodbye.")
            _blank(12)
            _footer()
            time.sleep(1)
            break

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    cls()
    _header()
    _blank(10)
    print("   Initialising capture system ...")
    _blank(10)
    _footer()

    if not init_capture_system():
        cls()
        _header()
        _blank(8)
        print("   ERROR: Capture system could not initialise.")
        _blank()
        print("   Run option 2 (Install) in the batch menu, then try again.")
        _blank(8)
        _footer()
        input("   Press ENTER to exit ... ")
        sys.exit(1)

    config = configure.load_configuration()

    # Validate stored output path
    out = config.get("output_path", OUTPUT_ROOT)
    if not os.path.normpath(out).lower().startswith(OUTPUT_ROOT.lower()):
        config["output_path"] = OUTPUT_ROOT
        configure.save_configuration(config)

    os.makedirs(config["output_path"], exist_ok=True)

    main_menu(config)


if __name__ == "__main__":
    main()