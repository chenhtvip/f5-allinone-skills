# Design: VS SSL 证书到期巡检方法

**日期**: 2026-04-16
**状态**: 已批准

---

## 背景

用户在日常巡检中需要快速定位哪些 Virtual Server 关联的 SSL 证书即将到期或已过期。现有 `F5SSL.get_summary_report()` 仅列出设备上所有证书的状态，无法关联到具体 VS，需要手动交叉比对。本设计将 VS → SSL Profile → 证书 的完整链路封装为一个方法，并更新 SKILL.md 触发词，使 Claude 在用户询问相关问题时自动加载并调用。

---

## 目标

- 一次调用返回"哪些 VS 绑定了即将到期或已过期的 SSL 证书"
- 与现有 `get_summary_report()` 保持一致的两级告警（WARNING / CRITICAL）
- 更新 SKILL.md，使该功能成为自然语言触发的 skill 能力

---

## 实现方案

### 选型

在 `F5SSL` 类中添加新方法，接受 `F5Config` 实例作为参数（方案 A）。
- 不引入新模块文件
- SSL 健康判断逻辑归 `F5SSL` 统一管理
- 通过参数注入避免循环导入

---

## 接口设计

### `F5SSL.get_vs_ssl_cert_report()`

```python
def get_vs_ssl_cert_report(
    self,
    config: "F5Config",
    days_warning: int = 30,
    days_critical: int = 7
) -> Dict[str, Any]:
```

**返回结构**：

```python
{
  "status": "CRITICAL" | "WARNING" | "OK",
  "expired":  [<record>, ...],   # is_expired=True
  "critical": [<record>, ...],   # days_until_expiry <= days_critical
  "warning":  [<record>, ...],   # days_until_expiry <= days_warning
  "ok":       [<record>, ...],   # days_until_expiry > days_warning
}
```

**每条 record**：

```python
{
  "vs_name":           str,   # Virtual Server 名称
  "destination":       str,   # VS 目标地址，如 /Common/10.1.10.100:443
  "ssl_profile":       str,   # 关联的 SSL Profile 名称
  "cert_name":         str,   # 证书名（"none" 表示 profile 未配置证书）
  "expiration_date":   str,   # 如 "2022-09-25 02:52:21 UTC"
  "days_until_expiry": int | None,
  "alert_level":       "EXPIRED" | "CRITICAL" | "WARNING" | "OK" | "UNKNOWN",
}
```

**数据流**：

```
list_virtual_servers()          → VS 列表（含 profilesReference）
    ↓
list_profiles("client-ssl")     → profile名 → cert路径 映射
    ↓
list_certificates()             → cert名 → 到期信息 映射
    ↓
三表 join → 打告警级别 → 按级别分组返回
```

**告警级别判定**：

| 条件 | 级别 |
|------|------|
| `is_expired = True` | EXPIRED（归入 status CRITICAL） |
| `days_until_expiry <= days_critical` | CRITICAL |
| `days_until_expiry <= days_warning` | WARNING |
| `days_until_expiry > days_warning` | OK |
| cert 查不到 | UNKNOWN |

**整体 status**：有 EXPIRED 或 CRITICAL → `CRITICAL`；有 WARNING → `WARNING`；否则 `OK`。

---

## SKILL.md 变更

### description 字段补充触发词

在 frontmatter `description` 末尾追加：

```
...or checking which virtual servers have expiring or expired SSL certificates linked via SSL profiles
```

### 新增方法文档段落

在 "SSL 证书管理" 节补充：

```python
# VS 关联证书到期巡检（两级告警）
report = ssl.get_vs_ssl_cert_report(config, days_warning=30, days_critical=7)
print(f"整体状态: {report['status']}")
for r in report['expired']:
    print(f"[EXPIRED] {r['vs_name']} → {r['ssl_profile']} → {r['cert_name']}")
for r in report['critical']:
    print(f"[CRITICAL] {r['vs_name']} → {r['cert_name']}，剩余 {r['days_until_expiry']} 天")
```

---

## 测试

在 `tests/test_f5_ssl.py` 追加 2 个测试：

| 测试名 | 场景 | 断言 |
|--------|------|------|
| `test_get_vs_ssl_cert_report_expired` | 1个VS绑过期证书 | `expired` 非空，`status=CRITICAL` |
| `test_get_vs_ssl_cert_report_ok` | 1个VS绑有效证书 | `ok` 非空，`status=OK`，其他列表为空 |

---

## 修改文件清单

| 文件 | 操作 |
|------|------|
| `skills/f5-allinone/f5_ssl.py` | 新增 `get_vs_ssl_cert_report()` 方法 |
| `skills/f5-allinone/SKILL.md` | 更新 description 触发词 + 补充方法文档 |
| `tests/test_f5_ssl.py` | 追加 2 个测试 case |
