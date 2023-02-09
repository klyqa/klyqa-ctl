"""Connection handler for device."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from klyqa_ctl.general.general import DEFAULT_SEND_TIMEOUT_MS, Command
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId


class DeviceConnectionHandler(ABC):  # pylint: disable=too-few-public-methods
    """Abstract class giving the connection handler's send message
    method to the device connection handlers."""

    @abstractmethod
    async def send_command_to_device(
        self,
        unit_id: UnitId,
        send_msgs: list[Command],
        aes_key: str = "",
        time_to_live_secs: float = DEFAULT_SEND_TIMEOUT_MS,
        **kwargs: Any,
    ) -> Message | None:
        """Send message to device via connection handler."""

    @abstractmethod
    async def send_to_device(
        self,
        unit_id: str,
        command: str,
        key: str = "",
        time_to_live_secs: float = DEFAULT_SEND_TIMEOUT_MS,
    ) -> str:
        """Send message to device via connection handler."""
