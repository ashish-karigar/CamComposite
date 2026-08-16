import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.helpers import mac_first_run_check


class EnsureOBSWebSocketConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "config.json"

    def _ensure(self):
        with (
            mock.patch.object(
                mac_first_run_check,
                "_obs_websocket_config_path",
                return_value=self.config_path,
            ),
            mock.patch.object(
                mac_first_run_check,
                "_stop_obs_for_configuration",
            ) as stop_obs,
        ):
            changed = mac_first_run_check.ensure_obs_websocket_config()
        return changed, stop_obs

    def test_creates_required_websocket_configuration(self):
        changed, stop_obs = self._ensure()

        self.assertTrue(changed)
        stop_obs.assert_called_once_with()
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["server_enabled"], True)
        self.assertEqual(config["server_port"], 4455)
        self.assertEqual(config["auth_required"], True)
        self.assertEqual(config["server_password"], "mylens123")
        self.assertEqual(config["first_load"], False)

    def test_preserves_unrelated_settings(self):
        self.config_path.write_text(
            json.dumps({"alerts_enabled": True, "server_enabled": False}),
            encoding="utf-8",
        )

        self._ensure()

        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["alerts_enabled"], True)

    def test_does_not_stop_obs_or_rewrite_when_already_configured(self):
        existing = {
            "alerts_enabled": False,
            "server_enabled": True,
            "server_port": 4455,
            "auth_required": True,
            "server_password": "mylens123",
            "first_load": False,
        }
        self.config_path.write_text(json.dumps(existing), encoding="utf-8")

        changed, stop_obs = self._ensure()

        self.assertFalse(changed)
        stop_obs.assert_not_called()
        self.assertEqual(
            json.loads(self.config_path.read_text(encoding="utf-8")),
            existing,
        )


if __name__ == "__main__":
    unittest.main()
