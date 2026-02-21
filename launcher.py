# launcher.py - Main entry point for Desktop-264-Capture.
# Control flow only; all display/UI lives in scripts.displays.

import os
import sys
import time

import scripts.configure as configure
import scripts.displays as displays
from scripts.recorder import init_capture_system, start_capture, stop_capture, cleanup

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
# Main menu loop
# ---------------------------------------------------------------------------
def main_menu(config):
    while True:
        choice = displays.main_menu_screen(config)

        if choice == "1":
            if not configure.is_recording:
                _do_start_recording(config)
            displays.recording_monitor(config)
            config = configure.load_configuration()

        elif choice == "2":
            if configure.is_recording:
                displays.show_cannot_configure()
            else:
                config = displays.configure_settings_screen(config)
                config = configure.load_configuration()

        elif choice == "3":
            displays.system_info_screen()

        elif choice == "4":
            if configure.is_recording:
                displays.show_cannot_purge()
            else:
                displays.purge_recordings_screen(config)

        elif choice.upper() == "Q":
            if configure.is_recording:
                displays.show_stopping_before_exit()
                _do_stop_recording()
            cleanup()
            displays.show_goodbye()
            break

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    displays.show_init_progress()

    if not init_capture_system():
        displays.show_init_error()
        sys.exit(1)

    config = configure.load_configuration()
    os.makedirs(config.get("output_path", "Output"), exist_ok=True)

    main_menu(config)


if __name__ == "__main__":
    main()