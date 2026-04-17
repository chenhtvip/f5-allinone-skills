"""F5 离线配置解析：解析 bigip.conf 文件，提取 VS/Pool/Members 映射关系，导出 CSV"""
import re
import csv
import os
from typing import Any, Dict, Iterator, List, Optional, TextIO, Tuple


class F5ConfigParser:
    """解析 F5 BIG-IP 配置文件（bigip.conf），提取 Virtual Server / Pool / Node 映射关系。

    离线解析，不需要 F5 设备连接。支持大文件分块处理。

    用法:
        parser = F5ConfigParser("bigip.conf")
        result = parser.parse()
        parser.export_csv("output.csv")
    """

    def __init__(self, config_path: str, chunk_size: int = 50000):
        """初始化解析器。

        Args:
            config_path: bigip.conf 文件路径
            chunk_size: 分块读取大小（字符数），默认 50000
        """
        if not os.path.isfile(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        self.config_path = config_path
        self.chunk_size = chunk_size
        self._parsed: Optional[Dict[str, Any]] = None

    # ==================== 公开方法 ====================

    def parse(self) -> Dict[str, Any]:
        """解析配置文件，返回完整解析结果。

        Returns:
            {"nodes": dict, "pools": dict, "virtuals": dict}
        """
        if self._parsed is not None:
            return self._parsed

        nodes: Dict[str, str] = {}
        pools: Dict[str, list] = {}
        virtuals: Dict[tuple, dict] = {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            for chunk in self._read_file_chunks(f, self.chunk_size):
                chunk_nodes = self.parse_nodes(chunk)
                chunk_pools = self.parse_pools(chunk)
                chunk_virtuals = self.parse_virtuals(
                    chunk, {**pools, **chunk_pools}, {**nodes, **chunk_nodes}
                )
                nodes.update(chunk_nodes)
                pools.update(chunk_pools)
                virtuals.update(chunk_virtuals)

        self._parsed = {"nodes": nodes, "pools": pools, "virtuals": virtuals}
        return self._parsed

    def export_csv(self, output_path: str = "f5_vs_pool_mapping.csv") -> str:
        """解析配置并导出 CSV 报告。

        Args:
            output_path: 输出 CSV 文件路径

        Returns:
            输出文件路径
        """
        result = self.parse()
        virtuals = result["virtuals"]

        # 计算最大成员数以生成动态列
        member_numbers = set()
        for row in virtuals.values():
            for key in row:
                match = re.match(r"Member (\d+)", key)
                if match:
                    member_numbers.add(int(match.group(1)))

        max_members = max(member_numbers) if member_numbers else 0

        fieldnames = [
            "Virtual Name",
            "Destination IP",
            "Destination Port",
            "Profiles",
            "Rules",
            "Source Address Translation",
            "Pool Name",
        ]
        for i in range(max_members):
            fieldnames.extend([f"Member {i+1} Address", f"Member {i+1} Port"])

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(virtuals.values())

        return output_path

    def get_vs_pool_mapping(self) -> List[Dict[str, Any]]:
        """返回 VS-Pool 映射的扁平字典列表，适合编程消费。

        Returns:
            [{"Virtual Name": ..., "Pool Name": ..., "Member 1 Address": ..., ...}, ...]
        """
        result = self.parse()
        return list(result["virtuals"].values())

    # ==================== 解析方法 ====================

    def parse_nodes(self, config: str) -> Dict[str, str]:
        """解析 ltm node 配置块。

        Args:
            config: 配置文本

        Returns:
            {node_name: ip_or_fqdn, ...} 含全路径和短名称双键
        """
        nodes = {}
        node_re = re.compile(r"ltm node (?P<node>[^\s\{]+)\s*\{", re.IGNORECASE)
        for m in node_re.finditer(config):
            name = m.group("node").strip()
            block, _, _ = self._extract_block_after_header(config, m)
            ip = re.search(r"address\s+([\d\.]+)", block)
            fqdn = re.search(r"fqdn\s*\{[^}]*?name\s+(\S+)", block, re.DOTALL)
            value = fqdn.group(1) if fqdn else ip.group(1) if ip else "UNKNOWN"
            nodes[name] = value
            base = name.split("/")[-1]
            if base not in nodes:
                nodes[base] = value
        return nodes

    def parse_pools(self, config: str) -> Dict[str, list]:
        """解析 ltm pool 配置块。

        Args:
            config: 配置文本

        Returns:
            {pool_name: [{"name": ..., "port": ..., "type": "ip"|"fqdn", "fqdn": ...}, ...]}
        """
        pools = {}
        pool_re = re.compile(r"ltm pool (?P<pool>[^\s\{]+)\s*\{", re.IGNORECASE)

        for m in pool_re.finditer(config):
            pool_name = m.group("pool").strip()
            block, _, _ = self._extract_block_after_header(config, m)
            members = []

            mem_hdr = re.search(r"members\s*\{", block, re.IGNORECASE)
            if mem_hdr:
                mem_block, _, _ = self._extract_block_after_header(block, mem_hdr)
                for mm in re.finditer(r"([^\s\{\:][^\s\{]*?):(\d+)\s*\{", mem_block):
                    member_ref = mm.group(1).strip()
                    member_port = mm.group(2).strip()
                    brace_start = mm.end() - 1
                    brace_end = self._find_matching_brace(mem_block, brace_start)
                    inner = mem_block[brace_start + 1:brace_end] if brace_end != -1 else ""
                    fq = re.search(r"fqdn\s*\{[^}]*?name\s+(\S+)", inner, re.DOTALL)
                    if fq:
                        members.append({
                            "name": member_ref, "port": member_port,
                            "type": "fqdn", "fqdn": fq.group(1)
                        })
                    else:
                        members.append({
                            "name": member_ref, "port": member_port,
                            "type": "ip", "fqdn": None
                        })

            pools[pool_name] = members
            base = pool_name.split("/")[-1]
            if base not in pools:
                pools[base] = members
        return pools

    def parse_virtuals(self, config: str, pools: Dict[str, list],
                       nodes: Dict[str, str]) -> Dict[tuple, dict]:
        """解析 ltm virtual 配置块并关联 Pool/Node 信息。

        Args:
            config: 配置文本
            pools: 已解析的 Pool 字典
            nodes: 已解析的 Node 字典

        Returns:
            {(vs_name, pool_name): {"Virtual Name": ..., "Pool Name": ..., ...}}
        """
        vs_re = re.compile(r"ltm virtual (?P<vs>[^\s\{]+)\s*\{", re.IGNORECASE)
        results = {}

        for m in vs_re.finditer(config):
            vs_name = m.group("vs").strip()
            block, _, _ = self._extract_block_after_header(config, m)

            # 支持任意分区（不仅限于 /Common/）
            dest = re.search(r"destination\s+(?:/[^/]+/)?([\d\.]+):(\d+)", block)
            pool_ref = re.search(r"pool\s+([^\s\}]+)", block)
            sat = re.search(r"source-address-translation\s*\{\s*type\s+(\S+)",
                            block, re.IGNORECASE)

            dest_ip = dest.group(1) if dest else ""
            dest_port = dest.group(2) if dest else ""
            pool_name = pool_ref.group(1) if pool_ref else ""
            sat_type = sat.group(1) if sat else ""

            # 提取 profiles
            profiles_list = []
            profiles_hdr = re.search(r"profiles\s*\{", block, re.IGNORECASE)
            if profiles_hdr:
                profiles_block, _, _ = self._extract_block_after_header(block, profiles_hdr)
                for pm in re.finditer(r"(/[^\s\{]+)\s*\{", profiles_block):
                    profiles_list.append(pm.group(1).strip())
            profiles_str = ", ".join(profiles_list) if profiles_list else ""

            # 提取 rules
            rules_list = []
            rules_hdr = re.search(r"rules\s*\{", block, re.IGNORECASE)
            if rules_hdr:
                rules_block, _, _ = self._extract_block_after_header(block, rules_hdr)
                for rm in re.finditer(r"(/[^\s\n]+)", rules_block):
                    rule_name = rm.group(1).strip()
                    if rule_name not in ("{", "}"):
                        rules_list.append(rule_name)
            rules_str = ", ".join(rules_list) if rules_list else ""

            # 关联 Pool 成员
            pool_members = pools.get(pool_name) or pools.get(pool_name.split("/")[-1]) or []

            node_values = []
            member_ports = []
            for mem in pool_members:
                if mem["type"] == "fqdn":
                    node_value = mem["fqdn"]
                else:
                    base = mem["name"].split("/")[-1]
                    node_value = nodes.get(mem["name"]) or nodes.get(base) or mem["name"]
                node_values.append(node_value)
                member_ports.append(mem["port"])

            key = (vs_name, pool_name)
            results[key] = {
                "Virtual Name": vs_name,
                "Destination IP": dest_ip,
                "Destination Port": dest_port,
                "Profiles": profiles_str,
                "Rules": rules_str,
                "Source Address Translation": sat_type,
                "Pool Name": pool_name,
            }

            for i in range(len(node_values)):
                if node_values[i] and member_ports[i]:
                    results[key][f"Member {i+1} Address"] = node_values[i]
                    results[key][f"Member {i+1} Port"] = member_ports[i]

        return results

    # ==================== 内部工具方法 ====================

    @staticmethod
    def _find_matching_brace(text: str, start_idx: int) -> int:
        """查找与 start_idx 处 '{' 匹配的 '}' 位置"""
        depth = 0
        for i in range(start_idx, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return i
        return -1

    @staticmethod
    def _extract_block_after_header(text: str, header_match) -> Tuple[str, int, int]:
        """提取 header 后面 {...} 块的内容"""
        brace_start = text.find("{", header_match.end() - 1)
        if brace_start == -1:
            return "", -1, -1
        brace_end = F5ConfigParser._find_matching_brace(text, brace_start)
        if brace_end == -1:
            return "", -1, -1
        return text[brace_start + 1:brace_end], brace_start, brace_end

    @staticmethod
    def _read_file_chunks(file: TextIO, chunk_size: int = 50000) -> Iterator[str]:
        """按块读取文件，确保不会在配置块中间断开"""
        buffer = ""
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                if buffer:
                    yield buffer
                break

            buffer += chunk

            last_complete = buffer.rfind("\n}")
            if last_complete != -1:
                yield buffer[:last_complete + 2]
                buffer = buffer[last_complete + 2:]
