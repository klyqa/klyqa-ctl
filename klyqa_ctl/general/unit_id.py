"""UnitId class"""

from __future__ import annotations

from dataclasses import dataclass

from klyqa_ctl.general.general import format_uid


@dataclass
class UnitId(str):

    _attr_unit_id: str | None = None

    def __post_init__(self) -> None:
        self.unit_id = self._attr_unit_id

    @property
    def unit_id(self) -> str | None:
        return self._attr_unit_id

    @unit_id.setter
    def unit_id(self, unit_id: str | None) -> None:
        self._attr_unit_id = format_uid(unit_id) if unit_id else ""

    def __str__(self) -> str:
        return self.unit_id if self.unit_id else ""
