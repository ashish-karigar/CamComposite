from pathlib import Path
import json
import os
import shlex
import shutil
import subprocess
import time


OBS_WEBSOCKET_PORT = 4455
OBS_WEBSOCKET_PASSWORD = "mylens123"


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


def _obs_websocket_config_path():
    return (
        Path.home()
        / "Library/Application Support/obs-studio/plugin_config/obs-websocket/config.json"
    )


def _obs_is_running():
    result = subprocess.run(
        ["osascript", "-e", 'application "OBS" is running'],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _stop_obs_for_configuration(timeout=10.0):
    if not _obs_is_running():
        return False

    print("[OBS] Stopping OBS to apply WebSocket configuration...")
    subprocess.run(
        ["osascript", "-e", 'tell application "OBS" to quit'],
        check=False,
        capture_output=True,
        text=True,
    )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _obs_is_running():
            return True
        time.sleep(0.2)

    raise RuntimeError(
        "OBS is running and could not be stopped. Quit OBS and launch CamComposite again."
    )


def _read_json_object(path):
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as config_file:
            value = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read OBS WebSocket config: {path}") from exc

    if not isinstance(value, dict):
        raise RuntimeError(f"OBS WebSocket config is not a JSON object: {path}")

    return value


def ensure_obs_websocket_config():
    """Configure the OBS WebSocket server expected by CamComposite.

    OBS writes its configuration while quitting, so stop it only when a change is
    required, then re-read the file before applying the CamComposite settings.
    Returns True when the configuration changed.
    """
    config_path = _obs_websocket_config_path()
    required_settings = {
        "server_enabled": True,
        "server_port": OBS_WEBSOCKET_PORT,
        "auth_required": True,
        "server_password": OBS_WEBSOCKET_PASSWORD,
        "first_load": False,
    }

    current_config = _read_json_object(config_path)
    if all(current_config.get(key) == value for key, value in required_settings.items()):
        print("[OBS] WebSocket configuration is ready.")
        return False

    _stop_obs_for_configuration()

    # OBS may rewrite this file as it exits, so use the latest version and preserve
    # all settings CamComposite does not own.
    current_config = _read_json_object(config_path)
    current_config.update(required_settings)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_name(f".{config_path.name}.tmp")

    try:
        with temporary_path.open("w", encoding="utf-8") as config_file:
            json.dump(current_config, config_file, indent=2)
            config_file.write("\n")
            config_file.flush()
            os.fsync(config_file.fileno())
        temporary_path.replace(config_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    print(
        f"[OBS] WebSocket enabled on port {OBS_WEBSOCKET_PORT} "
        "with CamComposite authentication."
    )
    return True

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

        destination = Path("/Applications/OBS.app")
        try:
            subprocess.run(
                ["ditto", str(app_path), str(destination)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            install_command = (
                f"ditto {shlex.quote(str(app_path))} "
                f"{shlex.quote(str(destination))}"
            )
            apple_command = install_command.replace("\\", "\\\\").replace('"', '\\"')
            prompt = (
                "CamComposite needs administrator permission to install OBS "
                "in the Applications folder."
            )
            apple_prompt = prompt.replace("\\", "\\\\").replace('"', '\\"')

            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'do shell script "{apple_command}" with administrator '
                    f'privileges with prompt "{apple_prompt}"',
                ],
                check=True,
                text=True,
            )

        if not destination.exists():
            raise RuntimeError("OBS installation completed, but OBS.app was not found.")
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

# def copy_obs_scene_config():
#     src = _resource_path("CamComposite-OBS.json")
#     if not src.exists():
#         raise FileNotFoundError(f"OBS config not found: {src}")
#
#     dst_dir = Path.home() / "Library/Application Support/obs-studio/basic/scenes"
#     dst_dir.mkdir(parents=True, exist_ok=True)
#     shutil.copy2(src, dst_dir / "CamComposite.json")

def copy_obs_profile_config():
    src = _resource_path("basic.ini")
    if not src.exists():
        raise FileNotFoundError(f"OBS profile config not found: {src}")

    dst_dir = Path.home() / "Library/Application Support/obs-studio/basic/profiles/CamComposite"
    dst_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src, dst_dir / "basic.ini")

def copy_obs_scene_config():
    import json
    import socket

    src = _resource_path("CamComposite-OBS.json")
    if not src.exists():
        raise FileNotFoundError(f"OBS config not found: {src}")

    dst_dir = Path.home() / "Library/Application Support/obs-studio/basic/scenes"
    dst_dir.mkdir(parents=True, exist_ok=True)

    dst_file = dst_dir / "CamComposite.json"

    # Load bundled OBS scene JSON
    with open(src, "r", encoding="utf-8") as f:
        scene_config = json.load(f)

    # Current Mac hostname format OBS/NDI usually stores
    hostname = socket.gethostname().split(".")[0].upper()
    current_ndi_name = f"{hostname}.LOCAL (MyLens Program)"

    # Patch NDI source name inside OBS config
    for source in scene_config.get("sources", []):
        if source.get("id") == "ndi_source" and source.get("name") == "MyLens":
            source.setdefault("settings", {})
            source["settings"]["ndi_source_name"] = current_ndi_name

    # Save patched scene config
    with open(dst_file, "w", encoding="utf-8") as f:
        json.dump(scene_config, f, indent=4)

    print(f"OBS scene copied and patched with NDI source: {current_ndi_name}")
