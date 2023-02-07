"""Device group."""
from __future__ import annotations

from klyqa_ctl.devices.device import Device


class DeviceGroup(Device):
    """Device group class."""

    def __init__(self) -> None:
        """Initiliaze device group."""

        super().__init__()

        self.u_id = ""
        self.name = ""
        self.devices: dict[str, Device] = {}
