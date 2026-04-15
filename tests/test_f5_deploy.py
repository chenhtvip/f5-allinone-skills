import pytest
from unittest.mock import MagicMock, call, patch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'f5-allinone'))

from f5_deploy import F5Deploy


class TestF5Deploy:
    def setup_method(self):
        self.mock_client = MagicMock()
        self.deploy = F5Deploy(self.mock_client)

    def test_create_virtual_server(self):
        self.mock_client.post.return_value = {
            "name": "vs_new",
            "destination": "/Common/10.0.0.2:443",
            "pool": "/Common/pool_new"
        }
        result = self.deploy.create_virtual_server(
            name="vs_new",
            destination="10.0.0.2:443",
            pool="pool_new",
            ip_protocol="tcp",
            partition="Common"
        )
        assert result["name"] == "vs_new"
        self.mock_client.post.assert_called_once()
        call_args = self.mock_client.post.call_args
        assert call_args[0][0] == "/ltm/virtual"
        payload = call_args[0][1]
        assert payload["name"] == "vs_new"
        assert payload["destination"] == "/Common/10.0.0.2:443"

    def test_create_pool(self):
        self.mock_client.post.return_value = {"name": "pool_new"}
        members = [
            {"address": "192.168.1.10", "port": 8080},
            {"address": "192.168.1.11", "port": 8080}
        ]
        result = self.deploy.create_pool(
            name="pool_new",
            members=members,
            lb_mode="round-robin",
            partition="Common"
        )
        assert result["name"] == "pool_new"
        payload = self.mock_client.post.call_args[0][1]
        assert payload["loadBalancingMode"] == "round-robin"
        assert len(payload["members"]) == 2

    def test_update_pool_member_state(self):
        self.mock_client.patch.return_value = {"session": "user-disabled"}
        result = self.deploy.update_pool_member_state(
            pool_name="pool_web",
            member_name="192.168.1.10:80",
            enabled=False,
            partition="Common"
        )
        call_args = self.mock_client.patch.call_args
        assert "~Common~pool_web/members/~Common~192.168.1.10:80" in call_args[0][0]
        payload = call_args[0][1]
        assert payload["session"] == "user-disabled"

    def test_deploy_with_transaction(self):
        self.mock_client.post.side_effect = [
            {"transId": "1234567890"},
            {"name": "pool_tx"},
        ]
        self.mock_client.patch.return_value = {"state": "COMPLETED"}

        changes = [
            {"method": "POST", "path": "/ltm/pool", "body": {"name": "pool_tx", "loadBalancingMode": "round-robin"}}
        ]
        result = self.deploy.deploy_with_transaction(changes)
        assert result["status"] == "success"
        assert self.mock_client.post.call_count == 2
        assert self.mock_client.patch.call_count == 1

    def test_save_config(self):
        self.mock_client.post.return_value = {"command": "save"}
        result = self.deploy.save_config()
        assert result is True
        self.mock_client.post.assert_called_once_with(
            "/sys/config", {"command": "save"}
        )

    def test_create_snat_pool(self):
        self.mock_client.post.return_value = {"name": "snat_new"}
        result = self.deploy.create_snat_pool(
            name="snat_new",
            members=["172.16.0.1", "172.16.0.2"],
            partition="Common"
        )
        assert result["name"] == "snat_new"
        payload = self.mock_client.post.call_args[0][1]
        assert "/Common/172.16.0.1" in payload["members"]
