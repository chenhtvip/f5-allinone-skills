"""F5 状态监控：CPU/内存/连接/吞吐/HA/接口流量"""
from typing import Any, Dict, List
from f5_client import F5Client


class F5Monitor:
    def __init__(self, client: F5Client):
        self.client = client

    def get_cpu_usage(self) -> Dict[str, Any]:
        """获取CPU使用率（5秒平均值）"""
        data = self.client.get("/sys/cpu/stats")
        entries = data.get("entries", {})
        for key, val in entries.items():
            nested = val.get("nestedStats", {}).get("entries", {})
            idle = nested.get("fiveSecAvgIdle", {}).get("value", 100)
            system = nested.get("fiveSecAvgSystem", {}).get("value", 0)
            user = nested.get("fiveSecAvgUser", {}).get("value", 0)
            return {
                "cpu_idle_pct": idle,
                "cpu_system_pct": system,
                "cpu_user_pct": user,
                "cpu_usage_pct": 100 - idle
            }
        return {"cpu_usage_pct": 0, "cpu_idle_pct": 100, "cpu_system_pct": 0, "cpu_user_pct": 0}

    def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        data = self.client.get("/sys/memory/stats")
        entries = data.get("entries", {})
        for key, val in entries.items():
            nested = val.get("nestedStats", {}).get("entries", {})
            total = nested.get("memoryTotal", {}).get("value", 0)
            used = nested.get("memoryUsed", {}).get("value", 0)
            total_mb = total // (1024 * 1024)
            used_mb = used // (1024 * 1024)
            usage_pct = round(used / total * 100, 2) if total > 0 else 0
            return {
                "memory_total_mb": total_mb,
                "memory_used_mb": used_mb,
                "memory_free_mb": total_mb - used_mb,
                "memory_usage_pct": usage_pct
            }
        return {"memory_total_mb": 0, "memory_used_mb": 0, "memory_free_mb": 0, "memory_usage_pct": 0}

    def get_connections(self) -> Dict[str, Any]:
        """获取并发连接数和新建连接数"""
        data = self.client.get("/sys/performance/connections/stats")
        entries = data.get("entries", {})
        for key, val in entries.items():
            nested = val.get("nestedStats", {}).get("entries", {})
            active = nested.get("Current Active Connections", {}).get("value", 0)
            new_conn = nested.get("New Connections", {}).get("value", 0)
            return {
                "active_connections": active,
                "new_connections_per_sec": new_conn
            }
        return {"active_connections": 0, "new_connections_per_sec": 0}

    def get_throughput(self) -> Dict[str, Any]:
        """获取吞吐量（bits/sec）"""
        data = self.client.get("/sys/performance/throughput/stats")
        entries = data.get("entries", {})
        for key, val in entries.items():
            nested = val.get("nestedStats", {}).get("entries", {})
            total_bps = nested.get("Throughput(bits/sec)", {}).get("value", 0)
            in_bps = nested.get("In", {}).get("value", 0)
            out_bps = nested.get("Out", {}).get("value", 0)
            return {
                "throughput_bps": total_bps,
                "throughput_mbps": round(total_bps / 1_000_000, 2),
                "in_bps": in_bps,
                "out_bps": out_bps
            }
        return {"throughput_bps": 0, "throughput_mbps": 0, "in_bps": 0, "out_bps": 0}

    def get_ha_status(self) -> Dict[str, Any]:
        """获取HA故障切换状态"""
        data = self.client.get("/cm/failover-status/stats")
        entries = data.get("entries", {})
        for key, val in entries.items():
            nested = val.get("nestedStats", {}).get("entries", {})
            status = nested.get("status", {}).get("description", "UNKNOWN")
            color = nested.get("color", {}).get("description", "unknown")
            return {
                "ha_status": status,
                "ha_color": color,
                "is_active": status == "ACTIVE"
            }
        return {"ha_status": "UNKNOWN", "ha_color": "unknown", "is_active": False}

    def get_sync_status(self) -> Dict[str, Any]:
        """获取配置同步状态"""
        data = self.client.get("/cm/sync-status/stats")
        entries = data.get("entries", {})
        for key, val in entries.items():
            nested = val.get("nestedStats", {}).get("entries", {})
            status = nested.get("status", {}).get("description", "UNKNOWN")
            color = nested.get("color", {}).get("description", "unknown")
            summary = nested.get("summary", {}).get("description", "")
            return {
                "sync_status": status,
                "sync_color": color,
                "sync_summary": summary,
                "is_synced": status == "In Sync"
            }
        return {"sync_status": "UNKNOWN", "sync_color": "unknown", "sync_summary": "", "is_synced": False}

    def get_interface_stats(self) -> List[Dict[str, Any]]:
        """获取所有接口流量统计"""
        data = self.client.get("/net/interface/stats")
        entries = data.get("entries", {})
        interfaces = []
        for url_key, val in entries.items():
            nested = val.get("nestedStats", {}).get("entries", {})
            interfaces.append({
                "name": nested.get("tmName", {}).get("description", ""),
                "status": nested.get("status", {}).get("description", "unknown"),
                "bits_in": nested.get("counters.bitsIn", {}).get("value", 0),
                "bits_out": nested.get("counters.bitsOut", {}).get("value", 0),
                "pkts_in": nested.get("counters.pktsIn", {}).get("value", 0),
                "pkts_out": nested.get("counters.pktsOut", {}).get("value", 0)
            })
        return interfaces

    def get_all_status(self) -> Dict[str, Any]:
        """聚合所有监控指标"""
        return {
            "cpu": self.get_cpu_usage(),
            "memory": self.get_memory_usage(),
            "connections": self.get_connections(),
            "throughput": self.get_throughput(),
            "ha": self.get_ha_status(),
            "sync": self.get_sync_status(),
            "interfaces": self.get_interface_stats()
        }
