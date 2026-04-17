"""f5_inventory.py 单元测试"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "f5-allinone"))
from f5_inventory import F5Inventory

VALID_YAML = """
devices:
  - name: f5-prod-01
    host: 10.1.1.14
    port: 443
    username: admin
    password: secret
  - name: f5-prod-02
    host: 10.1.1.15
    port: 443
    username: admin
    password: secret2
"""

MISSING_FIELD_YAML = """
devices:
  - name: f5-prod-01
    host: 10.1.1.14
    port: 443
    username: admin
"""

NO_DEVICES_KEY_YAML = """
hosts:
  - name: f5-prod-01
"""


def _write_tmp(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


class TestF5Inventory(unittest.TestCase):

    def test_load_returns_device_list(self):
        path = _write_tmp(VALID_YAML)
        try:
            inv = F5Inventory(path)
            devices = inv.load()
            self.assertEqual(len(devices), 2)
            self.assertEqual(devices[0]["name"], "f5-prod-01")
            self.assertEqual(devices[0]["host"], "10.1.1.14")
            self.assertEqual(devices[0]["port"], 443)
            self.assertEqual(devices[0]["username"], "admin")
            self.assertEqual(devices[0]["password"], "secret")
        finally:
            os.unlink(path)

    def test_load_file_not_found(self):
        inv = F5Inventory("/nonexistent/path/inventory.yaml")
        with self.assertRaises(FileNotFoundError):
            inv.load()

    def test_load_missing_devices_key(self):
        path = _write_tmp(NO_DEVICES_KEY_YAML)
        try:
            inv = F5Inventory(path)
            with self.assertRaises(ValueError):
                inv.load()
        finally:
            os.unlink(path)

    def test_validate_passes_for_valid_yaml(self):
        path = _write_tmp(VALID_YAML)
        try:
            errors = F5Inventory(path).validate()
            self.assertEqual(errors, [])
        finally:
            os.unlink(path)

    def test_validate_reports_missing_password(self):
        path = _write_tmp(MISSING_FIELD_YAML)
        try:
            errors = F5Inventory(path).validate()
            self.assertTrue(any("password" in e for e in errors))
        finally:
            os.unlink(path)

    def test_validate_file_not_found(self):
        errors = F5Inventory("/nonexistent/inventory.yaml").validate()
        self.assertTrue(len(errors) > 0)

    def test_default_port_is_443(self):
        yaml_no_port = """
devices:
  - name: f5-test
    host: 10.0.0.1
    username: admin
    password: pass
"""
        path = _write_tmp(yaml_no_port)
        try:
            devices = F5Inventory(path).load()
            self.assertEqual(devices[0]["port"], 443)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
