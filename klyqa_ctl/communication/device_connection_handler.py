"""Connection handler for device"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from klyqa_ctl.general.general import Command
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId


class DeviceConnectionHandler(ABC):
    """Abstract class giving the connection handler's send message
    method to the device connection handlers."""

    @abstractmethod
    async def send_message(
        self,
        send_msgs: list[Command],
        target_device_uid: UnitId,
        time_to_live_secs: float = -1.0,
        **kwargs: Any,
    ) -> Message | None:
        pass
