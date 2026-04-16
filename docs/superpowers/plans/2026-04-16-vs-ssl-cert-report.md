# VS SSL 证书到期巡检 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `F5SSL` 类中新增 `get_vs_ssl_cert_report()` 方法，关联 VS → SSL Profile → 证书链路，输出两级告警报告；并更新 SKILL.md 使 Claude 自动识别相关查询意图。

**Architecture:** 在现有 `f5_ssl.py` 的 `F5SSL` 类中添加新方法，接受 `F5Config` 实例作为参数，通过三步查询（VS列表、client-ssl profiles、证书列表）join 出完整链路，按 EXPIRED/CRITICAL/WARNING/OK 四级分组返回。

**Tech Stack:** Python 3.8+, unittest.mock（已有依赖，无新增）

---

### Task 1: 为 `get_vs_ssl_cert_report` 编写失败测试

**Files:**
- Modify: `tests/test_f5_ssl.py`

- [ ] **Step 1: 在 `tests/test_f5_ssl.py` 末尾追加两个测试方法**

在 `class TestF5SSL:` 的最后追加：

```python
    def test_get_vs_ssl_cert_report_expired(self):
        """VS 绑定已过期证书 → expired 非空，status=CRITICAL"""
        from unittest.mock import patch
        from datetime import datetime, timedelta, timezone
        import time

        past_ts = int((datetime.now(timezone.utc) - timedelta(days=10)).timestamp())

        mock_config = MagicMock()
        # VS 列表：https_vs 绑了 my-ssl-profile
        mock_config.list_virtual_servers.return_value = [
            {
                "name": "https_vs",
                "destination": "/Common/10.0.0.1:443",
                "profilesReference": {
                    "items": [
                        {"name": "my-ssl-profile", "fullPath": "/Common/my-ssl-profile"},
                        {"name": "http", "fullPath": "/Common/http"},
                    ]
                },
            }
        ]
        # client-ssl profile → cert 路径
        mock_config.list_profiles.return_value = [
            {"name": "my-ssl-profile", "cert": "/Common/expired.crt", "key": "/Common/expired.key"}
        ]
        # 证书列表：expired.crt 已过期
        self.mock_client.get.return_value = {
            "items": [
                {
                    "name": "expired.crt",
                    "partition": "Common",
                    "expirationDate": past_ts,
                    "subject": "CN=expired",
                    "issuer": "CN=CA",
                }
            ]
        }

        report = self.ssl.get_vs_ssl_cert_report(mock_config)

        assert report["status"] == "CRITICAL"
        assert len(report["expired"]) == 1
        assert report["expired"][0]["vs_name"] == "https_vs"
        assert report["expired"][0]["cert_name"] == "expired.crt"
        assert report["expired"][0]["alert_level"] == "EXPIRED"
        assert len(report["critical"]) == 0
        assert len(report["warning"]) == 0
        assert len(report["ok"]) == 0

    def test_get_vs_ssl_cert_report_ok(self):
        """VS 绑定有效证书 → ok 非空，status=OK"""
        from datetime import datetime, timedelta, timezone

        future_ts = int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())

        mock_config = MagicMock()
        mock_config.list_virtual_servers.return_value = [
            {
                "name": "web_vs",
                "destination": "/Common/10.0.0.2:443",
                "profilesReference": {
                    "items": [
                        {"name": "clientssl", "fullPath": "/Common/clientssl"},
                    ]
                },
            }
        ]
        mock_config.list_profiles.return_value = [
            {"name": "clientssl", "cert": "/Common/valid.crt", "key": "/Common/valid.key"}
        ]
        self.mock_client.get.return_value = {
            "items": [
                {
                    "name": "valid.crt",
                    "partition": "Common",
                    "expirationDate": future_ts,
                    "subject": "CN=valid",
                    "issuer": "CN=CA",
                }
            ]
        }

        report = self.ssl.get_vs_ssl_cert_report(mock_config)

        assert report["status"] == "OK"
        assert len(report["ok"]) == 1
        assert report["ok"][0]["vs_name"] == "web_vs"
        assert report["ok"][0]["alert_level"] == "OK"
        assert len(report["expired"]) == 0
        assert len(report["critical"]) == 0
        assert len(report["warning"]) == 0
```

- [ ] **Step 2: 运行测试，确认失败（方法未实现）**

```bash
python3 -m pytest tests/test_f5_ssl.py::TestF5SSL::test_get_vs_ssl_cert_report_expired tests/test_f5_ssl.py::TestF5SSL::test_get_vs_ssl_cert_report_ok -v
```

