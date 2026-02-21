# launcher.py – Main entry point for Desktop-264-Capture.

import json
import os
import sys
import time

import scripts.configure as configure
from scripts.recorder import init_capture_system, start_capture, stop_capture, cleanup


# Configuration helpers live in scripts/configure.py


# ---------------------------------------------------------------------------
# Recording control
# ---------------------------------------------------------------------------
def start_recording(config):
    if configure.is_recording:
        print("Already recording.")
        return
    start_capture(config)
    configure.is_recording         = True
    configure.recording_start_time = time.time()
    print("Recording started.")


def stop_recording():
    if not configure.is_recording:
        print("Not currently recording.")
        return
    stop_capture()
    configure.is_recording         = False
    configure.recording_start_time = None
    print("Recording stopped.")


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def display_recording_stats():
    if configure.is_recording:
        elapsed = time.time() - configure.recording_start_time
        print(f"\nRecording Status: ON   [{time.strftime('%H:%M:%S', time.gmtime(elapsed))}]")
    else:
        print("\nRecording Status: OFF")


def configure_settings(config):
    """Cycle through resolution, fps, and output folder options."""

    # Locate current indices
    res_index = 0
    for i, r in enumerate(configure.resolutions):
        if r["width"] == config["resolution"]["width"] and r["height"] == config["resolution"]["height"]:
            res_index = i
            break

    fps_index = 0
    if config.get("fps") in configure.fps_options:
        fps_index = configure.fps_options.index(config["fps"])

    while True:
        res = configure.resolutions[res_index]
        print("\n--- Configure Settings ---")
        print(f"  1. Resolution : {res['width']}x{res['height']}   (cycles: 1080p → 720p → 480p)")
        print(f"  2. FPS        : {config['fps']}   (cycles: 30 → 45 → 60)")
        print(f"  3. Output dir : {config['output_path']}")
        print(f"  4. Back")

        choice = input("Choice: ").strip()

        if choice == "1":
            res_index = (res_index + 1) % len(configure.resolutions)
            config["resolution"] = configure.resolutions[res_index]
            configure.save_configuration(config)
            r = config["resolution"]
            print(f"  Resolution set to {r['width']}x{r['height']}")

        elif choice == "2":
            fps_index = (fps_index + 1) % len(configure.fps_options)
            config["fps"] = configure.fps_options[fps_index]
            configure.save_configuration(config)
            print(f"  FPS set to {config['fps']}")

        elif choice == "3":
            new_path = input("  Enter output folder path (leave blank to keep current): ").strip()
            if new_path:
                os.makedirs(new_path, exist_ok=True)
                config["output_path"] = new_path
                configure.save_configuration(config)
                print(f"  Output folder set to: {new_path}")
            else:
                print("  Unchanged.")

        elif choice == "4":
            break

        else:
            print("  Invalid choice.")


def display_system_info():
    print("\n--- System Information ---")
    print(f"  Python        : {sys.version.split()[0]}")

    try:
        import cv2
        print(f"  OpenCV        : {cv2.__version__}")
        # Check x264vfw by probing the codec
        import tempfile
        tmp    = os.path.join(tempfile.gettempdir(), "_x264vfw_check.avi")
        fourcc = cv2.VideoWriter_fourcc(*"X264")
        w      = cv2.VideoWriter(tmp, fourcc, 30, (320, 240))
        ok     = w.isOpened()
        w.release()
        try:
            os.remove(tmp)
        except OSError:
            pass
        status = "✓ available" if ok else "✗ NOT found – reinstall x264vfw"
        print(f"  x264vfw codec : {status}")
    except ImportError:
        print("  OpenCV        : not installed")

    try:
        import mss
        print(f"  mss           : ✓ available")
    except ImportError:
        print("  mss           : not installed")

    input("\nPress ENTER to continue ...")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    if not init_capture_system():
        print("\nERROR: capture system could not initialise.")
        print("Run option 2 (Install) in the batch menu, then try again.")
        input("\nPress ENTER to exit ...")
        sys.exit(1)

    config = configure.load_configuration()

    print("\n" + "="*60)
    print("  Desktop-264-Capture")
    print("  mss capture  +  x264vfw encoding  |  GPU-agnostic")
    print("="*60)

    while True:
        display_recording_stats()
        print("\nMenu:")
        print("  1. Start Recording")
        print("  2. Stop Recording")
        print("  3. Configure Settings")
        print("  4. System Information")
        print("  5. Exit")

        choice = input("Choice: ").strip()

        if choice == "1":
            start_recording(config)

        elif choice == "2":
            stop_recording()

        elif choice == "3":
            configure_settings(config)
            config = configure.load_configuration()   # reload after changes

        elif choice == "4":
            display_system_info()

        elif choice == "5":
            if configure.is_recording:
                print("Stopping recording before exit ...")
                stop_recording()
            cleanup()
            print("Goodbye.")
            break

        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()