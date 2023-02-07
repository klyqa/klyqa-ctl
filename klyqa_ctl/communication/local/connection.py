"""Local connection class"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from enum import Enum, auto
import json
import logging
import socket
from typing import Any

from klyqa_ctl.communication.local.data_package import DataPackage, PackageType
from klyqa_ctl.devices.device import Device
from klyqa_ctl.general.general import (
    LOGGER,
    MAX_SOCKET_SEND_TIMEOUT_SECS,
    ReferencePass,
    get_asyncio_loop,
    task_log,
    task_log_debug,
    task_log_trace_ex,
    task_name,
)

try:
    from Cryptodome.Random import get_random_bytes  # pycryptodome
except ImportError:
    from Crypto.Random import get_random_bytes  # pycryptodome


class AesConnectionState(str, Enum):
    """AES encrypted connection state."""

    WAIT_IV = "WAIT_IV"
    CONNECTED = "CONNECTED"


class DeviceTcpReturn(Enum):
    NO_ERROR = auto()
    # SENT = auto()
    ANSWERED = auto()
    WRONG_UNIT_ID = auto()
    NO_UNIT_ID = auto()
    WRONG_AES = auto()
    TCP_ERROR = auto()
    TCP_SOCKET_CLOSED_UNEXPECTEDLY = auto()
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
    MSG_VALUES_OUT_OF_RANGE_LIMITS = auto()


class TcpConnection:
    """Local connection class."""

    def __init__(self) -> None:
        self._attr_state: str = AesConnectionState.WAIT_IV
        self._attr_local_iv: bytes = get_random_bytes(8)
        self._attr_remote_iv: bytes = b""
        self._attr_sending_aes: Any = None
        self._attr_receiving_aes: Any = None
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
    def remote_iv(self) -> bytes:
        return self._attr_remote_iv

    @remote_iv.setter
    def remote_iv(self, remote_iv: bytes) -> None:
        self._attr_remote_iv = remote_iv

    @property
    def local_iv(self) -> bytes:
        return self._attr_local_iv

    @local_iv.setter
    def local_iv(self, local_iv: bytes) -> None:
        self._attr_local_iv = local_iv

    @property
    def sending_aes(self) -> Any:
        return self._attr_sending_aes

    @sending_aes.setter
    def sending_aes(self, sending_aes: Any) -> None:
        self._attr_sending_aes = sending_aes

    @property
    def receiving_aes(self) -> Any:
        return self._attr_receiving_aes

    @receiving_aes.setter
    def receiving_aes(self, receiving_aes: Any) -> None:
        self._attr_receiving_aes = receiving_aes

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
    def socket(self, socket_new: socket.socket | None) -> None:
        self._attr_socket = socket_new

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

    async def read_local_tcp_socket(
        self, data_ref: ReferencePass
    ) -> DeviceTcpReturn:
        """Read from tcp socket and handle some exceptions."""

        loop: asyncio.AbstractEventLoop = get_asyncio_loop()
        if self.socket is None:
            return DeviceTcpReturn.SOCKET_ERROR
        try:
            task_log_debug("Read TCP socket to device.")
            # data_ref.ref = await loop.sock_recv(self.socket, 4096)
            data_ref.ref = await loop.run_in_executor(
                None, self.socket.recv, 4096
            )
            if len(data_ref.ref) == 0:
                task_log("TCP connection ended unexpectedly!", LOGGER.error)
                return DeviceTcpReturn.TCP_SOCKET_CLOSED_UNEXPECTEDLY
        except socket.timeout:
            task_log("socket.timeout.")
        except socket.error:
            task_log_trace_ex()
            return DeviceTcpReturn.SOCKET_ERROR
        except Exception as ex:
            task_log_trace_ex()
            return DeviceTcpReturn.SOCKET_ERROR

        return DeviceTcpReturn.NO_ERROR

    async def encrypt_and_send_msg(self, msg: str, device: Device) -> bool:
        """Encrypt the msg with aes and send it over the socket."""

        info_str: str = (
            (f"{task_name()} - " if LOGGER.level == logging.DEBUG else "")
            + 'Sending in local network to "'
            + device.get_name()
            + '": '
            + json.dumps(json.loads(msg), sort_keys=True, indent=4)
        )

        LOGGER.info(info_str)
        plain: bytes = msg.encode("utf-8")

        package: bytes = DataPackage.create(plain, PackageType.ENC).serialize(
            self.sending_aes
        )
        return await self.send_msg(package)

    async def send_msg(self, data: bytes) -> bool:
        """Send data to socket."""

        loop: asyncio.AbstractEventLoop = get_asyncio_loop()
        send_started = datetime.now()
        max_timeout = timedelta(seconds=MAX_SOCKET_SEND_TIMEOUT_SECS)
        while self.socket:
            try:
                await loop.run_in_executor(None, self.socket.send, data)
                return True
            except socket.timeout:
                task_log_debug("Send timed out, retrying...")
                if datetime.now() - send_started > max_timeout:
                    return False
                await asyncio.sleep(0.1)

        return False
