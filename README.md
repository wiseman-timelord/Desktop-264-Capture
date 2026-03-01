# Desktop-264-Capture
Statue: Beta - Project resume was a success, program has been tested and is fully working, and display has been worked on.

### Description
x264 Desktop recording with multi-channel audio on Windows ~8.1-10 with Python ~3.12.x. Batch launched with menu for, install or run. No GUI, intended to be used on secondary display, while recording primary display. Intended to have quality/optimal/HighCompression options for audio/video, having researched parameters behind simplified configuration. One would use this program for recording, gaming or application demonstration, etc, where one would want to be recording the primary display, and then editing later on the users own choice of video editor that supports, mp4 or mkv, file formats.

### Media
- Main menu, showing recorded 4 Hour video in 1 Hour segments, sizes "1080P" with quality at "Optimal"...(v0.4)
```
===============================================================================
   Desktop-264-Capture
===============================================================================

 Videos Folder:
     G:\Videos\Output

 Recent Files:
    Desktop_Video_2026_03_01_S004.mp4  (1.05 GB)
    Desktop_Video_2026_03_01_S003.mp4  (1.58 GB)
    Desktop_Video_2026_03_01_S002.mp4  (1.42 GB)
    Desktop_Video_2026_03_01_S001.mp4  (1.49 GB)
    (empty)


-------------------------------------------------------------------------------

   1) Start Recording

   2) Configure Settings

   3) System Information

   4) Purge Recordings


-------------------------------------------------------------------------------
Selection; Menu Options = 1-4, Quit = Q:

```
- The display while recording before secmentation...(v0.2)
```
===============================================================================
   Desktop-264-Capture : Recording
===============================================================================







   Status        : RECORDING  [00:00:10]

   Resolution    : 1280x720
   FPS Target    : 30
   Video Profile : Optimal Performance
   Audio Profile : Optimal Performance  (160 kbps)

   Temp Size     : 22.8 MB
   Output Dir    : G:\Videos\Output







-------------------------------------------------------------------------------
Press ENTER to stop recording ...


```
- Options Menu, now with 8 options...(v0.4)
```
===============================================================================
   Desktop-264-Capture : Configure Settings
===============================================================================




   1) Resolution         : 1280x720   (cycles: 1080p / 720p / 480p)

   2) FPS                : 30   (cycles: 30 / 45 / 60)

   3) Video Compression  : Optimal Performance

   4) Audio Bitrate      : 160 kbps   (cycles: 96 / 128 / 160 / 192 / 256)

   5) Audio Compression  : Optimal Performance

   6) Output Directory   : G:\Videos\Output

   7) Container Format   : MP4   (cycles: MKV / MP4)

   8) 1Hr Video Splits   : False   (Save in 1Hr Segments)




-------------------------------------------------------------------------------
   Selection; Options = 1-8, Back = B:

```

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

### Requirements
- Windows 8.1-10 - PClaude Sonnet assessed compatibility ranges, testing on Windows 10.
- Python 3.7-3.12 - Claude Sonnet assessed compatibility ranges, testing on v3.12.x 

### Instructions
1. Run the batch, right click and run as admin.
2. Select install, do clean install, and enable python through firewall if you havent already. After result summary you will be returned to menu.
3. BAck on the menu, select 1 to load the program.
4. In the main program, configure the options including output folder and resolution, etc, then return to main menu and select 1 to start recording, and when you are finished press enter until you return to the menu.
5. Repeat recording as required, and when you are finished, then exit the program with X on main menu.
- After moving/renaming the program folder, I noticed it was portable, as it did not require reinstall to work correctly in new path.

### Structure
The plan for the file structure...
```
.\Desktop-264-Capture.bat
.\installer.py   (install libraries/packages in, `.venv` and `.\data`, as well as create Json)
.\launcher.py    (run main program, main loop, startup/shutdown functions)
.\scripts\* (scripts for program entered through launcher).
.\scripts\configure.py   (globals/maps/lists, save/load json)
.\scripts\recorder.py
.\data\persistent.json   (persistent settings)
```

### Development
Project restart with Claude Sonnet...
1. Program needs testing/bugfixing.
2. Program needs actual testing of recording some demo videos for my latest apps. (these will feature on youtube).

### Credits
- mss / python-mss - Ultra-fast cross-platform screen-capture library using DXGI Desktop Duplication on Windows.
- OpenCV / opencv-python - Computer vision library used here for writing raw screen frames into an MJPG intermediate video file via VideoWriter.
- NumPy / numpy - Fundamental array library; used to convert raw BGRA pixel data from mss into BGR frames for OpenCV.
- pyaudiowpatch / pyaudiowpatch - Fork of PyAudio with WASAPI loopback support for Windows, enabling system audio and microphone capture in parallel threads.
- imageio-ffmpeg / imageio-ffmpeg - Bundles a self-contained ffmpeg binary (including libx264) so no separate ffmpeg installation is required. Used for all muxing and final H.264 encoding.
- FFmpeg (via imageio-ffmpeg) - The underlying multimedia engine. Handles re-encoding the MJPG intermediate to libx264, mixing loopback and microphone audio with amix, applying duplicate-frame dropping via mpdecimate, and writing the final MKV/MP4 container.
