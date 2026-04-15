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
        assert client.base_url == "https://192.168.1.1/mgmt/tm"

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
        assert call_url == "https://192.168.1.1/mgmt/tm/ltm/virtual"

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
