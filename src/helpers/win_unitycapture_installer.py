import os
import shutil
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

import pyvirtualcam
from pyvirtualcam import PixelFormat


UNITY_REPO_GIT = "https://github.com/schellingb/UnityCapture.git"
UNITY_REPO_ZIP = "https://github.com/schellingb/UnityCapture/archive/refs/heads/master.zip"


def _run(cmd, cwd=None):
    subprocess.check_call(cmd, cwd=cwd)


def _have_git() -> bool:
    return shutil.which("git") is not None


def unitycapture_is_registered() -> bool:
    """
    Best practical check: try opening a UnityCapture virtual camera via pyvirtualcam.
    If UnityCapture isn't installed/registered, pyvirtualcam will throw.
    """
    try:
        with pyvirtualcam.Camera(
            width=640,
            height=480,
            fps=30,
            fmt=PixelFormat.RGB,
            backend="unitycapture",
        ):
            return True
    except Exception:
        return False


def _clone_or_download_unitycapture(dest_dir: Path) -> Path:
    """
    Ensures the UnityCapture repo exists at dest_dir.
    Uses git if available; otherwise downloads ZIP.
    Returns repo_dir.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = dest_dir / "UnityCapture"

    if repo_dir.exists():
        return repo_dir

    if _have_git():
        _run(["git", "clone", UNITY_REPO_GIT, str(repo_dir)])
        return repo_dir

    # Fallback: ZIP download
    zip_path = dest_dir / "UnityCapture_master.zip"
    urllib.request.urlretrieve(UNITY_REPO_ZIP, zip_path)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest_dir)

    zip_path.unlink(missing_ok=True)

    extracted = dest_dir / "UnityCapture-master"
    if not extracted.exists():
        raise RuntimeError("UnityCapture ZIP extracted folder not found.")

    extracted.rename(repo_dir)
    return repo_dir


def _run_bat_as_admin(bat_path: Path, workdir: Path):
    """
    Launches a .bat with UAC elevation prompt.
    Note: this only launches elevated process; the .bat itself may still fail.
    """
    import ctypes

    bat_path = bat_path.resolve()
    workdir = workdir.resolve()

    params = f'/c "{bat_path}"'
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",       # triggers UAC
        "cmd.exe",
        params,
        str(workdir),
        1
    )
    if ret <= 32:
        raise RuntimeError(f"Failed to launch elevated installer (ShellExecuteW={ret}).")


def ensure_unitycapture_installed(project_root: Path) -> Path:
    """
    Ensures UnityCapture is installed/registered.
    If missing, clones/downloads into <project_root>/utils/UnityCapture and runs installer as admin.
    Returns the UnityCapture repo path.
    """
    if unitycapture_is_registered():
        return project_root / "utils" / "UnityCapture"  # best-effort path; may not exist

    utils_dir = project_root / "utils"
    repo_dir = _clone_or_download_unitycapture(utils_dir)

    install_bat = repo_dir / "Install" / "Install.bat"
    if not install_bat.exists():
        raise RuntimeError(f"Install.bat not found at: {install_bat}")

    print("[i] UnityCapture not detected. Installing now...")
    print("[i] A Windows UAC prompt will appear. Click 'Yes' to proceed.\n")

    _run_bat_as_admin(install_bat, install_bat.parent)

    # Give Windows a moment to register devices before we re-check
    for _ in range(20):
        time.sleep(0.5)
        if unitycapture_is_registered():
            print("[i] UnityCapture installed and detected ✅")
            return repo_dir

    raise RuntimeError(
        "UnityCapture installer was launched but the virtual camera is still not detected.\n"
        "Try rebooting, then run again. Also ensure Install.bat was approved in the UAC prompt."
    )