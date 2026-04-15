"""F5 配置下发：事务式配置变更、VS/Pool/SNAT 创建更新"""
from typing import Any, Dict, List
from f5_client import F5Client


class F5Deploy:
    def __init__(self, client: F5Client):
        self.client = client

    def create_virtual_server(self, name: str, destination: str, pool: str = None,
                               ip_protocol: str = "tcp", partition: str = "Common",
                               profiles: List[str] = None) -> Dict[str, Any]:
        """创建 Virtual Server"""
        payload = {
            "name": name,
            "partition": partition,
            "destination": f"/{partition}/{destination}",
            "ipProtocol": ip_protocol,
            "sourceAddressTranslation": {"type": "automap"}
        }
        if pool:
            payload["pool"] = f"/{partition}/{pool}"
        if profiles:
            payload["profiles"] = [{"name": p} for p in profiles]
        return self.client.post("/ltm/virtual", payload)

    def update_virtual_server(self, name: str, updates: Dict[str, Any],
                               partition: str = "Common") -> Dict[str, Any]:
        """更新 Virtual Server 属性"""
        return self.client.patch(f"/ltm/virtual/~{partition}~{name}", updates)

    def create_pool(self, name: str, members: List[Dict[str, Any]],
                    lb_mode: str = "round-robin", partition: str = "Common",
                    monitor: str = "http") -> Dict[str, Any]:
        """创建 Pool（含成员）"""
        formatted_members = [
            {
                "name": f"{m['address']}:{m['port']}",
                "address": m["address"]
            }
            for m in members
        ]
        payload = {
            "name": name,
            "partition": partition,
            "loadBalancingMode": lb_mode,
            "monitor": f"/Common/{monitor}",
            "members": formatted_members
        }
        return self.client.post("/ltm/pool", payload)

    def update_pool_member_state(self, pool_name: str, member_name: str,
                                  enabled: bool, partition: str = "Common") -> Dict[str, Any]:
        """启用或禁用 Pool 成员"""
        session = "user-enabled" if enabled else "user-disabled"
        path = f"/ltm/pool/~{partition}~{pool_name}/members/~{partition}~{member_name}"
        return self.client.patch(path, {"session": session})

    def create_snat_pool(self, name: str, members: List[str],
                          partition: str = "Common") -> Dict[str, Any]:
        """创建 SNAT Pool"""
        payload = {
            "name": name,
            "partition": partition,
            "members": [f"/{partition}/{m}" for m in members]
        }
        return self.client.post("/ltm/snatpool", payload)

    def deploy_with_transaction(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """事务式批量配置下发（原子提交）

        changes 格式:
        [
            {"method": "POST", "path": "/ltm/pool", "body": {...}},
            {"method": "PATCH", "path": "/ltm/virtual/~Common~vs_web", "body": {...}}
        ]
        """
        # 1. 创建事务（使用 /transaction 路径，base_url 已包含 /mgmt/tm）
        tx = self.client.post("/transaction", {})
        tx_id = tx["transId"]

        # 2. 在事务中执行每条变更
        self.client._session.headers.update({"X-F5-REST-Coordination-Id": str(tx_id)})
        try:
            for change in changes:
                method = change["method"].upper()
                path = change["path"]
                body = change.get("body", {})
                if method == "POST":
                    self.client.post(path, body)
                elif method == "PATCH":
                    self.client.patch(path, body)
                elif method == "PUT":
                    self.client.put(path, body)
                elif method == "DELETE":
                    self.client.delete(path)
        finally:
            self.client._session.headers.pop("X-F5-REST-Coordination-Id", None)

        # 3. 提交事务
        result = self.client.patch(f"/transaction/{tx_id}", {"state": "VALIDATING"})
        return {
            "status": "success",
            "transaction_id": tx_id,
            "result": result
        }

    def save_config(self) -> bool:
        """将运行配置保存到磁盘"""
        self.client.post("/sys/config", {"command": "save"})
        return True
