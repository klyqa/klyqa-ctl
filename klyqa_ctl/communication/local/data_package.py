"""Data package and data package types."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from klyqa_ctl.general.general import task_log

class PackageType(Enum):
    """Data package types"""
    IDENTITY = 0
    AES_INITIAL_VECTOR = 1
    DATA = 2

@dataclass
class DataPackage:
    """Data package"""
    
    _attr_raw_data: bytes
    _attr_data: bytes = b""
    _attr_length: int = 0
    _attr_type: PackageType | None = None
    _attr__valid: bool = False
        
    def read_raw_data(self) -> bool:
        """Read out the data package as follows: package length, package type and package data."""
        self.length = self.raw_data[0] * 256 + self.raw_data[1]
        self.type = PackageType(self.raw_data[3])

        self.data = self.raw_data[4 : 4 + self.length]
        if len(self.data) < self.length:
            task_log(f"Incomplete packet, waiting for more...")
            self._valid = False
            return False

        self._valid = True
        return True

    @property
    def raw_data(self) -> bytes:
        return self._attr_raw_data

    @raw_data.setter
    def raw_data(self, raw_data: bytes) -> None:
        self._attr_raw_data = raw_data

    @property
    def data(self) -> bytes:
        return self._attr_data

    @data.setter
    def data(self, data: bytes) -> None:
        self._attr_data = data

    @property
    def length(self) -> int:
        return self._attr_length

    @length.setter
    def length(self, length: int) -> None:
        self._attr_length = length

    @property
    def type(self) -> PackageType | None:
        return self._attr_type

    @type.setter
    def type(self, type: PackageType | None) -> None:
        self._attr_type = type

    @property
    def valid(self) -> bool:
        return self._attr__valid
    
    @property
    def _valid(self) -> bool:
        return self._valid

    @_valid.setter
    def _valid(self, _valid: bool) -> None:
        self._attr__valid = _valid
