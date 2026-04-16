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

    def get_vs_ssl_cert_report(
        self,
        config: "F5Config",
        days_warning: int = 30,
        days_critical: int = 7,
    ) -> Dict[str, Any]:
        """查询所有关联 SSL Profile 的 VS，检查其证书到期状态。

        返回结构：
        {
          "status": "CRITICAL" | "WARNING" | "OK",
          "expired":  [...],   # is_expired=True
          "critical": [...],   # days_until_expiry <= days_critical
          "warning":  [...],   # days_until_expiry <= days_warning
          "ok":       [...],   # days_until_expiry > days_warning
          "unknown":  [...],   # cert 未配置或找不到对应证书信息
        }
        每条记录包含：vs_name, destination, ssl_profile, cert_name,
                      expiration_date, days_until_expiry, alert_level
        """
        # 1. VS 列表（含 profilesReference）
        vs_list = config.list_virtual_servers()

        # 2. client-ssl profile → cert 名列表映射（支持 certKeyChain 和平铺 cert 两种方式）
        profile_certs: Dict[str, List[str]] = {}
        client_ssl_names: set = set()
        for p in config.list_profiles("client-ssl"):
            pname = p["name"]
            client_ssl_names.add(pname)
            certs_for_profile: List[str] = []

            # 优先读取 certKeyChain（SM2 双证书、SNI 多证书场景）
            for ckc in p.get("certKeyChain", []):
                ckc_cert = ckc.get("cert", "none")
                if ckc_cert and ckc_cert != "none":
                    certs_for_profile.append(ckc_cert.split("/")[-1])

            # 回退到平铺 cert 字段
            if not certs_for_profile:
                cert_path = p.get("cert", "none")
                if cert_path and cert_path != "none":
                    certs_for_profile.append(cert_path.split("/")[-1])

            if certs_for_profile:
                profile_certs[pname] = certs_for_profile

        # 3. 证书名 → 到期信息映射
        cert_info: Dict[str, Dict[str, Any]] = {
            c["name"]: c for c in self.list_certificates()
        }

        # 4. 三表 join，打告警级别（每个 profile 下的每张证书产生一条记录）
        records: List[Dict[str, Any]] = []
        for vs in vs_list:
            profiles_raw = vs.get("profilesReference", {}).get("items", [])
            ssl_profiles = [
                p for p in profiles_raw
                if p.get("name", "") in client_ssl_names
            ]
            for profile in ssl_profiles:
                pname = profile.get("name", "")
                cert_names = profile_certs.get(pname, [])

                if not cert_names:
                    # profile 未配置任何证书
                    records.append({
                        "vs_name": vs.get("name", ""),
                        "destination": vs.get("destination", ""),
                        "ssl_profile": pname,
                        "cert_name": None,
                        "expiration_date": "",
                        "days_until_expiry": None,
                        "alert_level": "UNKNOWN",
                    })
                    continue

                for cert_name in cert_names:
                    info = cert_info.get(cert_name)

                    if info is None:
                        alert = "UNKNOWN"
                        expiry_date = ""
                        days = None
                    elif info["is_expired"]:
                        alert = "EXPIRED"
                        expiry_date = info["expiration_date"]
                        days = info["days_until_expiry"]
                    elif info["days_until_expiry"] <= days_critical:
                        alert = "CRITICAL"
                        expiry_date = info["expiration_date"]
                        days = info["days_until_expiry"]
                    elif info["days_until_expiry"] <= days_warning:
                        alert = "WARNING"
                        expiry_date = info["expiration_date"]
                        days = info["days_until_expiry"]
                    else:
                        alert = "OK"
                        expiry_date = info["expiration_date"]
                        days = info["days_until_expiry"]

                    records.append({
                        "vs_name": vs.get("name", ""),
                        "destination": vs.get("destination", ""),
                        "ssl_profile": pname,
                        "cert_name": cert_name,
                        "expiration_date": expiry_date,
                        "days_until_expiry": days,
                        "alert_level": alert,
                    })

        expired  = [r for r in records if r["alert_level"] == "EXPIRED"]
        critical = [r for r in records if r["alert_level"] == "CRITICAL"]
        warning  = [r for r in records if r["alert_level"] == "WARNING"]
        ok       = [r for r in records if r["alert_level"] == "OK"]
        unknown  = [r for r in records if r["alert_level"] == "UNKNOWN"]

        if expired or critical:
            status = "CRITICAL"
        elif warning or unknown:
            status = "WARNING"
        else:
            status = "OK"

        return {
            "status": status,
            "expired": expired,
            "critical": critical,
            "warning": warning,
            "ok": ok,
            "unknown": unknown,
        }
