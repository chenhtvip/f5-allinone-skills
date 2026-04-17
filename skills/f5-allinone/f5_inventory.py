"""F5 设备清单管理：从 YAML 文件加载并校验设备列表"""
import os
from typing import Any, Dict, List

import yaml

REQUIRED_FIELDS = {"name", "host", "username", "password"}


class F5Inventory:
    """读取和校验 F5 设备清单 YAML 文件"""

    def __init__(self, inventory_path: str):
        self.inventory_path = os.path.abspath(inventory_path)

    def load(self) -> List[Dict[str, Any]]:
        """读取 YAML 清单，返回设备列表（每项含 name/host/port/username/password）"""
        if not os.path.exists(self.inventory_path):
            raise FileNotFoundError(f"设备清单文件不存在: {self.inventory_path}")
        with open(self.inventory_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or "devices" not in data:
            raise ValueError("YAML 格式错误：缺少顶层 'devices' 键")
        devices = data["devices"]
        if not isinstance(devices, list):
            raise ValueError("YAML 格式错误：'devices' 必须是列表")
        result = []
        for item in devices:
            if not isinstance(item, dict):
                continue
            device = {
                "name": str(item.get("name", "")),
                "host": str(item.get("host", "")),
                "port": int(item.get("port", 443)),
                "username": str(item.get("username", "")),
                "password": str(item.get("password", "")),
            }
            result.append(device)
        return result

    def validate(self) -> List[str]:
        """校验清单中所有设备的必填字段，返回错误信息列表（空列表表示校验通过）"""
        try:
            devices = self.load()
        except (FileNotFoundError, ValueError) as e:
            return [str(e)]
        errors = []
        for i, device in enumerate(devices, start=1):
            for field in REQUIRED_FIELDS:
                if not device.get(field):
                    errors.append(f"第 {i} 台设备缺少必填字段: '{field}'")
        return errors
