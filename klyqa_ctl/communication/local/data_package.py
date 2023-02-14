"""Data package and data package types."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from klyqa_ctl.general.general import task_log, task_log_trace


class PackageType(IntEnum):
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
        data_coded: bytes = b""

        if self.ptype != PackageType.IV:
            while len(data) % 16:
                data = data + bytes([0x20])  # space

        if aes_obj and self.ptype == PackageType.ENC:
            data_coded = aes_obj.encrypt(data)
        else:
            data_coded = data

        serialized: bytes = (
            bytes(
                [
                    len(data_coded) // 256,
                    len(data_coded) % 256,
                    0,
                    self.ptype.value,
                ]
            )
            + data_coded
        )

        task_log_trace("Serialized package data: %s", serialized)

        return serialized

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
