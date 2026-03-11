import threading
import traceback
import tkinter as tk

from app import CamCompositeApp
from ui.startup_splash import StartupSplash

from helpers.mac_first_run_check import (
    is_macos,
    obs_installed,
    ensure_distroav_ready,
    ndi_runtime_installed,
    obs_scene_config_present,
    install_obs,
    install_pkg,
    copy_obs_scene_config,
)

from helpers.win_first_run_check import (
    is_windows,
    ensure_windows_requirements,
)


def run_startup_setup(root, splash):
    try:
        if is_macos():
            splash.set_status("Checking OBS...", "Verifying required macOS dependencies.")
            splash.append_log("Checking OBS installation...")
            if not obs_installed():
                splash.append_log("OBS not found. Installing OBS...")
                install_obs()
                splash.append_log("OBS installed.")

            splash.set_status("Checking DistroAV...", "Verifying OBS plugin.")
            splash.append_log("Ensuring DistroAV is ready...")
            splash.append_log("CamComposite may now request administrator permission to install it.")
            ensure_distroav_ready()
            splash.append_log("DistroAV is ready.")

            splash.set_status("Checking NDI Runtime...", "Verifying NDI runtime.")
            splash.append_log("Checking NDI runtime...")
            if not ndi_runtime_installed():
                splash.append_log("NDI runtime not found.")
                splash.append_log("CamComposite will now request administrator permission to install it.")
                install_pkg("libNDI_for_Mac.pkg")

                if not ndi_runtime_installed():
                    raise RuntimeError("NDI runtime installation did not complete successfully.")

                splash.append_log("NDI runtime installed.")

            splash.set_status("Checking OBS config...", "Preparing CamComposite scene collection.")
            splash.append_log("Checking OBS scene config...")
            if not obs_scene_config_present():
                copy_obs_scene_config()
                splash.append_log("OBS scene config copied.")

        elif is_windows():
            ensure_windows_requirements(splash)

        else:
            raise RuntimeError("Unsupported operating system.")

        splash.set_status("Launching CamComposite...", "Setup complete.")
        splash.append_log("Setup complete. Launching app...")
        root.after(300, lambda: launch_main_app(root, splash))

    except Exception as e:
        splash.set_status("Setup failed", str(e))
        splash.append_log(f"ERROR: {e}")
        splash.append_log(traceback.format_exc())


def launch_main_app(root, splash):
    splash.shutdown()
    splash.destroy()
    root.destroy()
    app = CamCompositeApp()
    app.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    splash = StartupSplash(root)

    worker = threading.Thread(target=run_startup_setup, args=(root, splash), daemon=True)
    worker.start()

    root.mainloop()