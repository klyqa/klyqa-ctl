"""General connection handler"""

from __future__ import annotations

from abc import abstractmethod

from klyqa_ctl.communication.device_connection_handler import (
    DeviceConnectionHandler,
)
from klyqa_ctl.communication.local.connection import (
    DeviceTcpReturn,
    TcpConnection,
)
from klyqa_ctl.general.general import ReferencePass


class ConnectionHandler(DeviceConnectionHandler):  # type: ignore[misc]
    """Abstract class for a general connection handler class."""

    @abstractmethod
    async def handle_connection(
        self, device_ref: ReferencePass, connection: TcpConnection
    ) -> DeviceTcpReturn:
        """Handle connection."""
