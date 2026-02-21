# Desktop-264-Capture
Statue: Alpha - Restart underway.

### Description
x264vfw Desktop recording on Windows ~8.1-10

### Media
- Main menu will be like this...
```
===============================================================================
   Desktop-264-Capture
===============================================================================

 Videos Folder:
     .\Output

 Folder Contents:
    (empty)
    (empty)
    (empty)
    (empty)
    (empty)

-------------------------------------------------------------------------------

   Recording Status : OFF

   1) Start Recording

   2) Configure Settings

   3) System Information

   4) Purge Recordings

-------------------------------------------------------------------------------
   Selection; Menu Options = 1-4, Quit = Q:
```

### Output
<details>
<summary>The installer for purge install...(ALPHA)</summary>
  
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

<details>
<summary>Grok Encoding Research Notes...</summary>
   
   ```
   Proposed Configuration Menu: Video/Audio Quality vs CompressionImplement a key/selector in your program's config with three levels. These apply universally across FPS/resolutions/audio bitrates, as CRF adapts automatically. Base video on libx264; audio on AAC (efficient for mixed system/mic). Pass to imageio-ffmpeg via writer kwargs, e.g., writer = imageio.get_writer('output.mp4', fps=FPS, codec='libx264', quality=None, ffmpeg_params=['-crf', '18', ...]).Level
   Description
   Video Params (libx264)
   Audio Params (AAC)
   Expected Impact
   Good Quality
   Prioritizes crisp details (visually near-lossless, ideal for tutorials with text/UI). Larger files, moderate CPU.
   -preset veryfast -crf 18 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr
   -c:a aac -b:a [selected kbps]
   High quality, 1.5-2x larger files than Optimal. Minimal artifacts.
   Optimal Performance
   Balanced: Good visuals, smaller files, low CPU/latency for smooth recording. Recommended default.
   -preset veryfast -crf 22 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr
   -c:a aac -b:a [selected kbps]
   Solid quality, efficient sizes, no lag on mid-range CPUs.
   High Compression
   Minimizes file size for storage/archiving. Acceptable quality for general use, fastest/lowest CPU.
   -preset ultrafast -crf 25 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr
   -c:a aac -b:a [selected kbps]
   Smallest files (30-50% reduction vs Good), potential minor artifacts in motion.
   
   Why these? CRF scales quality/size; lower = better quality/larger. Presets control speed (ultrafast/veryfast for real-time). mpdecimate + vfr drops duplicates (huge savings in static screens). Zerolatency ensures no buffering delays. Audio bitrate is user-selected (128k: smallest, 192k: highest fidelity—negligible size impact vs video).
   Capture Params: Always set -framerate [30/45/60] for input, and resolution via capture size (e.g., 1920x1080). For mixed audio: capture system/mic separately and mix (e.g., via FFmpeg's amix filter if needed).
   
   Optimal Settings by FPS, Resolution, and Audio BitrateThese are full FFmpeg param sets (adapt to imageio-ffmpeg). File sizes are estimates for 1-min average screen recording (static desktop to moderate motion; test yours). Use the config level to override CRF/preset. Assumes MP4 output.480p (854x480) - Low-res for quick/small files (e.g., mobile previews)FPS
   Audio (kbps)
   Good Quality Params
   Optimal Params
   High Compression Params
   Est. Size/Min (Good/Opt/High)
   30
   128
   -framerate 30 -s 854x480 -preset veryfast -crf 18 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr -c:a aac -b:a 128k
   -framerate 30 -s 854x480 -preset veryfast -crf 22 ...
   -framerate 30 -s 854x480 -preset ultrafast -crf 25 ...
   50-100 / 30-70 / 20-50 MB
   30
   160
   (Same video; -b:a 160k)
   ...
   ...
   +5% size
   30
   192
   (Same video; -b:a 192k)
   ...
   ...
   +10% size
   45
   128/160/192
   (Bump -framerate 45; +20-30% size vs 30 FPS)
   ...
   ...
   60-120 / 40-85 / 25-60 MB (base)
   60
   128/160/192
   (Bump -framerate 60; +40-50% size vs 30 FPS)
   ...
   ...
   70-140 / 45-95 / 30-70 MB (base)
   
   720p (1280x720) - Balanced for most uses (clear text, moderate detail)FPS
   Audio (kbps)
   Good Quality Params
   Optimal Params
   High Compression Params
   Est. Size/Min (Good/Opt/High)
   30
   128
   -framerate 30 -s 1280x720 -preset veryfast -crf 18 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr -c:a aac -b:a 128k
   -framerate 30 -s 1280x720 -preset veryfast -crf 22 ...
   -framerate 30 -s 1280x720 -preset ultrafast -crf 25 ...
   100-200 / 60-140 / 40-100 MB
   30
   160
   (Same video; -b:a 160k)
   ...
   ...
   +5% size
   30
   192
   (Same video; -b:a 192k)
   ...
   ...
   +10% size
   45
   128/160/192
   (Bump -framerate 45; +20-30% size)
   ...
   ...
   120-240 / 70-170 / 50-120 MB (base)
   60
   128/160/192
   (Bump -framerate 60; +40-50% size)
   ...
   ...
   140-280 / 80-190 / 55-140 MB (base)
   
   1080p (1920x1080) - High-res for detailed captures (e.g., gaming/UI demos)FPS
   Audio (kbps)
   Good Quality Params
   Optimal Params
   High Compression Params
   Est. Size/Min (Good/Opt/High)
   30
   128
   -framerate 30 -s 1920x1080 -preset veryfast -crf 18 -tune zerolatency -pix_fmt yuv420p -vf mpdecimate -vsync vfr -c:a aac -b:a 128k
   -framerate 30 -s 1920x1080 -preset veryfast -crf 22 ...
   -framerate 30 -s 1920x1080 -preset ultrafast -crf 25 ...
   200-400 / 120-280 / 80-200 MB
   30
   160
   (Same video; -b:a 160k)
   ...
   ...
   +5% size
   30
   192
   (Same video; -b:a 192k)
   ...
   ...
   +10% size
   45
   128/160/192
   (Bump -framerate 45; +20-30% size)
   ...
   ...
   240-480 / 140-340 / 95-240 MB (base)
   60
   128/160/192
   (Bump -framerate 60; +40-50% size)
   ...
   ...
   280-560 / 160-380 / 110-280 MB (base)


  ```
</details>

### Requirements
- Windows ~8.1-10 - Programming towards Windows 8.1-10 compatibility, testing on Windows 10.
- Codec x264vfw - Codec must be installed from [SorceForge](https://sourceforge.net/projects/x264vfw/)
- Python - Testing on Python 3.12.x

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

### Done since restart
- Rethink done.
- Installer done.
- Batch Improved.
- Main program text interfacs improved.
