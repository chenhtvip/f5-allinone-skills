import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'f5-allinone'))

from f5_client import F5Client


class TestF5Client:
    def test_init_stores_connection_params(self):
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        assert client.host == "192.168.1.1"
        assert client.username == "admin"
        assert client.base_url == "https://192.168.1.1:443/mgmt/tm"

    def test_get_token_success(self):
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        mock_response = MagicMock()
        mock_response.json.return_value = {"token": {"token": "abc123"}}
        mock_response.raise_for_status.return_value = None

        with patch("requests.Session.post", return_value=mock_response):
            token = client.get_token()
        assert token == "abc123"

    def test_get_request_success(self):
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        client._token = "abc123"
        mock_response = MagicMock()
        mock_response.json.return_value = {"kind": "tm:ltm:virtual:virtualcollectionstate"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.Session.get", return_value=mock_response) as mock_get:
            result = client.get("/ltm/virtual")
        assert result == {"kind": "tm:ltm:virtual:virtualcollectionstate"}
        call_url = mock_get.call_args[0][0]
        assert call_url == "https://192.168.1.1:443/mgmt/tm/ltm/virtual"

    def test_post_request_success(self):
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        client._token = "abc123"
        payload = {"name": "test_vs", "destination": "10.0.0.1:80"}
        mock_response = MagicMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status.return_value = None

        with patch("requests.Session.post", return_value=mock_response):
            result = client.post("/ltm/virtual", payload)
        assert result["name"] == "test_vs"

    def test_connection_error_raises(self):
        import requests
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        with patch("requests.Session.post", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(ConnectionError, match="无法连接到F5设备"):
                client.get_token()

    def test_connection_error_raises_on_get(self):
        import requests
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        client._token = "abc123"
        with patch("requests.Session.get", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(ConnectionError, match="无法连接到F5设备"):
                client.get("/ltm/virtual")

    def test_connection_error_raises_on_post(self):
        import requests
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        client._token = "abc123"
        with patch("requests.Session.post", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(ConnectionError, match="无法连接到F5设备"):
                client.post("/ltm/virtual", {})

    def test_get_token_bad_response_raises_runtime_error(self):
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "format"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.Session.post", return_value=mock_response):
            with pytest.raises(RuntimeError, match="F5认证响应格式异常"):
                client.get_token()

    def test_port_used_in_urls(self):
        client = F5Client(host="192.168.1.1", username="admin", password="pass", port=8443)
        assert client.base_url == "https://192.168.1.1:8443/mgmt/tm"
        assert client._auth_url == "https://192.168.1.1:8443/mgmt/shared/authn/login"

    def test_token_ttl_triggers_refresh(self):
        import time
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        client._token = "old_token"
        # Simulate token acquired TOKEN_TTL - 30 seconds ago (past the refresh threshold)
        client._token_acquired = time.time() - 1171  # > TOKEN_TTL - 60 = 1140

        mock_response = MagicMock()
        mock_response.json.return_value = {"token": {"token": "new_token"}}
        mock_response.raise_for_status.return_value = None

        with patch("requests.Session.post", return_value=mock_response):
            with patch("requests.Session.get", return_value=mock_response) as mock_get:
                client.get("/ltm/virtual")

        assert client._token == "new_token"

    def test_token_not_refreshed_when_fresh(self):
        import time
        client = F5Client(host="192.168.1.1", username="admin", password="pass")
        client._token = "current_token"
        client._token_acquired = time.time()  # just acquired

        mock_response = MagicMock()
        mock_response.json.return_value = {"items": []}
        mock_response.raise_for_status.return_value = None

        with patch("requests.Session.get", return_value=mock_response):
            with patch.object(client, "get_token") as mock_get_token:
                client.get("/ltm/virtual")
                mock_get_token.assert_not_called()
