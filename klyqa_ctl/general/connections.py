"""Local and cloud connections"""

from __future__ import annotations
from typing import Any


class CloudConnection:
    """CloudConnection"""

    _attr_received_packages: list[Any]
    _attr_connected: bool

    def __init__(self) -> None:
        self._attr_connected = False
        self._attr_received_packages = []
        
    @property
    def received_packages(self) -> list[Any]:
        return self._attr_received_packages

    @received_packages.setter
    def received_packages(self, received_packages: list[Any]) -> None:
        self._attr_received_packages = received_packages

    @property
    def connected(self) -> bool:
        return self._attr_connected

    @connected.setter
    def connected(self, connected: bool) -> None:
        self._attr_connected = connected

PROD_HOST: str = "https://app-api.prod.qconnex.io"
TEST_HOST: str = "https://app-api.test.qconnex.io"

