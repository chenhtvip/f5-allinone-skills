import pytest
from unittest.mock import MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'f5-allinone'))

from f5_config import F5Config


class TestF5Config:
    def setup_method(self):
        self.mock_client = MagicMock()
        self.config = F5Config(self.mock_client)

    def test_list_virtual_servers(self):
        self.mock_client.get.return_value = {
            "items": [
                {
                    "name": "vs_web_80",
                    "destination": "/Common/10.0.0.1:80",
                    "pool": "/Common/pool_web",
                    "enabled": True,
                    "ipProtocol": "tcp"
                }
            ]
        }
        result = self.config.list_virtual_servers()
        assert len(result) == 1
        assert result[0]["name"] == "vs_web_80"
        assert result[0]["destination"] == "/Common/10.0.0.1:80"
        self.mock_client.get.assert_called_once_with("/ltm/virtual", params={"expandSubcollections": "true"})

    def test_get_virtual_server(self):
        self.mock_client.get.return_value = {
            "name": "vs_web_80",
            "destination": "/Common/10.0.0.1:80",
            "pool": "/Common/pool_web"
        }
        result = self.config.get_virtual_server("vs_web_80", partition="Common")
        assert result["name"] == "vs_web_80"
        self.mock_client.get.assert_called_once_with("/ltm/virtual/~Common~vs_web_80",
                                                      params={"expandSubcollections": "true"})

    def test_list_pools(self):
        self.mock_client.get.return_value = {
            "items": [
                {
                    "name": "pool_web",
                    "loadBalancingMode": "round-robin",
                    "members": {
                        "items": [
                            {"name": "192.168.1.10:80", "state": "up"}
                        ]
                    }
                }
            ]
        }
        result = self.config.list_pools()
        assert len(result) == 1
        assert result[0]["name"] == "pool_web"
        assert result[0]["lb_mode"] == "round-robin"

    def test_get_pool_members(self):
        self.mock_client.get.return_value = {
            "items": [
                {"name": "192.168.1.10:80", "state": "up", "session": "user-enabled"},
                {"name": "192.168.1.11:80", "state": "down", "session": "user-disabled"}
            ]
        }
        result = self.config.get_pool_members("pool_web", partition="Common")
        assert len(result) == 2
        assert result[0]["state"] == "up"

    def test_list_profiles(self):
        self.mock_client.get.return_value = {
            "items": [
                {"name": "http_default", "kind": "tm:ltm:profile:http:httpstate"},
                {"name": "tcp_default", "kind": "tm:ltm:profile:tcp:tcpstate"}
            ]
        }
        result = self.config.list_profiles(profile_type="http")
        assert len(result) == 2
        self.mock_client.get.assert_called_once_with("/ltm/profile/http")

    def test_list_snat_pools(self):
        self.mock_client.get.return_value = {
            "items": [
                {
                    "name": "snat_pool_01",
                    "members": [
                        "/Common/172.16.0.1",
                        "/Common/172.16.0.2"
                    ]
                }
            ]
        }
        result = self.config.list_snat_pools()
        assert len(result) == 1
        assert result[0]["name"] == "snat_pool_01"
        assert len(result[0]["members"]) == 2
