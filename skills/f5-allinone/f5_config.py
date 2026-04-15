"""F5 配置查询：Virtual Server / Pool / Profile / SNAT"""
from typing import Any, Dict, List, Optional
from f5_client import F5Client


class F5Config:
    def __init__(self, client: F5Client):
        self.client = client

    def list_virtual_servers(self, partition: str = "Common") -> List[Dict[str, Any]]:
        """列出所有 Virtual Server"""
        data = self.client.get("/ltm/virtual", params={"expandSubcollections": "true"})
        return data.get("items", [])

    def get_virtual_server(self, name: str, partition: str = "Common") -> Dict[str, Any]:
        """获取指定 Virtual Server 详情"""
        path = f"/ltm/virtual/~{partition}~{name}"
        return self.client.get(path, params={"expandSubcollections": "true"})

    def list_pools(self, partition: str = "Common") -> List[Dict[str, Any]]:
        """列出所有 Pool 及成员状态"""
        data = self.client.get("/ltm/pool", params={"expandSubcollections": "true"})
        pools = []
        for item in data.get("items", []):
            members = item.get("members", {}).get("items", [])
            up_count = sum(1 for m in members if m.get("state") == "up")
            pools.append({
                "name": item.get("name"),
                "partition": item.get("partition", partition),
                "lb_mode": item.get("loadBalancingMode", "round-robin"),
                "member_count": len(members),
                "members_up": up_count,
                "members": members
            })
        return pools

    def get_pool_members(self, pool_name: str, partition: str = "Common") -> List[Dict[str, Any]]:
        """获取指定 Pool 的成员列表"""
        path = f"/ltm/pool/~{partition}~{pool_name}/members"
        data = self.client.get(path)
        return data.get("items", [])

    def list_profiles(self, profile_type: str = "http") -> List[Dict[str, Any]]:
        """查询指定类型的 Profile（http/tcp/ssl-client/ssl-server/fastl4等）"""
        data = self.client.get(f"/ltm/profile/{profile_type}")
        return data.get("items", [])

    def list_snat_pools(self, partition: str = "Common") -> List[Dict[str, Any]]:
        """列出所有 SNAT Pool"""
        data = self.client.get("/ltm/snatpool")
        snat_pools = []
        for item in data.get("items", []):
            snat_pools.append({
                "name": item.get("name"),
                "partition": item.get("partition", partition),
                "members": item.get("members", [])
            })
        return snat_pools

    def list_snat_translations(self) -> List[Dict[str, Any]]:
        """列出 SNAT Translation 地址"""
        data = self.client.get("/ltm/snat-translation")
        return data.get("items", [])
