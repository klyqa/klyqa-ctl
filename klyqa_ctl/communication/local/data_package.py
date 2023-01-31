"""Data package and data package types."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from klyqa_ctl.general.general import task_log


class PackageType(Enum):
    """Data package types"""

    PLAIN = 0
    IV = 1
    ENC = 2


class PackageException(Exception):
    """Package exception"""


@dataclass
class DataPackage:
    """Data package"""

    _attr_data: bytes = b""
    _attr_length: int = 0
    _attr_type: PackageType = PackageType.PLAIN

    def serialize(self, aes_obj: Any = None) -> bytes:
        """Write package to bytes stream."""

        data: bytes = self.data

        if self.ptype != PackageType.IV:
            while len(data) % 16:
                data = data + bytes([0x20])  # space

        if aes_obj and self.ptype == PackageType.ENC:
            data = aes_obj.encrypt(data)

        return (
            bytes([len(data) // 256, len(data) % 256, 0, self.ptype.value])
            + data
        )

    @classmethod
    def create(
        cls: Any, data: bytes, ptype: PackageType = PackageType.PLAIN
    ) -> DataPackage:
        """Create"""
        pkg: DataPackage = DataPackage(data)
        pkg.length = len(data)
        pkg.ptype = ptype
        return pkg

    @classmethod
    def deserialize(cls: Any, data: bytes) -> DataPackage:
        """Read out the data package as follows: package length, package type
        and package data."""

        pkg: DataPackage = DataPackage()
        pkg.length = data[0] * 256 + data[1]
        pkg.ptype = PackageType(data[3])

        pkg.data = data[4 : 4 + pkg.length]
        if len(pkg.data) < pkg.length:
            task_log("Incomplete packet, waiting for more...")
            raise PackageException

        return pkg

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
    def ptype(self) -> PackageType:
        return self._attr_type

    @ptype.setter
    def ptype(self, pkg_type: PackageType) -> None:
        self._attr_type = pkg_type
