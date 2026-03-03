![Desktop-264-Capture](https://raw.githubusercontent.com/wiseman-timelord/Desktop-264-Capture/refs/heads/main/media/project_banner.jpg)
Statue: Beta - Added a GUI for version 1.00, and then spent significant time improving/refining/fixing, and now its looking/running quite nice.

### Description
x264 Desktop recording with multi-channel audio on Windows 8.1-10 with Python ~3.12.x. Batch launched with menu for, install or run. Now with GUI since v1.02+, and text display in version 0.5. Having quality/optimal/HighCompression options for audio/video, having researched parameters behind simplified configuration. Intended to be used on secondary display, while recording primary display with default audio output plus default audio input, set through Windows, and then after recording, one would want to be editing raw footage later on the users own choice of video editor that supports, mp4 or mkv, file formats, and then after saving the final movie, when it is time to move on to creating a next video, one would be purging the raw recordings, in order to keep things tidy. 

### Media
- The Dynamic Recording page, where we manage our files and commence recording...(v1.02)

![recording_page](https://raw.githubusercontent.com/wiseman-timelord/Desktop-264-Capture/refs/heads/main/media/recording_page.jpg)

- The Configure page, showing the detailed options available for recording...(v1.02)

![recording_page](https://raw.githubusercontent.com/wiseman-timelord/Desktop-264-Capture/refs/heads/main/media/configure_page.jpg)

- The About/Debug page, with some relevant information, and variables for debug...(v1.10)

![recording_page](https://raw.githubusercontent.com/wiseman-timelord/Desktop-264-Capture/refs/heads/main/media/about_debug_page.jpg)

### Output
<details>
<summary>The startup/initialization of main program (debug mode)...(v1.01)</summary>

```
   ===============================================================================
      Desktop-264-Capture: Launching (Debug Mode)...
   ===============================================================================
   
      Console will remain open to show logs.
      Close the App Window to return to this menu.
   
   Desktop-264-Capture: Initialising (Debug Mode) ...
   Capture system initialised  (mss + ffmpeg libx264 pipe + RAM buffer).
     CPU          : AMD Ryzen 9 3900X 12-Core Processor
     Logical CPUs : 24   SIMD: SSE2
     Thread cap   : 18 core(s)  (75% budget)
     Free RAM     : 52.7 GB   Video buffer cap: 16.0 GB  (75% of free, max 16 GB)
     Audio chunk  : 8192 frames
   Gradio server starting at http://127.0.0.1:7860 ...
   * Running on local URL:  http://127.0.0.1:7860
   * To create a public link, set `share=True` in `launch()`.

```
</details>



<details>
<summary>The installer for purge install...(ALPHA)</summary>
  
  ```

  ===============================================================================
     Desktop-264-Capture: Installer
  ===============================================================================
  
  Install Method: Clean Install
  
  Purging previous installation ...
    Deleting previous virtual-environment ...
    Purged data\
  
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
    wrote    data\persistent.json
  
  ============================================================
  INSTALLATION SUMMARY
  ============================================================
    .venv\Scripts\python.exe -m pip show mss
    ok  mss
    .venv\Scripts\python.exe -m pip show opencv-python
    ok  opencv-python
    .venv\Scripts\python.exe -m pip show numpy
    ok  numpy
    .venv\Scripts\python.exe -m pip show pyaudiowpatch
    ok  pyaudiowpatch
    .venv\Scripts\python.exe -m pip show imageio-ffmpeg
    ok  imageio-ffmpeg
  
    All components installed successfully.
  ============================================================
  
  Install complete - press ENTER to return to menu.


  
  ```
</details>

### Requirements
- Windows 8.1-10 - PClaude Sonnet assessed compatibility ranges, testing on Windows 10.
- Python 3.7-3.12 - Claude Sonnet assessed compatibility ranges, testing on v3.12.x.
- Powershell v5.1+ - Because of the command in the batch for re-sizing the Command Prompt.

### Instructions
Instructions are as follows...
```
1. Run the batch, right click and run as admin.
2. Select install, do clean install, and enable python through firewall if you havent already. After result summary you will be returned to menu.
3. BAck on the menu, select 1 to load the program.
4. In the main program, configure the options in Configure page including output folder and resolution, etc, then return to Recording page, and select to start recording, and when you are finished click Stop Recording, you will thenreturn to the file managment phase.
5. Repeat recording as required, and when you are finished, then exit the program by clicking "Exit Program".
- I made the program to NOT over-write previous files, hence we have the purge option, that I suggest running before recording, as otherwise filenames may get confusing.
```

### Structure
The plan for the file structure...
```
.\Desktop-264-Capture.bat  (this script is not being edited in this session, but it runs the installer/launcher)
.\installer.py   (install libraries/packages in, `.venv` and `.\data`, as well as create Json)
.\launcher.py    (run main program, main loop, startup/shutdown functions)
.\scripts\* (scripts for program entered through launcher).
.\scripts\displays.py    (interfaces, displays, browser, related functions)
.\scripts\configure.py   (globals/maps/lists, save/load json)
.\scripts\recorder.py   (codec/encoder/recording handling)
.\scripts\utilities.py   (maintenance, system/utility functions)
.\data\persistent.json   (persistent settings)
```

### Development
Project restart with Claude Sonnet...
- Testing and bugfixing for next/final 4 hour RimWorld movie.

<details>
<summary>Grok Encoding Research Notes (somewhat corrupted)...</summary>
   
   ```
   ### Proposed Configuration Menu: Video/Audio Quality vs Compression
   
   Implement a key/selector in your program's config with three levels. These apply universally across FPS/resolutions/audio bitrates, as CRF adapts automatically. Base video on libx264; audio on AAC (efficient for mixed system/mic). Pass to imageio-ffmpeg via writer kwargs, e.g., `writer = imageio.get_writer('output.mp4', fps=FPS, codec='libx264', quality=None, ffmpeg_params=['-crf', '18', ...])`.
   
   | Level              | Description                                                                 | Video Params (libx264)                                      | Audio Params (AAC)          | Expected Impact                                      |
   |--------------------|-----------------------------------------------------------------------------|-------------------------------------------------------------|-----------------------------|------------------------------------------------------|
   | Good Quality      | Prioritizes crisp details (visually near-lossless, ideal for tutorials with text/UI). Larger files, moderate CPU. | `-preset veryfast -crf 18 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr` | `-c:a aac -b:a [selected kbps]` | High quality, 1.5-2x larger files than Optimal. Minimal artifacts. |
   | Optimal Performance | Balanced: Good visuals, smaller files, low CPU/latency for smooth recording. Recommended default. | `-preset veryfast -crf 22 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr` | `-c:a aac -b:a [selected kbps]` | Solid quality, efficient sizes, no lag on mid-range CPUs. |
   | High Compression  | Minimizes file size for storage/archiving. Acceptable quality for general use, fastest/lowest CPU. | `-preset ultrafast -crf 25 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr` | `-c:a aac -b:a [selected kbps]` | Smallest files (30-50% reduction vs Good), potential minor artifacts in motion. |
   
   **Why these?** CRF scales quality/size; lower = better quality/larger. Presets control speed (ultrafast/veryfast for real-time). `mpdecimate + vfr` drops duplicates (huge savings in static screens). Zerolatency ensures no buffering delays. Audio bitrate is user-selected (128k: smallest, 192k: highest fidelity—negligible size impact vs video).
   
   **Capture Params:** Always set `-framerate [30/45/60]` for input, and resolution via capture size (e.g., 1920x1080). For mixed audio: capture system/mic separately and mix (e.g., via FFmpeg's amix filter if needed).
   
   ### Optimal Settings by FPS, Resolution, and Audio Bitrate
   
   These are full FFmpeg param sets (adapt to imageio-ffmpeg). File sizes are estimates for 1-min average screen recording (static desktop to moderate motion; test yours). Use the config level to override CRF/preset. Assumes MP4 output.
   
   #### 480p (854x480) - Low-res for quick/small files (e.g., mobile previews)
   
   | FPS | Audio (kbps) | Good Quality Params                                                                 | Optimal Params                                              | High Compression Params                                     | Est. Size/Min (Good/Opt/High)     |
   |-----|--------------|-------------------------------------------------------------------------------------|-------------------------------------------------------------|-------------------------------------------------------------|-----------------------------------|
   | 30  | 128         | `-framerate 30 -s 854x480 -preset veryfast -crf 18 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr -c:a aac -b:a 128k` | `-framerate 30 -s 854x480 -preset veryfast -crf 22 ...`     | `-framerate 30 -s 854x480 -preset ultrafast -crf 25 ...`    | 50-100 / 30-70 / 20-50 MB        |
   | 30  | 160         | (Same video; `-b:a 160k`)                                                           | ...                                                         | ...                                                         | +5% size                          |
   | 30  | 192         | (Same video; `-b:a 192k`)                                                           | ...                                                         | ...                                                         | +10% size                         |
   | 45  | 128/160/192 | (Bump `-framerate 45`; +20-30% size vs 30 FPS)                                      | ...                                                         | ...                                                         | 60-120 / 40-85 / 25-60 MB (base) |
   | 60  | 128/160/192 | (Bump `-framerate 60`; +40-50% size vs 30 FPS)                                      | ...                                                         | ...                                                         | 70-140 / 45-95 / 30-70 MB (base) |
   
   #### 720p (1280x720) - Balanced for most uses (clear text, moderate detail)
   
   | FPS | Audio (kbps) | Good Quality Params                                                                 | Optimal Params                                              | High Compression Params                                     | Est. Size/Min (Good/Opt/High)     |
   |-----|--------------|-------------------------------------------------------------------------------------|-------------------------------------------------------------|-------------------------------------------------------------|-----------------------------------|
   | 30  | 128         | `-framerate 30 -s 1280x720 -preset veryfast -crf 18 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr -c:a aac -b:a 128k` | `-framerate 30 -s 1280x720 -preset veryfast -crf 22 ...`    | `-framerate 30 -s 1280x720 -preset ultrafast -crf 25 ...`   | 100-200 / 60-140 / 40-100 MB     |
   | 30  | 160         | (Same video; `-b:a 160k`)                                                           | ...                                                         | ...                                                         | +5% size                          |
   | 30  | 192         | (Same video; `-b:a 192k`)                                                           | ...                                                         | ...                                                         | +10% size                         |
   | 45  | 128/160/192 | (Bump `-framerate 45`; +20-30% size)                                                | ...                                                         | ...                                                         | 120-240 / 70-170 / 50-120 MB (base) |
   | 60  | 128/160/192 | (Bump `-framerate 60`; +40-50% size)                                                | ...                                                         | ...                                                         | 140-280 / 80-190 / 55-140 MB (base) |
   
   #### 1080p (1920x1080) - High-res for detailed captures (e.g., gaming/UI demos)
   
   | FPS | Audio (kbps) | Good Quality Params                                                                 | Optimal Params                                              | High Compression Params                                     | Est. Size/Min (Good/Opt/High)     |
   |-----|--------------|-------------------------------------------------------------------------------------|-------------------------------------------------------------|-------------------------------------------------------------|-----------------------------------|
   | 30  | 128         | `-framerate 30 -s 1920x1080 -preset veryfast -crf 18 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr -c:a aac -b:a 128k` | `-framerate 30 -s 1920x1080 -preset veryfast -crf 22 ...`   | `-framerate 30 -s 1920x1080 -preset ultrafast -crf 25 ...`  | 200-400 / 120-280 / 80-200 MB    |
   | 30  | 160         | (Same video; `-b:a 160k`)                                                           | ...                                                         | ...                                                         | +5% size                          |
   | 30  | 192         | (Same video; `-b:a 192k`)                                                           | ...                                                         | ...                                                         | +10% size                         |
   | 45  | 128/160/192 | (Bump `-framerate 45`; +20-30% size)                                                | ...                                                         | ...                                                         | 240-480 / 140-340 / 95-240 MB (base) |
   | 60  | 128/160/192 | (Bump `-framerate 60`; +40-50% size)                                                | ...                                                         | ...                                                         | 280-560 / 160-380 / 110-280 MB (base) |

  ```
</details>

### Credits
- mss / python-mss - Ultra-fast cross-platform screen-capture library using DXGI Desktop Duplication on Windows.
- OpenCV / opencv-python - Computer vision library used here for writing raw screen frames into an MJPG intermediate video file via VideoWriter.
- NumPy / numpy - Fundamental array library; used to convert raw BGRA pixel data from mss into BGR frames for OpenCV.
- pyaudiowpatch / pyaudiowpatch - Fork of PyAudio with WASAPI loopback support for Windows, enabling system audio and microphone capture in parallel threads.
- imageio-ffmpeg / imageio-ffmpeg - Bundles a self-contained ffmpeg binary (including libx264) so no separate ffmpeg installation is required. Used for all muxing and final H.264 encoding.
- FFmpeg (via imageio-ffmpeg) - The underlying multimedia engine. Handles re-encoding the MJPG intermediate to libx264, mixing loopback and microphone audio with amix, applying duplicate-frame dropping via mpdecimate, and writing the final MKV/MP4 container.
