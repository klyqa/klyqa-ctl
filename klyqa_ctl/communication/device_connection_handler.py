"""Connection handler for device."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from klyqa_ctl.general.general import Command
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId


class DeviceConnectionHandler(ABC):  # pylint: disable=too-few-public-methods
    """Abstract class giving the connection handler's send message
    method to the device connection handlers."""

    @abstractmethod
    async def send_command_to_device(
        self,
        send_msgs: list[Command],
        target_device_uid: UnitId,
        time_to_live_secs: float = 30.0,
        **kwargs: Any,
    ) -> Message | None:
        """Send message to device via connection handler."""

    @abstractmethod
    async def send_to_device(
        self,
        unit_id: str,
        key: str,
        command: str,
        time_to_live_secs: float = 30.0,
    ) -> str:
        """Send message to device via connection handler."""
