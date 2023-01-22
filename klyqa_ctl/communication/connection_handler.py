"""General connection handler"""

from __future__ import annotations
from abc import abstractmethod

from klyqa_ctl.communication.local.connection import DeviceTcpReturn, TcpConnection
from klyqa_ctl.general.general import ReferenceParse

class ConnectionHandler:
    
    @abstractmethod
    async def handle_connection(
        self,
        device_ref: ReferenceParse,
        connection: TcpConnection
    ) -> DeviceTcpReturn:
        pass
