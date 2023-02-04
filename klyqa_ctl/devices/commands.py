"""Commands for all devices."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from klyqa_ctl.devices.device import Device
from klyqa_ctl.general.general import CommandType, CommandTyped, TypeJson


@dataclass
class CommandWithCheckValues(CommandTyped):
    """Command with check values range limits."""

    _force: bool = False  # protected vars for non json msg usage

    @abstractmethod
    def check_values(self, device: Device) -> bool:
        return False


@dataclass
class PingCommand(CommandTyped):
    """Ping command."""

    def __post_init__(self) -> None:
        self.type = CommandType.PING.value


@dataclass
class FwUpdateCommand(CommandTyped):
    """Firmware update command."""

    url: str = ""

    def __post_init__(self) -> None:
        self.type = CommandType.FW_UPDATE.value

    def url_json(self) -> TypeJson:
        return {"url": self.url}

    def json(self) -> TypeJson:
        return super().json() | self.url_json()


@dataclass
class RebootCommand(CommandTyped):
    """Reboot command."""

    def __post_init__(self) -> None:
        self.type = CommandType.REBOOT.value


@dataclass
class FactoryResetCommand(CommandTyped):
    """Factory reset command."""

    def __post_init__(self) -> None:
        self.type = CommandType.FACTORY_RESET.value
