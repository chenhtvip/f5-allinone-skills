import pytest
from unittest.mock import MagicMock, patch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'f5-allinone'))

from f5_monitor import F5Monitor


class TestF5Monitor:
    def setup_method(self):
        self.mock_client = MagicMock()
        self.monitor = F5Monitor(self.mock_client)

    def test_get_cpu_usage(self):
        self.mock_client.get.return_value = {
            "entries": {
                "https://localhost/mgmt/tm/sys/cpu/0": {
                    "nestedStats": {
                        "entries": {
                            "fiveSecAvgIdle": {"value": 85},
                            "fiveSecAvgSystem": {"value": 10},
                            "fiveSecAvgUser": {"value": 5}
                        }
                    }
                }
            }
        }
        result = self.monitor.get_cpu_usage()
        assert "cpu_usage_pct" in result
        assert result["cpu_usage_pct"] == 15  # 100 - idle(85)
        self.mock_client.get.assert_called_once_with("/sys/cpu/stats")

    def test_get_memory_usage(self):
        self.mock_client.get.return_value = {
            "entries": {
                "https://localhost/mgmt/tm/sys/memory/0": {
                    "nestedStats": {
                        "entries": {
                            "memoryTotal": {"value": 8589934592},
                            "memoryUsed": {"value": 4294967296}
                        }
                    }
                }
            }
        }
        result = self.monitor.get_memory_usage()
        assert result["memory_total_mb"] == 8192
        assert result["memory_used_mb"] == 4096
        assert result["memory_usage_pct"] == 50.0

    def test_get_connections(self):
        self.mock_client.get.return_value = {
            "entries": {
                "https://localhost/mgmt/tm/sys/performance/connections/0": {
                    "nestedStats": {
                        "entries": {
                            "oneMinAvgUsageRatio": {"value": 30},
                            "Current Active Connections": {"value": 5000},
                            "New Connections": {"value": 200}
                        }
                    }
                }
            }
        }
        result = self.monitor.get_connections()
        assert "active_connections" in result
        assert "new_connections_per_sec" in result

    def test_get_throughput(self):
        self.mock_client.get.return_value = {
            "entries": {
                "https://localhost/mgmt/tm/sys/performance/throughput/0": {
                    "nestedStats": {
                        "entries": {
                            "Throughput(bits/sec)": {"value": 1000000000},
                            "In": {"value": 600000000},
                            "Out": {"value": 400000000}
                        }
                    }
                }
            }
        }
        result = self.monitor.get_throughput()
        assert "throughput_bps" in result
        assert "in_bps" in result
        assert "out_bps" in result

    def test_get_ha_status(self):
        self.mock_client.get.return_value = {
            "entries": {
                "https://localhost/mgmt/tm/cm/failover-status/0": {
                    "nestedStats": {
                        "entries": {
                            "status": {"description": "ACTIVE"},
                            "color": {"description": "green"}
                        }
                    }
                }
            }
        }
        result = self.monitor.get_ha_status()
        assert result["ha_status"] == "ACTIVE"
        assert result["ha_color"] == "green"

    def test_get_sync_status(self):
        self.mock_client.get.return_value = {
            "entries": {
                "https://localhost/mgmt/tm/cm/sync-status/0": {
                    "nestedStats": {
                        "entries": {
                            "status": {"description": "In Sync"},
                            "color": {"description": "green"},
                            "summary": {"description": ""}
                        }
                    }
                }
            }
        }
        result = self.monitor.get_sync_status()
        assert result["sync_status"] == "In Sync"
        assert result["is_synced"] is True

    def test_get_interface_stats(self):
        self.mock_client.get.return_value = {
            "entries": {
                "https://localhost/mgmt/tm/net/interface/~Common~1.1/stats": {
                    "nestedStats": {
                        "entries": {
                            "tmName": {"description": "1.1"},
                            "status": {"description": "up"},
                            "counters.bitsIn": {"value": 1000000},
                            "counters.bitsOut": {"value": 500000},
                            "counters.pktsIn": {"value": 1000},
                            "counters.pktsOut": {"value": 800}
                        }
                    }
                }
            }
        }
        result = self.monitor.get_interface_stats()
        assert len(result) >= 1
        iface = result[0]
        assert "name" in iface
        assert "status" in iface
        assert "bits_in" in iface

    def test_get_all_status(self):
        self.monitor.get_cpu_usage = MagicMock(return_value={"cpu_usage_pct": 15})
        self.monitor.get_memory_usage = MagicMock(return_value={"memory_usage_pct": 50})
        self.monitor.get_connections = MagicMock(return_value={"active_connections": 5000})
        self.monitor.get_throughput = MagicMock(return_value={"throughput_bps": 1e9})
        self.monitor.get_ha_status = MagicMock(return_value={"ha_status": "ACTIVE"})
        self.monitor.get_sync_status = MagicMock(return_value={"sync_status": "In Sync"})
        self.monitor.get_interface_stats = MagicMock(return_value=[])

        result = self.monitor.get_all_status()
        assert "cpu" in result
        assert "memory" in result
        assert "connections" in result
        assert "throughput" in result
        assert "ha" in result
        assert "sync" in result
        assert "interfaces" in result
