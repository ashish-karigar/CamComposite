import os
import shutil
import subprocess
import time
from pathlib import Path

import pyvirtualcam
from pyvirtualcam import PixelFormat


def _run(cmd, cwd=None):
    subprocess.check_call(cmd, cwd=cwd)


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


def _run_bat_as_admin(bat_path: Path, workdir: Path):
    """
    Launches a .bat with UAC elevation prompt.
    """
    import ctypes

    bat_path = bat_path.resolve()
    workdir = workdir.resolve()

    params = f'/c "{bat_path}"'
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        "cmd.exe",
        params,
        str(workdir),
        1,
    )
    if ret <= 32:
        raise RuntimeError(f"Failed to launch elevated installer (ShellExecuteW={ret}).")


def _local_appdata_root() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "CamComposite"


def _installed_unitycapture_source(project_root: Path) -> Path:
    """
    Source shipped with the app by PyInstaller / installer.
    """
    return project_root / "packaging" / "win" / "UnityCapture"


def _prepare_local_unitycapture_copy(project_root: Path) -> Path:
    """
    Copies bundled UnityCapture payload from installed app folder into LOCALAPPDATA.
    Returns the LOCALAPPDATA UnityCapture repo path.
    """
    source_dir = _installed_unitycapture_source(project_root)
    if not source_dir.exists():
        raise RuntimeError(f"Bundled UnityCapture folder not found at: {source_dir}")

    appdata_root = _local_appdata_root()
    appdata_root.mkdir(parents=True, exist_ok=True)

    dest_dir = appdata_root / "UnityCapture"

    # Fresh copy each time installation is needed, so we don't depend on partial old state
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    shutil.copytree(source_dir, dest_dir)
    return dest_dir


def ensure_unitycapture_installed(project_root: Path) -> Path:
    """
    Ensures UnityCapture is installed/registered.
    Uses the UnityCapture payload bundled with the app, copies it into LOCALAPPDATA,
    then runs the installer as admin.
    Returns the LOCALAPPDATA UnityCapture path.
    """
    local_repo_dir = _local_appdata_root() / "UnityCapture"

    if unitycapture_is_registered():
        return local_repo_dir

    repo_dir = _prepare_local_unitycapture_copy(project_root)

    install_bat = repo_dir / "Install" / "Install.bat"
    if not install_bat.exists():
        raise RuntimeError(f"Install.bat not found at: {install_bat}")

    print("[i] UnityCapture not detected. Installing now...")
    print("[i] A Windows UAC prompt will appear. Click 'Yes' to proceed.\n")

    _run_bat_as_admin(install_bat, install_bat.parent)

    for _ in range(20):
        time.sleep(0.5)
        if unitycapture_is_registered():
            print("[i] UnityCapture installed and detected ✅")
            return repo_dir

    raise RuntimeError(
        "UnityCapture installer was launched but the virtual camera is still not detected.\n"
        "Try rebooting, then run again. Also ensure Install.bat was approved in the UAC prompt."
    )