预期输出：
```
FAILED tests/test_f5_ssl.py::TestF5SSL::test_get_vs_ssl_cert_report_expired - AttributeError: 'F5SSL' object has no attribute 'get_vs_ssl_cert_report'
FAILED tests/test_f5_ssl.py::TestF5SSL::test_get_vs_ssl_cert_report_ok - AttributeError: 'F5SSL' object has no attribute 'get_vs_ssl_cert_report'
```

---

### Task 2: 实现 `get_vs_ssl_cert_report()`

**Files:**
- Modify: `skills/f5-allinone/f5_ssl.py`

- [ ] **Step 1: 在 `f5_ssl.py` 的 `F5SSL` 类末尾添加新方法**

在 `get_summary_report()` 方法之后追加：

```python
    def get_vs_ssl_cert_report(
        self,
        config: Any,
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
        }
        每条记录包含：vs_name, destination, ssl_profile, cert_name,
                      expiration_date, days_until_expiry, alert_level
        """
        # 1. VS 列表（含 profilesReference）
        vs_list = config.list_virtual_servers()

        # 2. client-ssl profile → cert 路径映射
        profile_cert: Dict[str, str] = {}
        for p in config.list_profiles("client-ssl"):
            cert_path = p.get("cert", "none")
            if cert_path and cert_path != "none":
                profile_cert[p["name"]] = cert_path.split("/")[-1]

        # 3. 证书名 → 到期信息映射
        cert_info: Dict[str, Dict[str, Any]] = {
            c["name"]: c for c in self.list_certificates()
        }

        # 4. 三表 join，打告警级别
        records: List[Dict[str, Any]] = []
        for vs in vs_list:
            profiles_raw = vs.get("profilesReference", {}).get("items", [])
            ssl_profiles = [
                p for p in profiles_raw
                if "ssl" in p.get("fullPath", "").lower()
                or "ssl" in p.get("name", "").lower()
            ]
            for profile in ssl_profiles:
                pname = profile.get("name", "")
                cert_name = profile_cert.get(pname, "none")
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

        if expired or critical:
            status = "CRITICAL"
        elif warning:
            status = "WARNING"
        else:
            status = "OK"

        return {
            "status": status,
            "expired": expired,
            "critical": critical,
            "warning": warning,
            "ok": ok,
        }
```

- [ ] **Step 2: 运行测试，确认通过**

```bash
python3 -m pytest tests/test_f5_ssl.py -v
```

预期输出：全部 PASSED（共 8 个原有 + 2 个新增 = 10 个）。

- [ ] **Step 3: 提交**

```bash
git add skills/f5-allinone/f5_ssl.py tests/test_f5_ssl.py
git commit -m "feat: add get_vs_ssl_cert_report to F5SSL"
```

---

### Task 3: 更新 SKILL.md 触发词与文档

**Files:**
- Modify: `skills/f5-allinone/SKILL.md`

- [ ] **Step 1: 更新 frontmatter description（第3行）**

将：
```
description: Use when working with F5 BIG-IP load balancers via API - monitoring device status (CPU/memory/HA/connections), querying configuration (virtual servers/pools/profiles/SNAT), managing SSL certificates with expiry alerts, or deploying configuration changes programmatically via iControl REST API
```

替换为：
```
description: Use when working with F5 BIG-IP load balancers via API - monitoring device status (CPU/memory/HA/connections), querying configuration (virtual servers/pools/profiles/SNAT), managing SSL certificates with expiry alerts, checking which virtual servers have expiring or expired SSL certificates linked via SSL profiles, or deploying configuration changes programmatically via iControl REST API
```

- [ ] **Step 2: 在 "SSL 证书管理" 节的现有示例后追加新方法说明**

在以下内容之后：
```python
print(f"即将过期(7天内): {len(report['critical'])} 个")
```

追加：
```markdown

```python
# VS 关联证书到期巡检（两级告警：CRITICAL=7天，WARNING=30天）
config = F5Config(client)
report = ssl.get_vs_ssl_cert_report(config, days_warning=30, days_critical=7)
print(f"整体状态: {report['status']}")
for r in report['expired']:
    print(f"[EXPIRED]  VS={r['vs_name']}  证书={r['cert_name']}")
for r in report['critical']:
    print(f"[CRITICAL] VS={r['vs_name']}  证书={r['cert_name']}  剩余={r['days_until_expiry']}天")
for r in report['warning']:
    print(f"[WARNING]  VS={r['vs_name']}  证书={r['cert_name']}  剩余={r['days_until_expiry']}天")
```
```

- [ ] **Step 3: 运行全部测试，确认无回归**

```bash
python3 -m pytest tests/ -v
```

预期：全部 PASSED。

- [ ] **Step 4: 提交**

```bash
git add skills/f5-allinone/SKILL.md
git commit -m "docs: update SKILL.md trigger phrase and add get_vs_ssl_cert_report example"
```
