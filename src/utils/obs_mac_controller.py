# obs_mac_controller.py
import subprocess
import time

from obsws_python import ReqClient


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

    def hide_obs(self):
        self._hide_obs_app()

    def stop(self):
        if not self.is_running and self.client is None and self.obs_proc is None:
            print("OBS controller already stopped")
            return

        try:
            if self.client is not None:
                self._stop_virtual_camera()
        except Exception as e:
            print(f"Could not stop virtual camera cleanly: {e}")

        try:
            if self._obs_was_launched_by_us:
                self._quit_obs_app()
                self._wait_for_process_exit(self.obs_proc, "OBS", timeout=10)
        except Exception as e:
            print(f"Could not quit OBS cleanly: {e}")

        self.client = None
        self.obs_proc = None
        self.is_running = False
        self._obs_was_launched_by_us = False

        print("OBS pipeline stopped")

    def _launch_obs(self):
        return subprocess.Popen(["open", "-g", self.obs_app_path])

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
                    timeout=5
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
        for attempt in range(retries):
            try:
                self.client.start_virtual_cam()
                print("Virtual camera started")
                return
            except Exception as e:
                print(f"Could not start virtual camera yet... {attempt + 1}/{retries} -> {e}")
                time.sleep(delay)

        raise RuntimeError("Could not start OBS virtual camera")

    def _stop_virtual_camera(self, retries=10, delay=0.5):
        for attempt in range(retries):
            try:
                self.client.stop_virtual_cam()
                print("Virtual camera stopped")
                return
            except Exception as e:
                print(f"Could not stop virtual camera yet... {attempt + 1}/{retries} -> {e}")
                time.sleep(delay)

        print("Warning: could not stop virtual camera cleanly")