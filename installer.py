# This script will be used to install dependencies and set up the environment.
import os
import sys
import subprocess

VENV_DIR = ".venv"

def create_venv():
    """Creates a virtual environment if it doesn't exist."""
    if not os.path.exists(VENV_DIR):
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
        print("Virtual environment created.")
    else:
        print("Virtual environment already exists.")

def install_dependencies():
    """Installs the required dependencies using pip."""
    if os.name == 'nt':
        pip_executable = os.path.join(VENV_DIR, "Scripts", "pip.exe")
    else:
        pip_executable = os.path.join(VENV_DIR, "bin", "pip")

    print("Installing dependencies...")
    subprocess.check_call([pip_executable, "install", "av"])
    print("Dependencies installed.")

def create_output_dir():
    """Creates the Output directory if it doesn't exist."""
    if not os.path.exists("Output"):
        print("Creating Output directory...")
        os.makedirs("Output")
        print("Output directory created.")
    else:
        print("Output directory already exists.")

if __name__ == "__main__":
    create_venv()
    install_dependencies()
    create_output_dir()
    print("Installation complete.")
