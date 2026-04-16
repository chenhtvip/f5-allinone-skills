import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'f5-allinone'))

from f5_ssl import F5SSL


class TestF5SSL:
    def setup_method(self):
        self.mock_client = MagicMock()
        self.ssl = F5SSL(self.mock_client)

    def test_list_certificates(self):
        self.mock_client.get.return_value = {
            "items": [
                {
                    "name": "example.com.crt",
                    "partition": "Common",
                    "expirationDate": 1893456000,
                    "subject": "CN=example.com",
                    "issuer": "CN=Let's Encrypt Authority X3"
                }
            ]
        }
        result = self.ssl.list_certificates()
        assert len(result) == 1
        cert = result[0]
        assert cert["name"] == "example.com.crt"
        assert "expiration_date" in cert
        assert "days_until_expiry" in cert

    def test_days_until_expiry_future(self):
        future_ts = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        self.mock_client.get.return_value = {
            "items": [{"name": "test.crt", "expirationDate": future_ts,
                        "subject": "CN=test", "issuer": "CN=CA", "partition": "Common"}]
        }
        result = self.ssl.list_certificates()
        assert result[0]["days_until_expiry"] >= 29

    def test_days_until_expiry_expired(self):
        past_ts = int((datetime.now(timezone.utc) - timedelta(days=10)).timestamp())
        self.mock_client.get.return_value = {
            "items": [{"name": "old.crt", "expirationDate": past_ts,
                        "subject": "CN=old", "issuer": "CN=CA", "partition": "Common"}]
        }
        result = self.ssl.list_certificates()
        assert result[0]["days_until_expiry"] < 0
        assert result[0]["is_expired"] is True

    def test_get_expiring_certificates(self):
        soon_ts = int((datetime.now(timezone.utc) + timedelta(days=15)).timestamp())
        far_ts = int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())
        self.mock_client.get.return_value = {
            "items": [
                {"name": "soon.crt", "expirationDate": soon_ts,
                 "subject": "CN=soon", "issuer": "CN=CA", "partition": "Common"},
                {"name": "far.crt", "expirationDate": far_ts,
                 "subject": "CN=far", "issuer": "CN=CA", "partition": "Common"}
            ]
        }
        result = self.ssl.get_expiring_certificates(days_threshold=30)
        assert len(result) == 1
        assert result[0]["name"] == "soon.crt"

    def test_get_expiring_includes_already_expired(self):
        past_ts = int((datetime.now(timezone.utc) - timedelta(days=5)).timestamp())
        self.mock_client.get.return_value = {
            "items": [
                {"name": "expired.crt", "expirationDate": past_ts,
                 "subject": "CN=expired", "issuer": "CN=CA", "partition": "Common"}
            ]
        }
        result = self.ssl.get_expiring_certificates(days_threshold=30)
        assert len(result) == 1
        assert result[0]["is_expired"] is True

    def test_get_certificate_detail(self):
        self.mock_client.get.return_value = {
            "name": "example.com.crt",
            "partition": "Common",
            "expirationDate": 1893456000,
            "subject": "CN=example.com,O=Example Corp",
            "issuer": "CN=CA",
            "keyType": "rsa-2048"
        }
        result = self.ssl.get_certificate_detail("example.com.crt")
        assert result["name"] == "example.com.crt"
        assert "key_type" in result

    def test_get_vs_ssl_cert_report_expired(self):
        """VS 绑定已过期证书 → expired 非空，status=CRITICAL"""
        past_ts = int((datetime.now(timezone.utc) - timedelta(days=10)).timestamp())

        mock_config = MagicMock()
        # VS 列表：https_vs 绑了 my-ssl-profile
        mock_config.list_virtual_servers.return_value = [
            {
                "name": "https_vs",
                "destination": "/Common/10.0.0.1:443",
                "profilesReference": {
                    "items": [
                        {"name": "my-ssl-profile", "fullPath": "/Common/my-ssl-profile"},
                    ]
                },
            }
        ]
        # client-ssl profile → cert 路径
        mock_config.list_profiles.return_value = [
            {"name": "my-ssl-profile", "cert": "/Common/expired.crt", "key": "/Common/expired.key"}
        ]
        # 证书列表：expired.crt 已过期
        self.mock_client.get.return_value = {
            "items": [
                {
                    "name": "expired.crt",
                    "partition": "Common",
                    "expirationDate": past_ts,
                    "subject": "CN=expired",
                    "issuer": "CN=CA",
                }
            ]
        }

        report = self.ssl.get_vs_ssl_cert_report(mock_config)

        assert report["status"] == "CRITICAL"
        assert len(report["expired"]) == 1
        assert report["expired"][0]["vs_name"] == "https_vs"
        assert report["expired"][0]["cert_name"] == "expired.crt"
        assert report["expired"][0]["alert_level"] == "EXPIRED"
        assert len(report["critical"]) == 0
        assert len(report["warning"]) == 0
        assert len(report["ok"]) == 0

    def test_get_vs_ssl_cert_report_ok(self):
        """VS 绑定有效证书 → ok 非空，status=OK"""
        future_ts = int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())

        mock_config = MagicMock()
        mock_config.list_virtual_servers.return_value = [
            {
                "name": "web_vs",
                "destination": "/Common/10.0.0.2:443",
                "profilesReference": {
                    "items": [
                        {"name": "clientssl", "fullPath": "/Common/clientssl"},
                    ]
                },
            }
        ]
        mock_config.list_profiles.return_value = [
            {"name": "clientssl", "cert": "/Common/valid.crt", "key": "/Common/valid.key"}
        ]
        self.mock_client.get.return_value = {
            "items": [
                {
                    "name": "valid.crt",
                    "partition": "Common",
                    "expirationDate": future_ts,
                    "subject": "CN=valid",
                    "issuer": "CN=CA",
                }
            ]
        }

        report = self.ssl.get_vs_ssl_cert_report(mock_config)

        assert report["status"] == "OK"
        assert len(report["ok"]) == 1
        assert report["ok"][0]["vs_name"] == "web_vs"
        assert report["ok"][0]["alert_level"] == "OK"
        assert len(report["expired"]) == 0
        assert len(report["critical"]) == 0
        assert len(report["warning"]) == 0
