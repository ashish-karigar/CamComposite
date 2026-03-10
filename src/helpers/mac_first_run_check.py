from pathlib import Path
import shutil
import subprocess
import platform


def _resource_path(filename: str):
    import sys

    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        candidates = [
            base / filename,
            base / "resources" / filename,
            base / "packaging" / "mac" / "resources" / filename,
        ]
    else:
        base = Path(__file__).resolve().parents[2]
        candidates = [
            base / "packaging" / "mac" / "resources" / filename,
            base / "assets" / filename,
        ]

    for path in candidates:
        if path.exists():
            return path

    return candidates[0]

def is_macos():
    return platform.system() == "Darwin"

def obs_installed():
    return Path("/Applications/OBS.app").exists()

def ndi_runtime_installed():
    return Path("/usr/local/lib/libndi.dylib").exists()
# def ndi_tools_installed():
#     return Path("/Library/NDI SDK for Apple").exists() or Path("/usr/local/lib").exists()

def ensure_distroav_ready():
    user_path = Path.home() / "Library/Application Support/obs-studio/plugins/distroav.plugin"
    system_path = Path("/Library/Application Support/obs-studio/plugins/distroav.plugin")

    user_exists = user_path.exists()
    system_exists = system_path.exists()

    print(f"[DISTROAV] system={system_exists}, user={user_exists}")

    # Case 1: both exist
    if system_exists and user_exists:
        return True

    # Case 2: system exists, user missing
    if system_exists and not user_exists:
        user_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(system_path, user_path)
        return True

    # Case 3 and 4: system missing
    install_pkg("distroav-6.1.1-macos-universal.pkg")

    # Re-check after install
    system_exists = system_path.exists()
    if not system_exists:
        raise RuntimeError("DistroAV package install completed, but system plugin was not found.")

    user_path.parent.mkdir(parents=True, exist_ok=True)

    if user_path.exists():
        shutil.rmtree(user_path)

    shutil.copytree(system_path, user_path)
    return True

def obs_scene_config_present():
    return (
        Path.home()
        / "Library/Application Support/obs-studio/basic/scenes/CamComposite.json"
    ).exists()

def install_obs():
    dmg = _resource_path("obs-studio-32.0.4-macos-apple.dmg")
    if not dmg.exists():
        raise FileNotFoundError(f"OBS dmg not found: {dmg}")

    result = subprocess.run(
        ["hdiutil", "attach", str(dmg), "-nobrowse"],
        check=True,
        capture_output=True,
        text=True,
    )

    mount_point = None
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[-1].startswith("/Volumes/"):
            mount_point = parts[-1].strip()
            break

    if not mount_point:
        raise RuntimeError("Could not determine OBS dmg mount point.")

    try:
        app_path = Path(mount_point) / "OBS.app"
        if not app_path.exists():
            raise RuntimeError(f"OBS.app not found in mounted dmg: {mount_point}")

        subprocess.run(["cp", "-R", str(app_path), "/Applications/"], check=True)
    finally:
        subprocess.run(["hdiutil", "detach", mount_point], check=False)
# def install_obs():
#     dmg = _resource_path("obs-studio-32.0.4-macos-apple.dmg")
#     if not dmg.exists():
#         raise FileNotFoundError(f"OBS dmg not found: {dmg}")
#
#     subprocess.run(["hdiutil", "attach", str(dmg), "-nobrowse"], check=True)
#     try:
#         for volume in ["/Volumes/OBS", "/Volumes/OBS Studio"]:
#             app_path = Path(volume) / "OBS.app"
#             if app_path.exists():
#                 subprocess.run(["cp", "-R", str(app_path), "/Applications/"], check=True)
#                 return
#         raise RuntimeError("OBS.app not found in mounted dmg.")
#     finally:
#         subprocess.run(["hdiutil", "detach", "/Volumes/OBS"], check=False)
#         subprocess.run(["hdiutil", "detach", "/Volumes/OBS Studio"], check=False)

def install_pkg(pkg_name: str):
    pkg = _resource_path(pkg_name)
    if not pkg.exists():
        raise FileNotFoundError(f"Package not found: {pkg}")

    print(f"[SETUP] Starting PKG install: {pkg_name}")

    cmd = f'installer -pkg "{str(pkg)}" -target /'
    apple_cmd = cmd.replace("\\", "\\\\").replace('"', '\\"')

    prompt = (
        f"CamComposite needs to install a package to continue setup. "
        "Please enter your Mac administrator password."
    )
    apple_prompt = prompt.replace("\\", "\\\\").replace('"', '\\"')

    result = subprocess.run(
        [
            "osascript",
            "-e",
            f'do shell script "{apple_cmd}" with administrator privileges with prompt "{apple_prompt}"',
        ],
        check=True,
        text=True,
    )

    print(f"[SETUP] Finished PKG install: {pkg_name} (returncode={result.returncode})")
# def install_pkg(pkg_name: str):
#     pkg = _resource_path(pkg_name)
#     if not pkg.exists():
#         raise FileNotFoundError(f"Package not found: {pkg}")
#
#     subprocess.run(["sudo", "installer", "-pkg", str(pkg), "-target", "/"], check=True)

def copy_obs_scene_config():
    src = _resource_path("CamComposite.json")
    if not src.exists():
        raise FileNotFoundError(f"OBS config not found: {src}")

    dst_dir = Path.home() / "Library/Application Support/obs-studio/basic/scenes"
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / "CamComposite.json")