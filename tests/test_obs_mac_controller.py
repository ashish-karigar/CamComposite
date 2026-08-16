import unittest
from unittest import mock

from src.utils.obs_mac_controller import (
    MacOBSController,
    OBSVirtualCameraApprovalRequired,
)


class StartVirtualCameraTests(unittest.TestCase):
    def setUp(self):
        self.controller = MacOBSController()
        self.controller.client = mock.Mock()

    def test_opens_settings_when_extension_needs_approval(self):
        self.controller.client.start_virtual_cam.side_effect = RuntimeError("not installed")

        with (
            mock.patch.object(
                self.controller,
                "_virtual_camera_extension_active",
                return_value=False,
            ),
            mock.patch.object(
                self.controller,
                "_request_virtual_camera_approval",
            ) as request_approval,
        ):
            with self.assertRaises(OBSVirtualCameraApprovalRequired):
                self.controller._start_virtual_camera()

        request_approval.assert_called_once_with()
        self.controller.client.start_virtual_cam.assert_called_once_with()

    def test_starts_normally_when_extension_is_active(self):
        with mock.patch.object(
            self.controller,
            "_virtual_camera_extension_active",
            return_value=True,
        ):
            self.controller._start_virtual_camera(retries=1, delay=0)

        self.controller.client.start_virtual_cam.assert_called_once_with()

    def test_startup_check_skips_obs_when_extension_is_active(self):
        with (
            mock.patch.object(
                self.controller,
                "_virtual_camera_extension_active",
                return_value=True,
            ),
            mock.patch.object(self.controller, "_launch_obs") as launch_obs,
        ):
            changed = self.controller.ensure_virtual_camera_extension_approved()

        self.assertFalse(changed)
        launch_obs.assert_not_called()

    def test_startup_check_waits_for_user_approval_then_restarts_obs(self):
        process = mock.Mock()
        client = mock.Mock()

        with (
            mock.patch.object(
                self.controller,
                "_virtual_camera_extension_active",
                side_effect=[False, True],
            ),
            mock.patch.object(
                self.controller,
                "_launch_obs",
                return_value=process,
            ),
            mock.patch.object(
                self.controller,
                "_connect_obs",
                return_value=client,
            ),
            mock.patch.object(
                self.controller,
                "_start_virtual_camera",
                side_effect=OBSVirtualCameraApprovalRequired("approval required"),
            ),
            mock.patch.object(
                self.controller,
                "_restart_obs_after_extension_approval",
            ) as restart_obs,
            mock.patch("src.utils.obs_mac_controller.time.sleep"),
        ):
            changed = self.controller.ensure_virtual_camera_extension_approved()

        self.assertTrue(changed)
        restart_obs.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
