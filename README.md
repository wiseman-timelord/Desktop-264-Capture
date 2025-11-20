# Geforce-Hybrid-Capture
Statue: Alpha

### Description
So, while using Geforce Experience on Hybrid Radeon setup on Windows 8.1, there is an issue with Experience not loading, even when you disable the AMD hardware and reboot, while free alternatives are not able to record compitently, this is put down to that the build-in screen recording is using optimized process taking adavantage of key hardware features, this is what this program needs to to, is use the existing dlls etc, to trigger compitent screen recording.

### Structure
The plan for the file structure...
```
.\Geforce-Hybrid-Capture.bat
.\installer.py   (install libraries in `.venv`)
.\launcher.py    (run main program)
.\scripts\***.py (other scripts for program).
.\data\temporary.json
```

### Woo Installer
```
 Removing old virtual environment...
Running installer...

Deleting previous virtual-environment ...

Creating virtual-environment ...
  C:\Users\MaStar\AppData\Local\Programs\Python\Python311\python.exe -m venv .ve
nv

Upgrading pip ...
  .venv\Scripts\python.exe -m pip install --upgrade pip
Requirement already satisfied: pip in c:\program_files\geforce-hybrid-capture\.v
env\lib\site-packages (22.3)
Collecting pip
  Using cached pip-25.3-py3-none-any.whl (1.8 MB)
Installing collected packages: pip
  Attempting uninstall: pip
    Found existing installation: pip 22.3
    Uninstalling pip-22.3:
      Successfully uninstalled pip-22.3
Successfully installed pip-25.3

Installing Python packages ...
  .venv\Scripts\python.exe -m pip install --prefer-binary av>=12.0.0
Collecting av>=12.0.0
  Downloading av-16.0.1-cp311-cp311-win_amd64.whl.metadata (4.7 kB)
Downloading av-16.0.1-cp311-cp311-win_amd64.whl (32.3 MB)
   ---------------------------------------- 32.3/32.3 MB 442.4 kB/s  0:01:14
Installing collected packages: av
Successfully installed av-16.0.1
  ensured Output
  ensured data
  ensured scripts
  wrote data\configuration.json

============================================================
INSTALLATION SUMMARY
============================================================
  .venv\Scripts\python.exe -m pip show av
  V  av installed

  V  All packages installed successfully.
============================================================

Fresh install complete - press ENTER to return to menu.


```
