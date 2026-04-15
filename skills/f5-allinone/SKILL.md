---
name: f5-allinone
description: Use when working with F5 BIG-IP load balancers via API - monitoring device status (CPU/memory/HA/connections), querying configuration (virtual servers/pools/profiles/SNAT), managing SSL certificates with expiry alerts, or deploying configuration changes programmatically via iControl REST API
---

# F5 All-in-One Management Skill

## Overview

通过 F5 iControl REST API 实现完整的 F5 BIG-IP 设备管理，支持：
- **状态监控**：CPU/内存/连接/吞吐/HA状态/接口流量
- **配置查询**：Virtual Server/Pool/Profile/SNAT
- **SSL证书管理**：到期查询与有效期提醒
- **配置下发**：原子事务式配置变更

## 快速开始

```python
from f5_client import F5Client
from f5_monitor import F5Monitor
from f5_config import F5Config
from f5_ssl import F5SSL
from f5_deploy import F5Deploy

# 初始化客户端（自动处理Token认证）
client = F5Client(host="192.168.1.1", username="admin", password="your_password")

# 状态监控
monitor = F5Monitor(client)
status = monitor.get_all_status()

# 配置查询
config = F5Config(client)
vservers = config.list_virtual_servers()

# SSL 证书
ssl = F5SSL(client)
report = ssl.get_summary_report(days_warning=30, days_critical=7)

# 配置下发
deploy = F5Deploy(client)
deploy.create_pool("pool_new", [{"address": "192.168.1.10", "port": 80}])
```

## 状态监控 (F5Monitor)

| 方法 | 功能 |
|------|------|
| `get_cpu_usage()` | CPU使用率（5秒平均值） |
| `get_memory_usage()` | 内存总量/已用/使用率 |
| `get_connections()` | 并发连接数/新建连接数 |
| `get_throughput()` | 吞吐量 (bps/Mbps) |
| `get_ha_status()` | HA 角色（ACTIVE/STANDBY）|
| `get_sync_status()` | 配置同步状态 |
| `get_interface_stats()` | 各接口进出流量 |
| `get_all_status()` | 以上所有指标汇总 |

## 配置查询 (F5Config)

| 方法 | 功能 |
|------|------|
| `list_virtual_servers()` | 列出所有 VS |
| `get_virtual_server(name)` | VS 详情 |
| `list_pools()` | 列出所有 Pool 含成员状态 |
| `get_pool_members(pool_name)` | Pool 成员列表 |
| `list_profiles(profile_type)` | Profile 列表（http/tcp/ssl-client等）|
| `list_snat_pools()` | SNAT Pool 列表 |

## SSL 证书管理 (F5SSL)

```python
# 获取30天内到期的证书
expiring = ssl.get_expiring_certificates(days_threshold=30)

# 生成状态报告（自动分级 OK/WARNING/CRITICAL）
report = ssl.get_summary_report(days_warning=30, days_critical=7)
print(f"状态: {report['status']}")
print(f"已过期: {len(report['expired'])} 个")
print(f"即将过期(7天内): {len(report['critical'])} 个")
```

## 配置下发 (F5Deploy)

### 单个操作

```python
# 创建 Virtual Server
deploy.create_virtual_server(
    name="vs_web_443",
    destination="10.0.0.1:443",
    pool="pool_web",
    profiles=["http", "ssl-offload"]
)

# 禁用 Pool 成员（下线维护）
deploy.update_pool_member_state("pool_web", "192.168.1.10:80", enabled=False)

# 保存配置
deploy.save_config()
```

### 事务式批量下发

```python
changes = [
    {"method": "POST", "path": "/ltm/pool",
     "body": {"name": "pool_api", "loadBalancingMode": "round-robin"}},
    {"method": "POST", "path": "/ltm/virtual",
     "body": {"name": "vs_api", "destination": "/Common/10.0.0.5:8080",
               "pool": "/Common/pool_api"}}
]
result = deploy.deploy_with_transaction(changes)
```

## F5 设备连接要求

- F5 BIG-IP 版本：12.x 及以上（iControl REST API）
- 账号权限：需要 Administrator 或 Resource Administrator 角色
- 网络：管理口（MGMT）可达，默认端口 443
- SSL：设备使用自签名证书时自动跳过验证（urllib3 警告已抑制）
