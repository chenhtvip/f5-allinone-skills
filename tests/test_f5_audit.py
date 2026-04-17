"""f5_audit.py 单元测试"""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "f5-allinone"))
from f5_audit import F5Audit

VALID_YAML = """
devices:
  - name: f5-prod-01
    host: 10.1.1.14
    port: 443
    username: admin
    password: secret
"""

MOCK_MONITOR = {
    "cpu": {"cpu_usage_pct": 5, "cpu_idle_pct": 95, "cpu_system_pct": 2, "cpu_user_pct": 3},
    "memory": {"memory_total_mb": 8192, "memory_used_mb": 3400, "memory_free_mb": 4792, "memory_usage_pct": 41.5},
    "connections": {"active_connections": 1280, "new_connections_per_sec": 50},
    "throughput": {"throughput_bps": 120000000, "throughput_mbps": 120.0, "in_bps": 60000000, "out_bps": 60000000},
    "ha": {"ha_status": "ACTIVE", "ha_color": "green", "is_active": True},
    "sync": {"sync_status": "In Sync", "sync_color": "green", "sync_summary": "", "is_synced": True},
    "interfaces": [],
}

MOCK_SSL = {
    "total": 5,
    "expired": [],
    "critical": [],
    "warning": [],
    "ok": [],
    "status": "OK",
}


def _write_tmp(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


class TestF5Audit(unittest.TestCase):

    def setUp(self):
        self.yaml_path = _write_tmp(VALID_YAML)

    def tearDown(self):
        os.unlink(self.yaml_path)

    @patch("f5_audit.F5Monitor")
    @patch("f5_audit.F5SSL")
    @patch("f5_audit.F5Client")
    def test_run_device_success(self, mock_client_cls, mock_ssl_cls, mock_monitor_cls):
        mock_monitor_cls.return_value.get_all_status.return_value = MOCK_MONITOR
        mock_ssl_cls.return_value.get_summary_report.return_value = MOCK_SSL

        audit = F5Audit(self.yaml_path)
        device = {"name": "f5-prod-01", "host": "10.1.1.14", "port": 443, "username": "admin", "password": "secret"}
        result = audit.run_device(device)

        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["error"])
        self.assertEqual(result["monitor"], MOCK_MONITOR)
        self.assertEqual(result["ssl"], MOCK_SSL)

    @patch("f5_audit.F5Client")
    def test_run_device_connection_error(self, mock_client_cls):
        mock_client_cls.side_effect = ConnectionError("无法连接")

        audit = F5Audit(self.yaml_path)
        device = {"name": "f5-prod-01", "host": "10.1.1.14", "port": 443, "username": "admin", "password": "secret"}
        result = audit.run_device(device)

        self.assertEqual(result["status"], "error")
        self.assertIn("无法连接", result["error"])
        self.assertIsNone(result["monitor"])

    @patch("f5_audit.F5Monitor")
    @patch("f5_audit.F5SSL")
    @patch("f5_audit.F5Client")
    def test_run_all_returns_results_for_all_devices(self, mock_client_cls, mock_ssl_cls, mock_monitor_cls):
        mock_monitor_cls.return_value.get_all_status.return_value = MOCK_MONITOR
        mock_ssl_cls.return_value.get_summary_report.return_value = MOCK_SSL

        audit = F5Audit(self.yaml_path)
        results = audit.run_all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "f5-prod-01")

    @patch("f5_audit.F5Monitor")
    @patch("f5_audit.F5SSL")
    @patch("f5_audit.F5Client")
    def test_export_csv_creates_file(self, mock_client_cls, mock_ssl_cls, mock_monitor_cls):
        mock_monitor_cls.return_value.get_all_status.return_value = MOCK_MONITOR
        mock_ssl_cls.return_value.get_summary_report.return_value = MOCK_SSL

        audit = F5Audit(self.yaml_path)
        results = audit.run_all()

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            csv_path = tmp.name
        try:
            audit.export_csv(results, csv_path)
            self.assertTrue(os.path.exists(csv_path))
            with open(csv_path, encoding="utf-8-sig") as f:
                content = f.read()
            self.assertIn("f5-prod-01", content)
            self.assertIn("ACTIVE", content)
            self.assertIn("OK", content)
        finally:
            os.unlink(csv_path)

    @patch("f5_audit.F5Monitor")
    @patch("f5_audit.F5SSL")
    @patch("f5_audit.F5Client")
    def test_export_csv_error_device_has_empty_metrics(self, mock_client_cls, mock_ssl_cls, mock_monitor_cls):
        mock_client_cls.side_effect = ConnectionError("timeout")

        audit = F5Audit(self.yaml_path)
        device = {"name": "f5-prod-01", "host": "10.1.1.14", "port": 443, "username": "admin", "password": "secret"}
        results = [audit.run_device(device)]

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            csv_path = tmp.name
        try:
            audit.export_csv(results, csv_path)
            with open(csv_path, encoding="utf-8-sig") as f:
                content = f.read()
            self.assertIn("error", content)
            self.assertIn("timeout", content)
        finally:
            os.unlink(csv_path)


if __name__ == "__main__":
    unittest.main()
