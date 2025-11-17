# Geforce-Hybrid-Capture
Status: Alpha

### Description
A command-line application to record the screen using NVIDIA's hardware-accelerated screen capture and encoding, designed for systems where the standard GeForce Experience software is not working.

### Structure
*   `Geforce-Hybrid-Capture.bat`: The main launcher script.
*   `installer.py`: Installs dependencies and sets up the environment.
*   `launcher.py`: The main application entry point with the command-line menu.
*   `scripts/recorder.py`: The core recording functionality, using `ctypes` to interface with NVIDIA's NvFBC API.
*   `scripts/temporary.py`: Stores the application's state.
*   `data/configuration.json`: The application's configuration file.
*   `Output/`: The directory where recorded videos are saved.

### Important: Dependencies and a Note on the Core Recorder

**1. FFmpeg with NVENC Support is Required**

This application uses the PyAV library, which is a Pythonic binding for FFmpeg. To use NVIDIA's hardware-accelerated encoders (e.g., `h264_nvenc`), you must have a version of FFmpeg that was compiled with NVENC support.

*   **How to get FFmpeg with NVENC:**
    *   The easiest way to get a pre-compiled version for Windows is to download it from [Gyan.dev](https://www.gyan.dev/ffmpeg/builds/). The "full" build is recommended.
    *   After downloading, you must add the `bin` directory of the extracted FFmpeg folder to your system's PATH environment variable.

**2. The Core Recording Functionality is Experimental**

The core of this application (`scripts/recorder.py`) interfaces with NVIDIA's native DLLs using Python's `ctypes` library. This is a complex and low-level task. Due to the limitations of the development environment, **this code is untested and should be considered experimental.**

It is based on the official NVIDIA Capture SDK documentation and is a "best-effort" implementation. It is possible that it will have bugs or may not work as expected on your specific system. You may need to debug and modify the code to get it working correctly.

### Usage

1.  Run the `Geforce-Hybrid-Capture.bat` script. This will create a virtual environment, install the necessary Python libraries, and then start the application.
2.  Use the command-line menu to start and stop recording, and to configure the settings.
