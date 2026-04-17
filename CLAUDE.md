# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Install dependencies:
```bash
pip install -r skills/f5-allinone/requirements.txt
```

Run all tests:
```bash
pytest tests/
```

Run a single test file:
```bash
pytest tests/test_f5_client.py
```

Run a single test:
```bash
pytest tests/test_f5_client.py::TestF5Client::test_get_token_success
```

## Architecture

This is a Claude Code **skill plugin** for managing F5 BIG-IP devices via the iControl REST API. The entry point for the skill is [skills/f5-allinone/SKILL.md](skills/f5-allinone/SKILL.md), and plugin metadata is in [.claude-plugin/plugin.json](.claude-plugin/plugin.json).

### Module layout under `skills/f5-allinone/`

All modules import from each other using bare module names (no package prefix), because tests add the directory to `sys.path` directly.

| Module | Class | Responsibility |
|--------|-------|----------------|
| [f5_client.py](skills/f5-allinone/f5_client.py) | `F5Client` | Token auth, HTTP session, all raw REST calls |
| [f5_monitor.py](skills/f5-allinone/f5_monitor.py) | `F5Monitor` | CPU/memory/connections/throughput/HA/interface stats |
| [f5_config.py](skills/f5-allinone/f5_config.py) | `F5Config` | Read-only queries: VS, pool, profile, SNAT |
| [f5_ssl.py](skills/f5-allinone/f5_ssl.py) | `F5SSL` | Certificate expiry listing and alert reports |
| [f5_deploy.py](skills/f5-allinone/f5_deploy.py) | `F5Deploy` | Write operations: create/update VS/pool, atomic transactions |
| [f5_config_parser.py](skills/f5-allinone/f5_config_parser.py) | `F5ConfigParser` | Offline bigip.conf parsing: VS/pool/member extraction, CSV export |

### Key design details

- **Token lifecycle**: `F5Client` auto-refreshes the iControl token 60 seconds before it expires (TTL = 1200s). All higher-level classes call through `F5Client`; they never touch auth directly.
- **Path convention**: REST paths are passed as `/ltm/...` (relative to `/mgmt/tm`). The `~{partition}~{name}` pattern is used for named object references (e.g., `/ltm/virtual/~Common~vs_web`).
- **Transactions**: `F5Deploy.deploy_with_transaction()` wraps multiple changes in an F5 atomic transaction — POST to `/transaction`, execute changes, then PATCH to commit. Use this for multi-step config changes that must succeed or fail together.
- **Offline parsing**: `F5ConfigParser` operates on bigip.conf text files without any network connectivity. It does NOT take `F5Client` — it takes a file path, similar to `F5Inventory`. Supports chunked reading for large config files.
- **SSL verification**: Disabled globally on the session (`verify=False`) because F5 devices commonly use self-signed certs. `urllib3` warnings are suppressed at import time in `f5_client.py`.
- **Bug in f5_client.py**: The `__init__` method hardcodes `self.host`, `self.username`, and `self.password` instead of using the constructor parameters. This must be fixed before the client works with any host other than `10.1.11.14`.

### Tests

Tests live in `tests/` and use `unittest.mock` (no pytest-specific fixtures needed). Each test file manually inserts the module path at `sys.path[0]`. All tests mock the `requests.Session` methods — no live F5 device is required.
