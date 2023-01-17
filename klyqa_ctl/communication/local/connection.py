"""Local connection class"""
from __future__ import annotations
import asyncio

from datetime import datetime
import socket
import traceback
from typing import Any
from enum import Enum, auto

from klyqa_ctl.general.general import ReferenceParse, task_log

try:
    from Cryptodome.Random import get_random_bytes  # pycryptodome
except:
    from Crypto.Random import get_random_bytes  # pycryptodome

class AesConnectionState(str, Enum):
    """AES encrypted connection state."""
    WAIT_IV = "WAIT_IV"
    CONNECTED = "CONNECTED"

class DeviceTcpReturn(Enum):
    NO_ERROR = auto()
    SENT = auto()
    ANSWERED = auto()
    WRONG_UNIT_ID = auto()
    NO_UNIT_ID = auto()
    WRONG_AES = auto()
    TCP_ERROR = auto()
    UNKNOWN_ERROR = auto()
    SOCKET_TIMEOUT = auto()
    NOTHING_DONE = auto()
    SENT_ERROR = auto()
    NO_MESSAGE_TO_SEND = auto()
    DEVICE_LOCK_TIMEOUT = auto()
    ERROR_LOCAL_IV = auto()
    MISSING_AES_KEY = auto()
    RESPONSE_ERROR = auto()
    SEND_ERROR = auto()
    SOCKET_ERROR = auto()
    
class TcpConnection:
    """Local connection class."""

    def __init__(self) -> None:
        self._attr_state: str = AesConnectionState.WAIT_IV
        self._attr_localIv: bytes = get_random_bytes(8)
        self._attr_remoteIv: bytes = b""
        self._attr_sendingAES: Any = None
        self._attr_receivingAES: Any = None
        self._attr_address: dict[str, str | int] = {"ip": "", "port": -1}
        self._attr_socket: socket.socket | None = None
        self._attr_received_packages: list[Any] = []
        self._attr_sent_msg_answer: dict[str, Any] = {}
        self._attr_aes_key_confirmed: bool = False
        self._attr_aes_key: bytes = b""
        self._attr_started: datetime = datetime.now()
        
    @property
    def state(self) -> str:
        return self._attr_state
    
    @state.setter
    def state(self, state: str) -> None:
        self._attr_state = state
    
    @property
    def remoteIv(self) -> bytes:
        return self._attr_localIv
    
    @remoteIv.setter
    def remoteIv(self, remoteIv: bytes) -> None:
        self._attr_remoteIv = remoteIv
    
    @property
    def localIv(self) -> bytes:
        return self._attr_localIv
    
    @localIv.setter
    def localIv(self, localIv: bytes) -> None:
        self._attr_localIv = localIv
    
    @property
    def sendingAES(self) -> Any:
        return self._attr_sendingAES
    
    @sendingAES.setter
    def sendingAES(self, sendingAES: Any) -> None:
        self._attr_sendingAES = sendingAES
    
    @property
    def receivingAES(self) -> Any:
        return self._attr_receivingAES
    
    @receivingAES.setter
    def receivingAES(self, receivingAES: Any) -> None:
        self._attr_receivingAES = receivingAES
    
    @property
    def address(self) -> dict[str, str | int]:
        return self._attr_address
    
    @address.setter
    def address(self, address: dict[str, str | int]) -> None:
        self._attr_address = address
    
    @property
    def socket(self) -> socket.socket | None:
        return self._attr_socket
    
    @socket.setter
    def socket(self, socket: socket.socket | None) -> None:
        self._attr_socket = socket
    
    @property
    def received_packages(self) -> list[Any]:
        return self._attr_received_packages
    
    @received_packages.setter
    def received_packages(self, received_packages: list[Any]) -> None:
        self._attr_received_packages = received_packages
    
    @property
    def sent_msg_answer(self) -> dict[str, Any]:
        return self._attr_sent_msg_answer
    
    @sent_msg_answer.setter
    def sent_msg_answer(self, sent_msg_answer: dict[str, Any]) -> None:
        self._attr_sent_msg_answer = sent_msg_answer
    
    @property
    def aes_key_confirmed(self) -> bool:
        return self._attr_aes_key_confirmed
    
    @aes_key_confirmed.setter
    def aes_key_confirmed(self, aes_key_confirmed: bool) -> None:
        self._attr_aes_key_confirmed = aes_key_confirmed
    
    @property
    def aes_key(self) -> bytes:
        return self._attr_aes_key
    
    @aes_key.setter
    def aes_key(self, aes_key: bytes) -> None:
        self._attr_aes_key = aes_key
    
    @property
    def started(self) -> datetime:
        return self._attr_started
    
    @started.setter
    def started(self, started: datetime) -> None:
        self._attr_started = started
            
    async def read_local_tcp_socket(self, data_ref: ReferenceParse) -> DeviceTcpReturn:
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        if self.socket is None:
            return DeviceTcpReturn.SOCKET_ERROR
        try:
            data_ref.ref = await loop.run_in_executor(None, self.socket.recv, 4096)
            if len(data_ref.ref) == 0:
                task_log("EOF")
                return DeviceTcpReturn.TCP_ERROR
        except socket.timeout:
            task_log("socket.timeout.")
        except:
            task_log(f"{traceback.format_exc()}")
            return DeviceTcpReturn.UNKNOWN_ERROR
        return DeviceTcpReturn.NO_ERROR
        