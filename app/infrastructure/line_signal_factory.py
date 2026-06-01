"""Line signal adapter construction shared by GUI and production tools."""
from __future__ import annotations

from typing import Any

from app.infrastructure.line_signal import LabVIEWTcpLineSignalAdapter, ModbusLineSignalAdapter, VirtualLineSignalAdapter


def create_line_signal(line_config: dict[str, Any], plc_config: dict[str, Any] | None = None):
    if not line_config.get("enabled", False):
        return VirtualLineSignalAdapter()
    adapter_type = line_config.get("type", "modbus")
    if adapter_type == "modbus":
        merged_config = dict(plc_config or {})
        merged_config.update(line_config)
        return ModbusLineSignalAdapter(merged_config)
    if adapter_type == "labview_tcp":
        return LabVIEWTcpLineSignalAdapter(line_config)
    if adapter_type == "virtual":
        return VirtualLineSignalAdapter()
    raise ValueError(f"Unsupported line signal adapter type: {adapter_type}")
