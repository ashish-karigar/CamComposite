import subprocess
import sys
import time
import signal
from pathlib import Path

from obsws_python import ReqClient

OBS_PATH = "/Applications/OBS.app/Contents/MacOS/OBS"
OBS_PORT = 4455
OBS_PASSWORD = "mylens123"
SCENE_NAME = "CamComposite"

NDI_SCRIPT = "run_mac_ndi_to_obs_prototype.py"


def launch_obs():
    return subprocess.Popen(["open", "-g", "/Applications/OBS.app"])


def hide_obs_app():
    # Hide OBS window on macOS
    script = '''
    tell application "System Events"
        set visible of process "OBS" to false
    end tell
    '''
    subprocess.run(["osascript", "-e", script], check=False)


def quit_obs_app():
    script = 'tell application "OBS" to quit'
    subprocess.run(["osascript", "-e", script], check=False)


def wait_for_process_exit(proc, name, timeout=10):
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
            print(f"Waiting for OBS websocket... {attempt + 1}/{retries} -> {e}")
            time.sleep(delay)

    raise RuntimeError("Could not connect to OBS websocket")


def wait_until_obs_ready(client, scene_name, retries=30, delay=1.0):
    for attempt in range(retries):
        try:
            scenes = client.get_scene_list()
            scene_names = [s["sceneName"] for s in scenes.scenes]
            print("Available scenes:", scene_names)

            if scene_name not in scene_names:
                raise RuntimeError(f"Scene '{scene_name}' not found in OBS")

            client.set_current_program_scene(scene_name)
            print(f"Switched to scene: {scene_name}")
            return

        except Exception as e:
            print(f"OBS not ready yet... {attempt + 1}/{retries} -> {e}")
            time.sleep(delay)

    raise RuntimeError("OBS opened, but never became ready")


def start_virtual_camera(client, retries=10, delay=1.0):
    for attempt in range(retries):
        try:
            client.start_virtual_cam()
            print("Virtual camera started")
            return
        except Exception as e:
            print(f"Could not start virtual camera yet... {attempt + 1}/{retries} -> {e}")
            time.sleep(delay)

    raise RuntimeError("Could not start OBS virtual camera")


def stop_virtual_camera(client, retries=10, delay=0.5):
    for attempt in range(retries):
        try:
            client.stop_virtual_cam()
            print("Virtual camera stopped")
            return
        except Exception as e:
            print(f"Could not stop virtual camera yet... {attempt + 1}/{retries} -> {e}")
            time.sleep(delay)

    print("Warning: could not stop virtual camera cleanly")


def terminate_process(proc, name, timeout=5):
    if proc is None:
        return

    if proc.poll() is not None:
        return

    try:
        proc.terminate()
        proc.wait(timeout=timeout)
        print(f"{name} terminated")
    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"{name} killed")


def main():
    obs_proc = None
    ndi_proc = None
    client = None

    try:
        ndi_proc = subprocess.Popen([sys.executable, NDI_SCRIPT])
        print("Started NDI sender")

        obs_proc = launch_obs()
        print("Launched OBS")

        time.sleep(3)

        client = connect_obs()
        wait_until_obs_ready(client, SCENE_NAME)
        start_virtual_camera(client)

        time.sleep(1)
        hide_obs_app()
        print("OBS hidden")

        print("Everything is running. Press Ctrl+C to stop.")

        while True:
            if ndi_proc.poll() is not None:
                raise RuntimeError("NDI sender stopped unexpectedly")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping everything...")


    finally:

        if client is not None:

            try:

                stop_virtual_camera(client)

            except Exception as e:

                print(f"Could not stop virtual camera cleanly: {e}")

        quit_obs_app()

        wait_for_process_exit(obs_proc, "OBS", timeout=10)

        terminate_process(ndi_proc, "NDI sender")


if __name__ == "__main__":
    main()