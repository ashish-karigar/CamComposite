# obs_mac_controller.py
import subprocess
import time

from obsws_python import ReqClient


OBS_VIRTUAL_CAMERA_EXTENSION_ID = (
    "com.obsproject.obs-studio.mac-camera-extension"
)
CAMERA_EXTENSIONS_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.LoginItems-Settings.extension"
)


class OBSVirtualCameraApprovalRequired(RuntimeError):
    pass


class MacOBSController:
    def __init__(
        self,
        scene_name: str = "CamComposite",
        obs_app_path: str = "/Applications/OBS.app",
        host: str = "localhost",
        port: int = 4455,
        password: str = "mylens123",
    ):
        self.scene_name = scene_name
        self.obs_app_path = obs_app_path
        self.host = host
        self.port = port
        self.password = password

        self.obs_proc = None
        self.client = None
        self.is_running = False
        self._obs_was_launched_by_us = False
        self._restart_obs_before_next_start = False

    def start(self):
        if self.is_running:
            print("OBS controller already running")
            return

        self.obs_proc = self._launch_obs()
        self._obs_was_launched_by_us = True
        print("Launched OBS")

        time.sleep(3)

        self.client = self._connect_obs()
        self._wait_until_obs_ready()
        self._start_virtual_camera()

        self.is_running = True
        print("OBS pipeline started")

    def ensure_virtual_camera_extension_approved(self, timeout=300.0):
        """Trigger and wait for the one-time macOS camera-extension approval."""
        if self._virtual_camera_extension_active():
            print("[OBS] Camera extension is active.")
            return False

        self.obs_proc = self._launch_obs()
        self._obs_was_launched_by_us = True
        print("[OBS] Launching OBS to request Camera Extension approval...")
        time.sleep(3)
        self.client = self._connect_obs()

        try:
            self._start_virtual_camera()
        except OBSVirtualCameraApprovalRequired:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self._virtual_camera_extension_active():
                    print("[OBS] Camera extension approval detected.")
                    self._restart_obs_after_extension_approval()
                    return True
                time.sleep(1)

            raise RuntimeError(
                "OBS Camera Extension approval timed out. Enable it in System "
                "Settings, then launch CamComposite again."
            )

        # Starting succeeded even though systemextensionsctl did not report the
        # extension yet. Stop the temporary camera and OBS before app startup.
        self._restart_obs_after_extension_approval()
        return True

    def _restart_obs_after_extension_approval(self):
        try:
            if self.client is not None:
                self._stop_virtual_camera(self.client)
        finally:
            self.client = None
            self._quit_obs_app()
            time.sleep(2)
            self.obs_proc = None
            self._obs_was_launched_by_us = False
            self._restart_obs_before_next_start = False

    def hide_obs(self):
        self._hide_obs_app()

    def stop(self):
        if not self.is_running and self.client is None and self.obs_proc is None:
            print("OBS controller already stopped")
            return

        client = self.client
        obs_proc = self.obs_proc
        obs_was_launched_by_us = self._obs_was_launched_by_us

        # Mark stopped before cleanup so repeated stop calls do not fight this one.
        self.client = None
        self.obs_proc = None
        self.is_running = False
        self._obs_was_launched_by_us = False

        try:
            if client is not None:
                self._stop_virtual_camera(client)
        except Exception as e:
            print(f"Could not stop virtual camera cleanly: {e}")

        try:
            if obs_was_launched_by_us:
                self._quit_obs_app()
                self._wait_for_process_exit(obs_proc, "OBS", timeout=10)
        except Exception as e:
            print(f"Could not quit OBS cleanly: {e}")

        print("OBS pipeline stopped")

    def _launch_obs(self):
        if self._restart_obs_before_next_start:
            self._quit_obs_app()
            time.sleep(2)
            self._restart_obs_before_next_start = False

        return subprocess.Popen(["open", "-g", self.obs_app_path])

    def _virtual_camera_extension_active(self):
        result = subprocess.run(
            ["systemextensionsctl", "list"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False

        for line in result.stdout.splitlines():
            if OBS_VIRTUAL_CAMERA_EXTENSION_ID not in line:
                continue

            normalized = line.lower()
            return "activated enabled" in normalized

        return False

    def _request_virtual_camera_approval(self):
        self._restart_obs_before_next_start = True

        # OBS owns the extension request. Keep its system prompt visible, then
        # take the user directly to the page where macOS requires their approval.
        subprocess.run(
            ["osascript", "-e", 'tell application "OBS" to activate'],
            check=False,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["open", CAMERA_EXTENSIONS_SETTINGS_URL],
            check=False,
        )

    def _hide_obs_app(self):
        script = """
        tell application "System Events"
            set visible of process "OBS" to false
        end tell
        """
        subprocess.run(["osascript", "-e", script], check=False)

    def _quit_obs_app(self):
        script = 'tell application "OBS" to quit'
        subprocess.run(["osascript", "-e", script], check=False)

    def _wait_for_process_exit(self, proc, name, timeout=10):
        if proc is None:
            return

        if proc.poll() is not None:
            print(f"{name} already exited")
            return

        try:
            proc.wait(timeout=timeout)
            print(f"{name} exited cleanly")
        except subprocess.TimeoutExpired:
            print(f"{name} did not exit in time; leaving it running to avoid crash dialog")

    def _connect_obs(self, retries=30, delay=1.0):
        for attempt in range(retries):
            try:
                client = ReqClient(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    timeout=5,
                )
                print(f"Connected to OBS on attempt {attempt + 1}")
                return client
            except Exception as e:
                print(f"Waiting for OBS websocket... {attempt + 1}/{retries} -> {e}")
                time.sleep(delay)

        raise RuntimeError("Could not connect to OBS websocket")

    def _wait_until_obs_ready(self, retries=30, delay=1.0):
        for attempt in range(retries):
            try:
                if self.client is None:
                    raise RuntimeError("OBS websocket client is not connected")

                scenes = self.client.get_scene_list()
                scene_names = [s["sceneName"] for s in scenes.scenes]
                print("Available scenes:", scene_names)

                if self.scene_name not in scene_names:
                    raise RuntimeError(f"Scene '{self.scene_name}' not found in OBS")

                self.client.set_current_program_scene(self.scene_name)
                print(f"Switched to scene: {self.scene_name}")
                return

            except Exception as e:
                print(f"OBS not ready yet... {attempt + 1}/{retries} -> {e}")
                time.sleep(delay)

        raise RuntimeError("OBS opened, but never became ready")

    def _start_virtual_camera(self, retries=10, delay=1.0):
        extension_was_active = self._virtual_camera_extension_active()

        for attempt in range(retries):
            try:
                if self.client is None:
                    raise RuntimeError("OBS websocket client is not connected")

                self.client.start_virtual_cam()
                print("Virtual camera started")
                return
            except Exception as e:
                if not extension_was_active:
                    self._request_virtual_camera_approval()
                    raise OBSVirtualCameraApprovalRequired(
                        "Enable the OBS Camera Extension in System Settings, "
                        "then return to CamComposite and press Start again."
                    ) from e

                print(f"Could not start virtual camera yet... {attempt + 1}/{retries} -> {e}")
                time.sleep(delay)

        raise RuntimeError("Could not start OBS virtual camera")

    def _stop_virtual_camera(self, client, retries=3, delay=0.5):
        if client is None:
            return

        for attempt in range(retries):
            try:
                client.stop_virtual_cam()
                print("Virtual camera stopped")
                return
            except Exception as e:
                message = str(e)

                # OBS already closing / websocket gone. No point retrying noisily.
                if (
                    "Connection to remote host was lost" in message
                    or "Expecting value" in message
                    or "not ready" in message
                ):
                    print(f"Virtual camera stop skipped: OBS is already closing ({message})")
                    return

                print(f"Could not stop virtual camera yet... {attempt + 1}/{retries} -> {e}")
                time.sleep(delay)

        print("Warning: could not stop virtual camera cleanly")
