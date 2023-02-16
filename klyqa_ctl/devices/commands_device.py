"""Commands for all devices."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from klyqa_ctl.devices.device import Device
from klyqa_ctl.general.general import CommandTyped


@dataclass
class CommandWithCheckValues(CommandTyped):
    """Command with check values range limits."""

    _force: bool = False  # protected vars for non json msg usage

    @abstractmethod
    def check_values(self, device: Device) -> bool:
        return False
