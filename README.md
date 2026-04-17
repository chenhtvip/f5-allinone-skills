# F5 All-in-One Skills

适用于 Claude Code 的 F5 BIG-IP 一体化管理插件，通过 iControl REST API 实现设备监控、配置查询、SSL 证书管理、配置下发与批量巡检，以及离线 bigip.conf 解析。

## 功能模块

| 模块 | 功能 |
|------|------|
| `F5Monitor` | CPU / 内存 / 连接 / 吞吐 / HA 状态 / 接口流量监控 |
| `F5Config` | Virtual Server / Pool / Profile / SNAT 配置查询 |
| `F5SSL` | SSL 证书到期查询、分级告警、VS 关联证书巡检 |
| `F5Deploy` | 创建/更新 VS/Pool，原子事务式批量配置下发 |
| `F5Audit` | 多设备批量巡检，结果导出 CSV 报告 |
| `F5ConfigParser` | 离线解析 bigip.conf，提取 VS/Pool/Members，导出 CSV |

## 快速开始

### 安装依赖

```bash
pip install -r skills/f5-allinone/requirements.txt
```

### 基本用法

```python
from f5_client import F5Client
from f5_monitor import F5Monitor
from f5_config import F5Config
from f5_ssl import F5SSL
from f5_deploy import F5Deploy

# 初始化客户端（自动处理 Token 认证与刷新）
client = F5Client(host="192.168.1.1", username="admin", password="your_password")

# 状态监控
monitor = F5Monitor(client)
status = monitor.get_all_status()

# 配置查询
config = F5Config(client)
vservers = config.list_virtual_servers()

# SSL 证书报告
ssl = F5SSL(client)
report = ssl.get_summary_report(days_warning=30, days_critical=7)

# 配置下发
deploy = F5Deploy(client)
deploy.create_pool("pool_new", [{"address": "192.168.1.10", "port": 80}])
```

### 批量巡检

编辑 `skills/f5-allinone/inventory.yaml`：

```yaml
devices:
  - name: f5-prod-01
    host: 10.1.1.14
    port: 443
    username: admin
    password: your_password
```

执行巡检：

```python
from f5_audit import F5Audit

audit = F5Audit("inventory.yaml")
results = audit.run_all()
audit.export_csv(results, "audit_report.csv")
```

### 离线配置解析

```python
from f5_config_parser import F5ConfigParser

parser = F5ConfigParser("bigip.conf")
parser.export_csv("vs_pool_mapping.csv")
```

## 运行测试

```bash
pytest tests/
```

## 设备要求

- F5 BIG-IP 12.x 及以上（iControl REST API）
- 账号需要 Administrator 或 Resource Administrator 角色
- 管理口（MGMT）443 端口可达
