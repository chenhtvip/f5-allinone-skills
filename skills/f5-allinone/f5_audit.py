"""F5 批量巡检：读取设备清单，并发执行巡检，导出 CSV 报告"""
import csv
from datetime import datetime
from typing import Any, Dict, List

from f5_client import F5Client
from f5_inventory import F5Inventory
from f5_monitor import F5Monitor
from f5_ssl import F5SSL


class F5Audit:
    """对 inventory.yaml 中所有设备执行巡检，汇总结果并导出 CSV"""

    def __init__(self, inventory_path: str = "inventory.yaml"):
        self.inventory = F5Inventory(inventory_path)

    def run_device(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """对单台设备执行巡检，捕获异常保证不中断整体流程"""
        result: Dict[str, Any] = {
            "name": device["name"],
            "host": device["host"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ok",
            "error": None,
            "monitor": None,
            "ssl": None,
        }
        try:
            client = F5Client(
                host=device["host"],
                username=device["username"],
                password=device["password"],
                port=device["port"],
            )
            monitor = F5Monitor(client)
            ssl = F5SSL(client)
            result["monitor"] = monitor.get_all_status()
            result["ssl"] = ssl.get_summary_report()
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        return result

    def run_all(self) -> List[Dict[str, Any]]:
        """对清单中所有设备顺序执行巡检，返回结果列表"""
        errors = self.inventory.validate()
        if errors:
            raise ValueError("设备清单校验失败:\n" + "\n".join(errors))
        devices = self.inventory.load()
        results = []
        for device in devices:
            print(f"  巡检设备: {device['name']} ({device['host']}) ...", end=" ", flush=True)
            result = self.run_device(device)
            status_label = "OK" if result["status"] == "ok" else f"ERROR: {result['error']}"
            print(status_label)
            results.append(result)
        return results

    def export_csv(self, results: List[Dict[str, Any]], output_path: str = "audit_report.csv") -> str:
        """将巡检结果导出为 CSV 文件，返回文件路径"""
        fieldnames = [
            "巡检时间", "设备名", "主机", "状态",
            "HA状态", "CPU使用率%", "内存使用率%",
            "并发连接", "吞吐Mbps", "SSL状态",
            "SSL过期证书数", "SSL告警证书数", "错误信息",
        ]
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                monitor = r.get("monitor") or {}
                ssl = r.get("ssl") or {}
                row = {
                    "巡检时间": r["timestamp"],
                    "设备名": r["name"],
                    "主机": r["host"],
                    "状态": r["status"],
                    "HA状态": monitor.get("ha", {}).get("ha_status", ""),
                    "CPU使用率%": monitor.get("cpu", {}).get("cpu_usage_pct", ""),
                    "内存使用率%": monitor.get("memory", {}).get("memory_usage_pct", ""),
                    "并发连接": monitor.get("connections", {}).get("active_connections", ""),
                    "吞吐Mbps": monitor.get("throughput", {}).get("throughput_mbps", ""),
                    "SSL状态": ssl.get("status", ""),
                    "SSL过期证书数": len(ssl.get("expired", [])),
                    "SSL告警证书数": len(ssl.get("critical", [])) + len(ssl.get("warning", [])),
                    "错误信息": r.get("error") or "",
                }
                writer.writerow(row)
        return output_path
