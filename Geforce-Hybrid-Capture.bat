@echo off
python installer.py
call .venv\\Scripts\\activate.bat
python launcher.py
deactivate
