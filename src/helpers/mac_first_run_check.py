import os
import socket
import subprocess
from dataclasses import dataclass
from typing import Optional, Dict, Any

from obsws_python import ReqClient


OBS_APP_BUNDLE = "/Applications/OBS.app"
OBS_EXECUTABLE = "/Applications/OBS.app/Contents/MacOS/OBS"
OBS_PASSWORD = "mylens123"


@dataclass
class CheckResult:
    ok: bool
    status: str
    detail: str = ""


def check_obs_installed() -> CheckResult:
    """
    Simple file-system check for OBS installation.
    """
    if os.path.exists(OBS_APP_BUNDLE) and os.path.exists(OBS_EXECUTABLE):
        return CheckResult(True, "installed", "OBS.app found in /Applications")
    return CheckResult(False, "missing", "OBS.app was not found in /Applications")


def check_port_open(host: str = "127.0.0.1", port: int = 4455, timeout: float = 1.0) -> bool:
    """
    Low-level socket probe. Useful before trying obs-websocket auth.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_obs_websocket(port: int = 4455, password: Optional[str] = None) -> CheckResult:
    """
    Checks whether OBS websocket is enabled/reachable.

    Cases:
    - port closed -> websocket disabled / OBS not running
    - port open + valid auth -> enabled and reachable
    - port open + invalid password -> enabled, but auth failed
    """
    port_open = check_port_open(port=port)
    if not port_open:
        return CheckResult(
            False,
            "unreachable",
            f"No server reachable on localhost:{port}. OBS may be closed or websocket may be disabled."
        )

    if password is None:
        return CheckResult(
            True,
            "reachable",
            f"Port {port} is open. OBS websocket appears reachable, but auth was not tested."
        )

    try:
        client = ReqClient(host="localhost", port=port, password=password, timeout=3)
        version_info = client.get_version()
        return CheckResult(
            True,
            "enabled",
            f"Connected successfully. OBS version: {version_info.obs_version}"
        )
    except Exception as e:
        msg = str(e)

        # If auth fails, the server is still there, which tells us websocket is enabled.
        auth_markers = [
            "authentication",
            "identify",
            "auth",
            "password",
            "401",
        ]
        if any(marker in msg.lower() for marker in auth_markers):
            return CheckResult(
                True,
                "enabled_auth_failed",
                "OBS websocket is reachable, but the password was rejected."
            )

        return CheckResult(
            False,
            "error",
            f"Websocket port is open, but connection failed: {msg}"
        )


def _run_osascript(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )


def check_hide_permission() -> CheckResult:
    """
    Checks whether the current host app (Terminal/PyCharm/future packaged app)
    appears to have permission to use System Events.

    This may trigger a macOS permission prompt the first time.
    """
    script = '''
    tell application "System Events"
        return name of first process
    end tell
    '''

    result = _run_osascript(script)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    combined = f"{stdout} {stderr}".strip().lower()

    if result.returncode == 0:
        return CheckResult(
            True,
            "granted",
            "System Events control is available."
        )

    # Common denial patterns on macOS
    denial_markers = [
        "not authorized",
        "not allowed",
        "access not allowed",
        "(-1743)",
        "osascript is not allowed",
        "system events got an error",
    ]
    if any(marker in combined for marker in denial_markers):
        return CheckResult(
            False,
            "denied",
            "Accessibility / automation permission is not granted for the current app."
        )

    return CheckResult(
        False,
        "unknown",
        f"Could not verify hide permission. osascript returned: {stderr or stdout or 'no output'}"
    )


def run_all_checks(obs_password: Optional[str] = None, obs_port: int = 4455) -> Dict[str, Any]:
    obs_result = check_obs_installed()
    ws_result = check_obs_websocket(port=obs_port, password=obs_password)
    hide_result = check_hide_permission()

    overall_ok = obs_result.ok and ws_result.ok

    return {
        "overall_ok": overall_ok,
        "obs_installed": obs_result,
        "obs_websocket": ws_result,
        "hide_permission": hide_result,
    }


def print_report(report: Dict[str, Any]) -> None:
    print("\n=== Mac First-Run Check ===")

    for key in ["obs_installed", "obs_websocket", "hide_permission"]:
        item: CheckResult = report[key]
        print(f"\n{key}:")
        print(f"  ok     : {item.ok}")
        print(f"  status : {item.status}")
        print(f"  detail : {item.detail}")

    print(f"\noverall_ok: {report['overall_ok']}")


if __name__ == "__main__":
    # Put your OBS websocket password here if you want auth tested.
    OBS_PASSWORD = "mylens123"
    # Example:
    # OBS_PASSWORD = "mylens123"

    report = run_all_checks(obs_password=OBS_PASSWORD, obs_port=4455)
    print_report(report)