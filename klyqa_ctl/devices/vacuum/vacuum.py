"""Vacuum cleaner"""
from __future__ import annotations

from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.vacuum.response_status import ResponseStatus


class VacuumCleaner(Device):
    """Vaccum cleaner."""

    def __init__(self) -> None:
        """Set the default status class for the device."""

        super().__init__()
        self.response_classes["status"] = ResponseStatus

