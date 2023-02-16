"""Local and cloud connections"""

from __future__ import annotations

from typing import Any

from klyqa_ctl.communication.device_connection_handler import (
    DeviceConnectionHandler,
)


class DeviceConnection:
    """Device connection state"""

    def __init__(self) -> None:
        self._attr_con: DeviceConnectionHandler | None = None
        self._attr_connected: bool = False
        self._attr_received_packages: list[Any] = []

    @property
    def con(self) -> DeviceConnectionHandler | None:
        return self._attr_con

    @con.setter
    def con(self, con: DeviceConnectionHandler) -> None:
        self._attr_con = con

    @property
    def connected(self) -> bool:
        return self._attr_connected

    @connected.setter
    def connected(self, connected: bool) -> None:
        self._attr_connected = connected

    @property
    def received_packages(self) -> list[Any]:
        return self._attr_received_packages

    @received_packages.setter
    def received_packages(self, received_packages: list[Any]) -> None:
        self._attr_received_packages = received_packages


# class DeviceLocalState(DeviceConnectionState):
#     """Device local connection state"""


# class DeviceCloudState(DeviceConnectionState):
#     """Device cloud connection state"""

#     _attr_received_packages: list[Any]

#     def __init__(self) -> None:
#         super().__init__()
