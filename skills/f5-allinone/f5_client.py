"""F5 iControl REST API 基础客户端"""
import time
import requests
import urllib3
from typing import Any, Dict, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN_TTL = 1200


class F5Client:
    """封装 F5 iControl REST API 认证与请求"""

    def __init__(self, host: str, username: str, password: str, port: int = 443):
        self.host = host
        self.username = username
        self.password = password
        self.base_url = f"https://{host}:{port}/mgmt/tm"
        self._auth_url = f"https://{host}:{port}/mgmt/shared/authn/login"
        self._token: Optional[str] = None
        self._token_acquired: Optional[float] = None
        self._session = requests.Session()
        self._session.verify = False

    def get_token(self) -> str:
        """获取 F5 认证 Token（有效期1200秒）"""
        payload = {
            "username": self.username,
            "password": self.password,
            "loginProviderName": "tmos"
        }
        try:
            resp = self._session.post(self._auth_url, json=payload, timeout=10)
            resp.raise_for_status()
            try:
                self._token = resp.json()["token"]["token"]
            except (KeyError, ValueError) as e:
                raise RuntimeError(f"F5认证响应格式异常 ({self.host}): {e}")
            self._token_acquired = time.time()
            self._session.headers.update({"X-F5-Auth-Token": self._token})
            return self._token
        except requests.ConnectionError as e:
            raise ConnectionError(f"无法连接到F5设备 {self.host}: {e}")

    def _ensure_auth(self):
        if not self._token or (
            self._token_acquired is not None
            and time.time() - self._token_acquired > TOKEN_TTL - 60
        ):
            self.get_token()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = getattr(self._session, method)(url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.ConnectionError as e:
            raise ConnectionError(f"无法连接到F5设备 {self.host}: {e}")

    def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET 请求，path 以 /ltm/... 形式传入"""
        self._ensure_auth()
        return self._request("get", path, params=params, timeout=30).json()

    def post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST 请求"""
        self._ensure_auth()
        return self._request("post", path, json=data, timeout=30).json()

    def put(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """PUT 请求（全量更新）"""
        self._ensure_auth()
        return self._request("put", path, json=data, timeout=30).json()

    def patch(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH 请求（部分更新）"""
        self._ensure_auth()
        return self._request("patch", path, json=data, timeout=30).json()

    def delete(self, path: str) -> bool:
        """DELETE 请求"""
        self._ensure_auth()
        self._request("delete", path, timeout=30)
        return True
