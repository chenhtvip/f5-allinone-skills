"""F5 SSL 证书管理：到期查询、有效期提醒"""
from datetime import datetime, timezone
from typing import Any, Dict, List
from f5_client import F5Client


class F5SSL:
    def __init__(self, client: F5Client):
        self.client = client

    def _parse_cert(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """将 F5 证书原始数据转换为友好格式"""
        expiry_ts = item.get("expirationDate", 0)
        expiry_dt = datetime.fromtimestamp(expiry_ts, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        days_until = (expiry_dt - now).days
        return {
            "name": item.get("name", ""),
            "partition": item.get("partition", "Common"),
            "subject": item.get("subject", ""),
            "issuer": item.get("issuer", ""),
            "expiration_timestamp": expiry_ts,
            "expiration_date": expiry_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "days_until_expiry": days_until,
            "is_expired": days_until < 0,
            "key_type": item.get("keyType", "unknown")
        }

    def list_certificates(self) -> List[Dict[str, Any]]:
        """列出所有 SSL 证书及到期信息"""
        data = self.client.get("/sys/file/ssl-cert")
        return [self._parse_cert(item) for item in data.get("items", [])]

    def get_certificate_detail(self, name: str, partition: str = "Common") -> Dict[str, Any]:
        """获取指定证书详情"""
        data = self.client.get(f"/sys/file/ssl-cert/~{partition}~{name}")
        return self._parse_cert(data)

    def get_expiring_certificates(self, days_threshold: int = 30) -> List[Dict[str, Any]]:
        """获取在 days_threshold 天内到期或已过期的证书"""
        certs = self.list_certificates()
        return [c for c in certs if c["days_until_expiry"] <= days_threshold]

    def get_summary_report(self, days_warning: int = 30, days_critical: int = 7) -> Dict[str, Any]:
        """生成证书到期状态摘要报告"""
        certs = self.list_certificates()
        expired = [c for c in certs if c["is_expired"]]
        critical = [c for c in certs if not c["is_expired"] and c["days_until_expiry"] <= days_critical]
        warning = [c for c in certs if not c["is_expired"] and
                   days_critical < c["days_until_expiry"] <= days_warning]
        ok = [c for c in certs if c["days_until_expiry"] > days_warning]
        return {
            "total": len(certs),
            "expired": expired,
            "critical": critical,
            "warning": warning,
            "ok": ok,
            "status": "CRITICAL" if expired or critical else "WARNING" if warning else "OK"
        }
