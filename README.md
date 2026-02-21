# Desktop-264-Capture
Statue: Alpha - Restart underway.

### Description
x264vfw Desktop recording on Windows ~8.1-10

### Output
<details>
<summary>The installer for purge install...(ALPHA)</summary>
  
  ```
  ===============================================================================
     Desktop-264-Capture: Installer
  ===============================================================================
  
  Install Method: Clean Install
  
  Purging previous installation ...
    Deleting previous virtual-environment ...
    Purged data\persistent.json
    Purged data\x264vfw
  
  Creating virtual-environment ...
    C:\Program Files\Python312\python.exe -m venv .venv
  
  Upgrading pip ...
    .venv\Scripts\python.exe -m pip install --upgrade pip
  Requirement already satisfied: pip in c:\media_files\desktop-264-capture\desktop-264-capture-a007\.venv\lib\site-packages (24.0)
  Collecting pip
    Using cached pip-26.0.1-py3-none-any.whl.metadata (4.7 kB)
  Using cached pip-26.0.1-py3-none-any.whl (1.8 MB)
  Installing collected packages: pip
    Attempting uninstall: pip
      Found existing installation: pip 24.0
      Uninstalling pip-24.0:
        Successfully uninstalled pip-24.0
  Successfully installed pip-26.0.1
  
  Installing Python packages ...
    .venv\Scripts\python.exe -m pip install --prefer-binary mss>=9.0.0
  Collecting mss>=9.0.0
    Using cached mss-10.1.0-py3-none-any.whl.metadata (6.7 kB)
  Using cached mss-10.1.0-py3-none-any.whl (24 kB)
  Installing collected packages: mss
  Successfully installed mss-10.1.0
    .venv\Scripts\python.exe -m pip install --prefer-binary opencv-python>=4.5.0
  Collecting opencv-python>=4.5.0
    Using cached opencv_python-4.13.0.92-cp37-abi3-win_amd64.whl.metadata (20 kB)
  Collecting numpy>=2 (from opencv-python>=4.5.0)
    Using cached numpy-2.4.2-cp312-cp312-win_amd64.whl.metadata (6.6 kB)
  Using cached opencv_python-4.13.0.92-cp37-abi3-win_amd64.whl (40.2 MB)
  Using cached numpy-2.4.2-cp312-cp312-win_amd64.whl (12.3 MB)
  Installing collected packages: numpy, opencv-python
  Successfully installed numpy-2.4.2 opencv-python-4.13.0.92
    .venv\Scripts\python.exe -m pip install --prefer-binary numpy>=1.21.0
  Requirement already satisfied: numpy>=1.21.0 in .\.venv\Lib\site-packages (2.4.2)
    .venv\Scripts\python.exe -m pip install --prefer-binary pyaudiowpatch>=0.2.12
  Collecting pyaudiowpatch>=0.2.12
    Using cached pyaudiowpatch-0.2.12.8-cp312-cp312-win_amd64.whl.metadata (9.9 kB)
  Using cached pyaudiowpatch-0.2.12.8-cp312-cp312-win_amd64.whl (99 kB)
  Installing collected packages: pyaudiowpatch
  Successfully installed pyaudiowpatch-0.2.12.8
    .venv\Scripts\python.exe -m pip install --prefer-binary imageio-ffmpeg>=0.4.7
  Collecting imageio-ffmpeg>=0.4.7
    Using cached imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl.metadata (1.5 kB)
  Using cached imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl (31.2 MB)
  Installing collected packages: imageio-ffmpeg
  Successfully installed imageio-ffmpeg-0.6.0
  
    ensured  .\Output\
    ensured  .\data\
    ensured  .\scripts\
    ensured  .\data\x264vfw\
    wrote    data\persistent.json
  
  Setting up openh264 (win64) ...
    Downloading  openh264-1.8.0-win64.d  [####################]  100%
    Extracting    openh264-1.8.0-win64.d  [####################]  100%
  
    Extracted  → openh264-1.8.0-win64.dll
    ✓  openh264 ready.
  
  ============================================================
  INSTALLATION SUMMARY
  ============================================================
    .venv\Scripts\python.exe -m pip show mss
    ✓  mss
    .venv\Scripts\python.exe -m pip show opencv-python
    ✓  opencv-python
    .venv\Scripts\python.exe -m pip show numpy
    ✓  numpy
    .venv\Scripts\python.exe -m pip show pyaudiowpatch
    ✓  pyaudiowpatch
    .venv\Scripts\python.exe -m pip show imageio-ffmpeg
    ✓  imageio-ffmpeg
    ✓  openh264 (win64) – openh264-1.8.0-win64.dll
  
    ✓  All components installed successfully.
  ============================================================
  
  Install complete – press ENTER to return to menu.
  ```
</details>

### Requirements
- Windows ~8.1-10 - Programming towards Windows 8.1-10 compatibility, testing on Windows 10.
- Codec x264vfw - Codec must be installed from [SorceForge](https://sourceforge.net/projects/x264vfw/)
- Python - Testing on Python 3.12.x

### Structure
The plan for the file structure...
```
.\Geforce-Hybrid-Capture.bat
.\installer.py   (install libraries in `.venv`)
.\launcher.py    (run main program)
.\scripts\* (scripts for program entered through launcher).
.\scripts\temporary.py
.\scripts\recorder.py
.\data\convifguration.json
```

### Development
Project restart with Claude Sonnet...
1. Program needs testing/bugfixing.
2. Program needs actual testing of recording some demo videos for my latest apps. (these will feature on youtube).

### Done since restart
- Rethink done.
- Installer done.
- Batch Improved.
- Main program text interfacs improved.
