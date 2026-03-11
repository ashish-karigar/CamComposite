import time
from pathlib import Path

from src.helpers.win_unitycapture_installer import (
    unitycapture_is_registered,
    ensure_unitycapture_installed,
)


def is_windows() -> bool:
    import platform
    return platform.system() == "Windows"


def project_root() -> Path:
    # src/helpers/win_first_run_check.py -> CamComposite/
    return Path(__file__).resolve().parents[2]


def unitycapture_installed() -> bool:
    return unitycapture_is_registered()


def ensure_windows_requirements(splash=None):
    """
    Checks and installs Windows requirements needed by CamComposite.
    Currently: UnityCapture only.
    """
    if splash:
        splash.set_status("Checking UnityCapture...", "Verifying required Windows dependencies.")
        splash.append_log("Checking UnityCapture installation...")

    if unitycapture_installed():
        if splash:
            splash.append_log("UnityCapture already installed.")
        return

    if splash:
        splash.append_log("UnityCapture not found.")
        splash.append_log("CamComposite will now install UnityCapture.")
        splash.append_log("A Windows administrator prompt may appear.")

    ensure_unitycapture_installed(project_root())

    # Small pause so device registration settles
    time.sleep(0.5)

    if not unitycapture_installed():
        raise RuntimeError("UnityCapture installation did not complete successfully.")

    if splash:
        splash.append_log("UnityCapture installed and ready.")