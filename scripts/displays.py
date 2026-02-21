# scripts/displays.py
# All console UI screens and menus for Desktop-264-Capture.
# Extracted from launcher.py so that launcher only holds control flow.

import glob
import msvcrt
import os
import sys
import time

import scripts.configure as configure
from scripts import recorder

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT = "Output"

# ---------------------------------------------------------------------------
# UI constants
# ---------------------------------------------------------------------------
BAR = "=" * 79
SEP = "-" * 79
W   = 79
CONSOLE_LINES = 30          # matches `mode con cols=80 lines=30` in .bat

# Filename prefix used by recorder and matched by purge.
VIDEO_PREFIX = "Desktop_Video_"

# ---------------------------------------------------------------------------
# UI primitives
# ---------------------------------------------------------------------------
def cls():
    os.system("cls")


def header(subtitle=""):
    """Print the standard 3-line header block."""
    print(BAR)
    if subtitle:
        title = f"   Desktop-264-Capture : {subtitle}"
    else:
        title = "   Desktop-264-Capture"
    print(title)
    print(BAR)


def footer():
    print(SEP)


def blank(n=1):
    for _ in range(n):
        print()


def fmt_bytes(n):
    """Human-readable file size."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    else:
        return f"{n / 1024 ** 3:.2f} GB"


def fmt_time(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(int(seconds)))


# ---------------------------------------------------------------------------
# Output path helper
# ---------------------------------------------------------------------------
def resolve_output_path(user_input):
    """
    Accept any valid directory path the user provides.
    - Absolute paths (e.g. G:\\Videos\\Output) are accepted directly.
    - Relative paths are resolved relative to .\\Output\\.
    - Blank input returns None (caller keeps current value).
    """
    if not user_input:
        return None

    raw  = user_input.strip()
    norm = os.path.normpath(raw)

    # Absolute path – accept as-is
    if os.path.isabs(norm):
        return norm

    # Relative path – anchor inside .\Output\ if not already
    parts = norm.split(os.sep)
    if parts[0].lower() == DEFAULT_OUTPUT.lower():
        return norm
    return os.path.join(DEFAULT_OUTPUT, norm)


# ---------------------------------------------------------------------------
# Folder listing helpers
# ---------------------------------------------------------------------------
def _list_videos(output_path):
    """
    Return a list of (filename, size_bytes) for Desktop_Video_* files
    in output_path, sorted newest-first by modification time.
    """
    if not os.path.isdir(output_path):
        return []

    pattern = os.path.join(output_path, f"{VIDEO_PREFIX}*")
    files   = glob.glob(pattern)

    entries = []
    for fp in files:
        if os.path.isfile(fp):
            entries.append((fp, os.path.getmtime(fp), os.path.getsize(fp)))

    entries.sort(key=lambda e: e[1], reverse=True)
    return [(os.path.basename(e[0]), e[2]) for e in entries]


def _display_path(out_path):
    """Friendly display: relative with .\\ prefix when inside cwd, else full."""
    try:
        rel = os.path.relpath(out_path)
        if not rel.startswith(".."):
            return f".\\{rel}"
    except ValueError:
        pass   # different drive on Windows – keep absolute
    return out_path


# ---------------------------------------------------------------------------
# Main menu screen  (fixed 28-line layout, no dampening needed)
# ---------------------------------------------------------------------------
def main_menu_screen(config):
    """
    Display the main menu once and return the user's choice string.

    Layout (fixed 28 lines, fits cleanly in 30-line console):
      3  header
      1  blank
      1  Videos Folder label
      1  folder path
      1  blank
      1  Folder Contents label
      5  file slots  (always exactly 5 – pads unused slots with "(empty)")
      1  blank
      1  mid-separator
      1  blank
      1  recording status
      1  blank
      1  option 1
      1  blank
      1  option 2
      1  blank
      1  option 3
      1  blank
      1  option 4
      1  blank
      1  bottom separator
      1  input prompt
    ──
     28  total
    """
    out_path = config.get("output_path", DEFAULT_OUTPUT)
    videos   = _list_videos(out_path)

    # Always display exactly 5 slots; pad any unused slots with "(empty)".
    # _list_videos already sorts newest-first, so we just take the top 5.
    MAX_SLOTS = 5
    shown     = videos[:MAX_SLOTS]
    slots     = len(shown)

    # Recording status line
    status_line = "OFF"
    if configure.is_recording and configure.recording_start_time:
        elapsed = time.time() - configure.recording_start_time
        status_line = f"RECORDING  [{fmt_time(elapsed)}]"

    cls()
    header()
    blank()                                         # line 4

    print(" Videos Folder:")                        # line 5
    print(f"     {_display_path(out_path)}")        # line 6
    blank()                                         # line 7

    print(" Recent Files:")                      # line 8
    for name, size in shown:                        # lines 9-13 (up to 5 real files)
        print(f"    {name}  ({fmt_bytes(size)})")
    for _ in range(MAX_SLOTS - slots):              # pad remaining slots with "(empty)"
        print("    (empty)")
    blank()                                         # line 14

    footer()                                        # line 15
    blank()                                         # line 16
    print(f"   Recording Status : {status_line}")  # line 17
    blank()                                         # line 18
    print("   1) Start Recording")                 # line 19
    blank()                                         # line 20
    print("   2) Configure Settings")              # line 21
    blank()                                         # line 22
    print("   3) System Information")              # line 23
    blank()                                         # line 24
    print("   4) Purge Recordings")                # line 25
    blank()                                         # line 26
    footer()                                        # line 27
    choice = input("   Selection; Menu Options = 1-4, Quit = Q: ").strip()  # line 28
    return choice


# ---------------------------------------------------------------------------
# Purge recordings screen
# ---------------------------------------------------------------------------
def purge_recordings_screen(config):
    """
    Ask for confirmation, then delete all Desktop_Video_* files in the
    configured output folder.  Returns the number of files deleted.
    """
    out_path = config.get("output_path", DEFAULT_OUTPUT)
    videos   = _list_videos(out_path)

    cls()
    header("Purge Recordings")
    blank(3)

    if not videos:
        print("   No recordings found to purge.")
        blank(10)
        footer()
        input("   Press ENTER to return to menu ... ")
        return 0

    total_size = sum(s for _, s in videos)
    print(f"   Output folder : {_display_path(out_path)}")
    print(f"   Files found   : {len(videos)}")
    print(f"   Total size    : {fmt_bytes(total_size)}")
    blank()
    print(f"   This will delete ALL files matching '{VIDEO_PREFIX}*'")
    print("   in the output folder.  This cannot be undone.")
    blank(6)
    footer()
    confirm = input("   Type YES to confirm purge, or press ENTER to cancel: ").strip()

    if confirm == "YES":
        deleted = 0
        for name, _ in videos:
            fp = os.path.join(out_path, name)
            try:
                os.remove(fp)
                deleted += 1
            except OSError as e:
                print(f"   WARNING: could not delete {name}: {e}")

        cls()
        header("Purge Recordings")
        blank(8)
        print(f"   Purged {deleted} of {len(videos)} recording(s).")
        blank(8)
        footer()
        input("   Press ENTER to return to menu ... ")
        return deleted
    else:
        cls()
        header("Purge Recordings")
        blank(10)
        print("   Purge cancelled.")
        blank(10)
        footer()
        time.sleep(1)
        return 0


# ---------------------------------------------------------------------------
# Recording monitor screen
# ---------------------------------------------------------------------------
def recording_monitor(config):
    """
    Full-screen live status loop while recording.
    Press ENTER to stop.  Blocks until mux is complete, then shows results.
    """
    res = config["resolution"]
    fps = config["fps"]
    out = config["output_path"]

    vc_label = config.get("video_compression", "Optimal Performance")
    ac_label = config.get("audio_compression", "Optimal Performance")
    ab_kbps  = configure.effective_audio_bitrate(config)

    # Drain any buffered keypress so the loop doesn't exit immediately
    while msvcrt.kbhit():
        msvcrt.getwch()

    while configure.is_recording:
        elapsed  = time.time() - configure.recording_start_time
        tmp      = recorder.current_temp_video
        tmp_size = os.path.getsize(tmp) if (tmp and os.path.exists(tmp)) else 0

        cls()
        header("Recording")
        blank(3)
        print(f"   Status        : RECORDING  [{fmt_time(elapsed)}]")
        blank()
        print(f"   Resolution    : {res['width']}x{res['height']}")
        print(f"   FPS Target    : {fps}")
        print(f"   Video Profile : {vc_label}")
        print(f"   Audio Profile : {ac_label}  ({ab_kbps} kbps)")
        blank()
        print(f"   Temp Size     : {fmt_bytes(tmp_size)}")
        print(f"   Output Dir    : {out}")
        blank(5)
        print("   Press ENTER to stop recording ...")
        blank(2)
        footer()

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
    header("Recording")
    blank(5)
    print("   Stopping capture ...")
    print("   Muxing audio + video - please wait ...")
    blank()
    footer()

    recorder.stop_capture()
    configure.is_recording         = False
    configure.recording_start_time = None

    # Results screen
    output_file = recorder.last_output_file
    file_size   = 0
    if output_file and os.path.exists(output_file):
        file_size = os.path.getsize(output_file)

    cls()
    header("Recording Complete")
    blank(7)
    if output_file:
        print(f"   File    : {output_file}")
        print(f"   Size    : {fmt_bytes(file_size)}")
    else:
        print("   WARNING : Output file not found - check Output folder.")
    blank(10)
    footer()
    input("   Press ENTER to return to menu ... ")


# ---------------------------------------------------------------------------
# Configure settings screen  (top-level)
# ---------------------------------------------------------------------------
def configure_settings_screen(config):
    """Master settings menu - delegates to sub-screens."""

    while True:
        res = config["resolution"]
        cls()
        header("Configure Settings")
        blank(3)

        print(f"   1) Resolution         : {res['width']}x{res['height']}"
              f"   (cycles: 1080p / 720p / 480p)")
        blank()
        print(f"   2) FPS                : {config['fps']}"
              f"   (cycles: 30 / 45 / 60)")
        blank()
        print(f"   3) Video Compression  : {config.get('video_compression', 'Optimal Performance')}")
        blank()
        print(f"   4) Audio Bitrate      : {config.get('audio_bitrate', 192)} kbps"
              f"   (cycles: 96 / 128 / 160 / 192 / 256)")
        blank()
        print(f"   5) Audio Compression  : {config.get('audio_compression', 'Optimal Performance')}")
        blank()
        print(f"   6) Output Directory   : {config['output_path']}")
        blank(4)
        footer()
        choice = input("   Selection; Options = 1-6, Back = B: ").strip()

        # ---- 1) Resolution (cycle) ----
        if choice == "1":
            res_index = 0
            for i, r in enumerate(configure.resolutions):
                if (r["width"] == config["resolution"]["width"]
                        and r["height"] == config["resolution"]["height"]):
                    res_index = i
                    break
            res_index = (res_index + 1) % len(configure.resolutions)
            config["resolution"] = configure.resolutions[res_index]
            configure.save_configuration(config)

        # ---- 2) FPS (cycle) ----
        elif choice == "2":
            fps_index = 0
            if config.get("fps") in configure.fps_options:
                fps_index = configure.fps_options.index(config["fps"])
            fps_index = (fps_index + 1) % len(configure.fps_options)
            config["fps"] = configure.fps_options[fps_index]
            configure.save_configuration(config)

        # ---- 3) Video compression (sub-screen) ----
        elif choice == "3":
            config = _video_compression_screen(config)

        # ---- 4) Audio bitrate (cycle) ----
        elif choice == "4":
            opts = configure.audio_bitrate_options
            cur  = config.get("audio_bitrate", 192)
            idx  = opts.index(cur) if cur in opts else 0
            idx  = (idx + 1) % len(opts)
            config["audio_bitrate"] = opts[idx]
            configure.save_configuration(config)

        # ---- 5) Audio compression (sub-screen) ----
        elif choice == "5":
            config = _audio_compression_screen(config)

        # ---- 6) Output directory ----
        elif choice == "6":
            config = _output_dir_screen(config)

        elif choice.upper() == "B":
            break

    return config


# ---------------------------------------------------------------------------
# Video compression sub-screen
# ---------------------------------------------------------------------------
def _video_compression_screen(config):
    current = config.get("video_compression", "Optimal Performance")
    options = configure.video_compression_options

    while True:
        cls()
        header("Video Compression")
        blank(3)

        for i, opt in enumerate(options, 1):
            profile = configure.VIDEO_COMPRESSION[opt]
            marker  = " <--" if opt == current else ""
            print(f"   {i}) {opt}{marker}")
            print(f"      {profile['description']}")
            print(f"      preset={profile['preset']}  crf={profile['crf']}  "
                  f"tune={profile['tune']}")
            blank()

        blank(3)
        footer()
        sel = input("   Selection; Options = 1-3, Back = B: ").strip()

        if sel in ("1", "2", "3"):
            idx = int(sel) - 1
            config["video_compression"] = options[idx]
            configure.save_configuration(config)
            current = options[idx]
        elif sel.upper() == "B":
            break

    return config


# ---------------------------------------------------------------------------
# Audio compression sub-screen
# ---------------------------------------------------------------------------
def _audio_compression_screen(config):
    current = config.get("audio_compression", "Optimal Performance")
    options = configure.audio_compression_options

    while True:
        cls()
        header("Audio Compression")
        blank(3)

        eff = configure.effective_audio_bitrate(config)
        print(f"   Selected bitrate : {config.get('audio_bitrate', 192)} kbps")
        print(f"   Effective output : {eff} kbps  (after profile cap)")
        blank()

        for i, opt in enumerate(options, 1):
            profile = configure.AUDIO_COMPRESSION[opt]
            marker  = " <--" if opt == current else ""
            cap_str = (f"{profile['bitrate_cap']} kbps cap"
                       if profile["bitrate_cap"] else "no cap")
            print(f"   {i}) {opt}{marker}")
            print(f"      {profile['description']}  ({cap_str})")
            blank()

        blank(3)
        footer()
        sel = input("   Selection; Options = 1-3, Back = B: ").strip()

        if sel in ("1", "2", "3"):
            idx = int(sel) - 1
            config["audio_compression"] = options[idx]
            configure.save_configuration(config)
            current = options[idx]
        elif sel.upper() == "B":
            break

    return config


# ---------------------------------------------------------------------------
# Output directory sub-screen
# ---------------------------------------------------------------------------
def _output_dir_screen(config):
    cls()
    header("Configure Settings : Output Directory")
    blank(4)
    print(f"   Current output folder : {config['output_path']}")
    blank()
    print("   Enter a folder path.  Examples:")
    print("       Recordings            ->  .\\Output\\Recordings")
    print("       G:\\Videos\\Output      ->  G:\\Videos\\Output")
    blank()
    print("   Leave blank to keep current.")
    blank(6)
    footer()
    raw = input("   New output folder: ").strip()
    if raw:
        resolved = resolve_output_path(raw)
        if resolved is None:
            return config
        try:
            os.makedirs(resolved, exist_ok=True)
            config["output_path"] = resolved
            configure.save_configuration(config)
        except OSError as e:
            cls()
            header("Configure Settings")
            blank(10)
            print(f"   ERROR: Could not create folder: {e}")
            blank(10)
            footer()
            time.sleep(3)
    return config


# ---------------------------------------------------------------------------
# System information screen
# ---------------------------------------------------------------------------
def system_info_screen():
    cls()
    header("System Information")
    blank(4)

    print(f"   Python   : {sys.version.split()[0]}")

    try:
        import cv2
        print(f"   OpenCV   : {cv2.__version__}")
    except ImportError:
        print("   OpenCV   : not installed")

    try:
        import mss as _mss
        print("   mss      : available")
    except ImportError:
        print("   mss      : not installed")

    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"   ffmpeg   : {ffmpeg_path}")
    except Exception:
        print("   ffmpeg   : not found")

    print("   Encoding : MJPG intermediate -> libx264 via ffmpeg")
    print(f"   Output   : {DEFAULT_OUTPUT}")

    blank(8)
    footer()
    input("   Press ENTER to continue ... ")


# ---------------------------------------------------------------------------
# Blocking-message helpers (used by launcher for short notices)
# ---------------------------------------------------------------------------
def show_cannot_configure():
    cls()
    header()
    blank(10)
    print("   Cannot configure while recording is active.")
    blank(10)
    footer()
    time.sleep(2)


def show_cannot_purge():
    cls()
    header()
    blank(10)
    print("   Cannot purge while recording is active.")
    blank(10)
    footer()
    time.sleep(2)


def show_stopping_before_exit():
    cls()
    header()
    blank(10)
    print("   Stopping recording before exit ...")
    blank(10)
    footer()


def show_goodbye():
    cls()
    header()
    blank(12)
    print("   Goodbye.")
    blank(12)
    footer()
    time.sleep(1)


def show_init_progress():
    cls()
    header()
    blank(10)
    print("   Initialising capture system ...")
    blank(10)
    footer()


def show_init_error():
    cls()
    header()
    blank(8)
    print("   ERROR: Capture system could not initialise.")
    blank()
    print("   Run option 2 (Install) in the batch menu, then try again.")
    blank(8)
    footer()
    input("   Press ENTER to exit ... ")