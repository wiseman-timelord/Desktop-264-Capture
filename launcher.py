# launcher.py - Main entry point for the Geforce Hybrid Capture application.

import json
import os
import sys
import time
import scripts.temporary as temporary
from scripts.recorder import init_nvidia_apis, start_capture, stop_capture, cleanup

def load_configuration():
    """
    Loads the application's configuration from the 'data/configuration.json' file.
    If the file is not found, it prints an error message and exits.
    """
    try:
        with open("data/configuration.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: configuration.json not found. Please run the installer.")
        sys.exit(1)

def save_configuration(config):
    """
    Saves the provided configuration dictionary to the 'data/configuration.json' file.
    """
    with open("data/configuration.json", "w") as f:
        json.dump(config, f, indent=4)

def start_recording(config):
    """
    Starts the screen recording process. It sets the 'is_recording' flag,
    records the start time, and calls the 'start_capture' function from the recorder module.
    """
    if not temporary.is_recording:
        start_capture(config)
        temporary.is_recording = True
        temporary.recording_start_time = time.time()
        print("Recording started.")
    else:
        print("Already recording.")

def stop_recording():
    """
    Stops the screen recording process. It clears the 'is_recording' flag,
    resets the start time, and calls the 'stop_capture' function from the recorder module.
    """
    if temporary.is_recording:
        stop_capture()
        temporary.is_recording = False
        temporary.recording_start_time = None
        print("Recording stopped.")
    else:
        print("Not currently recording.")

def display_recording_stats():
    """
    Displays the current recording status (ON/OFF) and the elapsed time if a recording is in progress.
    """
    if temporary.is_recording:
        elapsed_time = time.time() - temporary.recording_start_time
        print(f"\nRecording Status: ON")
        print(f"  Duration: {time.strftime('%H:%M:%S', time.gmtime(elapsed_time))}")
    else:
        print("\nRecording Status: OFF")

def configure_settings(config):
    """
    Presents a menu to the user to configure the application's settings,
    including resolution, FPS, and codec. The changes are saved to the configuration file.
    """
    resolution_index = 0
    codec_index = 0

    # Find the initial index for the current resolution and codec
    for i, res in enumerate(temporary.resolutions):
        if res['width'] == config['resolution']['width'] and res['height'] == config['resolution']['height']:
            resolution_index = i
            break

    if config['codec'] in temporary.codecs:
        codec_index = temporary.codecs.index(config['codec'])

    while True:
        print("\nConfiguration Menu:")
        print(f"1. Cycle Resolution: {config['resolution']['width']}x{config['resolution']['height']}")
        print(f"2. Cycle Codec: {config['codec']}")
        print("3. Set FPS")
        print("4. Back to Main Menu")
        choice = input("Enter your choice: ")
        if choice == "1":
            resolution_index = (resolution_index + 1) % len(temporary.resolutions)
            config['resolution'] = temporary.resolutions[resolution_index]
            save_configuration(config)
        elif choice == "2":
            codec_index = (codec_index + 1) % len(temporary.codecs)
            config['codec'] = temporary.codecs[codec_index]
            save_configuration(config)
        elif choice == "3":
            try:
                fps = int(input("Enter new FPS: "))
                config['fps'] = fps
                save_configuration(config)
            except ValueError:
                print("Invalid input. Please enter an integer.")
        elif choice == "4":
            break
        else:
            print("Invalid choice. Please try again.")

def main():
    """
    The main function of the application. It initializes the NVIDIA APIs,
    loads the configuration, and then enters the main application loop.
    """
    if not init_nvidia_apis():
        sys.exit(1)
    config = load_configuration()
    print("Geforce Hybrid Capture")
    print("----------------------")
    while True:
        display_recording_stats()
        print("\nMenu:")
        print("1. Start Recording")
        print("2. Stop Recording")
        print("3. Configure Settings")
        print("4. Exit")
        choice = input("Enter your choice: ")
        if choice == "1":
            start_recording(config)
        elif choice == "2":
            stop_recording()
        elif choice == "3":
            configure_settings(config)
        elif choice == "4":
            if temporary.is_recording:
                stop_recording()
            cleanup()
            print("Exiting.")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
