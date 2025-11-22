# Geforce-Hybrid-Capture
Statue: Alpha - Halted (ie stopped) due to Afterburner having, NV12 video capture and multi-stream audio! (if only I had known this before)

### Description
So, while using Geforce Experience on Hybrid Radeon setup on Windows 8.1, there is an issue with Experience not loading, even when you disable the AMD hardware and reboot, while free alternatives are not able to record compitently, this is put down to that the build-in screen recording is using optimized process taking adavantage of key hardware features, this is what this program needs to to, is use the existing dlls etc, to trigger compitent screen recording.

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
- Ideally I want to install 475 drivers, but they use different dlls, so need to produce critical research, ensure that the program is compatible with ALL 300/400 series drivers, understanding subtle differences between dlls used for recording and what best combination, and installing/NotingConfigurationInJson, and main program knows from json what to use for what, thus optimally compatible with differing levels of 300/400 drivers.
