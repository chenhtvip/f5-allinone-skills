import os
import sys
import csv
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'f5-allinone'))

from f5_config_parser import F5ConfigParser

# ==================== 测试数据 ====================

SIMPLE_CONFIG = """\
ltm node /Common/10.1.201.200 {
    address 10.1.201.200
}
ltm node /Common/10.1.97.59 {
    address 10.1.97.59
}
ltm pool /Common/DEMO_59 {
    members {
        /Common/10.1.201.200:80 {
            address 10.1.201.200
        }
        /Common/10.1.97.59:80 {
            address 10.1.97.59
        }
    }
    monitor /Common/tcp
}
ltm virtual /Common/DEMO_80 {
    destination /Common/10.1.100.53:80
    pool /Common/DEMO_59
    profiles {
        /Common/http {
            context all
        }
        /Common/tcp { }
    }
    rules {
        /Common/Rule_Insert_ClientIP
        /Common/demo_pool_selected
    }
    source-address-translation {
        type automap
    }
}
"""

FQDN_CONFIG = """\
ltm node /Common/api.example.com {
    fqdn {
        autopopulate enabled
        name api.example.com
    }
}
ltm pool /Common/pool_fqdn {
    members {
        /Common/api.example.com:443 {
            fqdn {
                autopopulate enabled
                name api.example.com
            }
        }
    }
}
ltm virtual /Common/vs_fqdn {
    destination /Common/10.0.0.1:443
    pool /Common/pool_fqdn
}
"""

VS_WITHOUT_POOL = """\
ltm virtual /Common/vs_forward {
    destination /Common/0.0.0.0:0
    profiles {
        /Common/fastL4 { }
    }
}
"""

MULTI_PARTITION_CONFIG = """\
ltm node /Tenant1/10.2.0.1 {
    address 10.2.0.1
}
ltm pool /Tenant1/pool_app {
    members {
        /Tenant1/10.2.0.1:8080 {
            address 10.2.0.1
        }
    }
}
ltm virtual /Tenant1/vs_app {
    destination /Tenant1/10.2.0.100:443
    pool /Tenant1/pool_app
}
"""


def _write_temp_config(content):
    """写入临时配置文件并返回路径"""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


