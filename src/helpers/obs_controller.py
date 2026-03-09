# obs_controller.py
import subprocess
import time
from obsws_python import ReqClient

OBS_PATH = "/Applications/OBS.app/Contents/MacOS/OBS"
OBS_PORT = 4455
OBS_PASSWORD = "mylens123"
SCENE_NAME = "CamComposite"


def launch_obs():
    return subprocess.Popen([OBS_PATH])


def connect_obs(port=OBS_PORT, password=OBS_PASSWORD, retries=30, delay=1.0):
    for attempt in range(retries):
        try:
            client = ReqClient(
                host="localhost",
                port=port,
                password=password,
                timeout=5
            )
            print(f"Connected to OBS on attempt {attempt + 1}")
            return client
        except Exception as e:
            print(f"Waiting for OBS websocket... attempt {attempt + 1}/{retries} -> {e}")
            time.sleep(delay)

    raise RuntimeError("Could not connect to OBS websocket")


def wait_until_obs_ready(client, scene_name, retries=30, delay=1.0):
    for attempt in range(retries):
        try:
            # Try reading the scene list first
            scenes = client.get_scene_list()
            scene_names = [s["sceneName"] for s in scenes.scenes]
            print("Available scenes:", scene_names)

            if scene_name not in scene_names:
                raise RuntimeError(f"Scene '{scene_name}' not found in OBS")

            # Try switching once OBS is ready
            client.set_current_program_scene(scene_name)
            print(f"Switched to scene: {scene_name}")
            return

        except Exception as e:
            print(f"OBS not ready yet... attempt {attempt + 1}/{retries} -> {e}")
            time.sleep(delay)

    raise RuntimeError("OBS opened, but never became ready for scene switching")


def start_virtual_camera(client, retries=10, delay=1.0):
    for attempt in range(retries):
        try:
            client.start_virtual_cam()
            print("Virtual camera started")
            return
        except Exception as e:
            print(f"Could not start virtual camera yet... attempt {attempt + 1}/{retries} -> {e}")
            time.sleep(delay)

    raise RuntimeError("Could not start OBS virtual camera")


if __name__ == "__main__":
    launch_obs()
    time.sleep(3)  # initial startup buffer

    client = connect_obs()
    wait_until_obs_ready(client, SCENE_NAME)
    start_virtual_camera(client)

    print("OBS connected and virtual camera started.")