class TestF5ConfigParser:

    def test_parse_simple_vs_pool_node(self):
        path = _write_temp_config(SIMPLE_CONFIG)
        try:
            parser = F5ConfigParser(path)
            result = parser.parse()

            assert "10.1.201.200" in result["nodes"].values()
            assert "/Common/DEMO_59" in result["pools"]
            assert len(result["pools"]["/Common/DEMO_59"]) == 2

            virtuals = result["virtuals"]
            assert len(virtuals) == 1
            key = ("/Common/DEMO_80", "/Common/DEMO_59")
            assert key in virtuals
            vs = virtuals[key]
            assert vs["Virtual Name"] == "/Common/DEMO_80"
            assert vs["Destination IP"] == "10.1.100.53"
            assert vs["Destination Port"] == "80"
            assert vs["Pool Name"] == "/Common/DEMO_59"
            assert vs["Member 1 Address"] == "10.1.201.200"
            assert vs["Member 1 Port"] == "80"
            assert vs["Member 2 Address"] == "10.1.97.59"
            assert vs["Member 2 Port"] == "80"
        finally:
            os.unlink(path)

    def test_parse_fqdn_node(self):
        path = _write_temp_config(FQDN_CONFIG)
        try:
            parser = F5ConfigParser(path)
            result = parser.parse()

            assert result["nodes"].get("/Common/api.example.com") == "api.example.com"

            members = result["pools"]["/Common/pool_fqdn"]
            assert len(members) == 1
            assert members[0]["type"] == "fqdn"
            assert members[0]["fqdn"] == "api.example.com"

            vs = list(result["virtuals"].values())[0]
            assert vs["Member 1 Address"] == "api.example.com"
        finally:
            os.unlink(path)

    def test_parse_multiple_members(self):
        path = _write_temp_config(SIMPLE_CONFIG)
        try:
            parser = F5ConfigParser(path)
            vs = list(parser.parse()["virtuals"].values())[0]
            assert "Member 1 Address" in vs
            assert "Member 2 Address" in vs
            assert vs["Member 1 Port"] == "80"
            assert vs["Member 2 Port"] == "80"
        finally:
            os.unlink(path)

    def test_parse_profiles_extraction(self):
        path = _write_temp_config(SIMPLE_CONFIG)
        try:
            parser = F5ConfigParser(path)
            vs = list(parser.parse()["virtuals"].values())[0]
            profiles = vs["Profiles"]
            assert "/Common/http" in profiles
            assert "/Common/tcp" in profiles
        finally:
            os.unlink(path)

    def test_parse_irules_extraction(self):
        path = _write_temp_config(SIMPLE_CONFIG)
        try:
            parser = F5ConfigParser(path)
            vs = list(parser.parse()["virtuals"].values())[0]
            rules = vs["Rules"]
            assert "/Common/Rule_Insert_ClientIP" in rules
            assert "/Common/demo_pool_selected" in rules
        finally:
            os.unlink(path)

    def test_parse_snat_type(self):
        path = _write_temp_config(SIMPLE_CONFIG)
        try:
            parser = F5ConfigParser(path)
            vs = list(parser.parse()["virtuals"].values())[0]
            assert vs["Source Address Translation"] == "automap"
        finally:
            os.unlink(path)

    def test_parse_vs_without_pool(self):
        path = _write_temp_config(VS_WITHOUT_POOL)
        try:
            parser = F5ConfigParser(path)
            result = parser.parse()
            assert len(result["virtuals"]) == 1
            vs = list(result["virtuals"].values())[0]
            assert vs["Pool Name"] == ""
            assert "Member 1 Address" not in vs
        finally:
            os.unlink(path)

    def test_parse_empty_config(self):
        path = _write_temp_config("")
        try:
            parser = F5ConfigParser(path)
            result = parser.parse()
            assert result["nodes"] == {}
            assert result["pools"] == {}
            assert result["virtuals"] == {}
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            F5ConfigParser("/nonexistent/path/bigip.conf")

    def test_export_csv(self):
        conf_path = _write_temp_config(SIMPLE_CONFIG)
        csv_path = tempfile.mktemp(suffix=".csv")
        try:
            parser = F5ConfigParser(conf_path)
            result_path = parser.export_csv(csv_path)
            assert result_path == csv_path
            assert os.path.isfile(csv_path)

            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["Virtual Name"] == "/Common/DEMO_80"
            assert rows[0]["Destination IP"] == "10.1.100.53"
            assert rows[0]["Member 1 Address"] == "10.1.201.200"
            assert rows[0]["Member 2 Address"] == "10.1.97.59"
            assert "Member 1 Port" in reader.fieldnames
            assert "Member 2 Port" in reader.fieldnames
        finally:
            os.unlink(conf_path)
            if os.path.isfile(csv_path):
                os.unlink(csv_path)

    def test_get_vs_pool_mapping(self):
        path = _write_temp_config(SIMPLE_CONFIG)
        try:
            parser = F5ConfigParser(path)
            mapping = parser.get_vs_pool_mapping()
            assert isinstance(mapping, list)
            assert len(mapping) == 1
            assert mapping[0]["Virtual Name"] == "/Common/DEMO_80"
        finally:
            os.unlink(path)

    def test_parse_caching(self):
        path = _write_temp_config(SIMPLE_CONFIG)
        try:
            parser = F5ConfigParser(path)
            result1 = parser.parse()
            result2 = parser.parse()
            assert result1 is result2
        finally:
            os.unlink(path)

    def test_chunked_reading(self):
        """使用很小的 chunk_size 强制多块处理，验证结果与单块一致"""
        path = _write_temp_config(SIMPLE_CONFIG)
        try:
            parser_normal = F5ConfigParser(path, chunk_size=50000)
            parser_chunked = F5ConfigParser(path, chunk_size=100)

            result_normal = parser_normal.parse()
            result_chunked = parser_chunked.parse()

            assert len(result_normal["virtuals"]) == len(result_chunked["virtuals"])
            # 比较 VS 名称集合
            vs_names_normal = {v["Virtual Name"] for v in result_normal["virtuals"].values()}
            vs_names_chunked = {v["Virtual Name"] for v in result_chunked["virtuals"].values()}
            assert vs_names_normal == vs_names_chunked
        finally:
            os.unlink(path)

    def test_non_common_partition(self):
        """验证非 /Common/ 分区的配置也能正确解析"""
        path = _write_temp_config(MULTI_PARTITION_CONFIG)
        try:
            parser = F5ConfigParser(path)
            result = parser.parse()

            assert "/Tenant1/10.2.0.1" in result["nodes"]
            assert "/Tenant1/pool_app" in result["pools"]

            vs = list(result["virtuals"].values())[0]
            assert vs["Virtual Name"] == "/Tenant1/vs_app"
            assert vs["Destination IP"] == "10.2.0.100"
            assert vs["Destination Port"] == "443"
            assert vs["Member 1 Address"] == "10.2.0.1"
        finally:
            os.unlink(path)
