from __future__ import annotations

import asyncio
import socket
from test.conftest import TEST_UNIT_ID
import time
from typing import Any

import mock
import pytest

from klyqa_ctl.communication.local.connection import TcpConnection
from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.communication.local.data_package import DataPackage, PackageType
from klyqa_ctl.general.general import QCX_SYN

try:
    from Cryptodome.Random import get_random_bytes  # pycryptodome
except ImportError:
    from Crypto.Random import get_random_bytes  # pycryptodome

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
except ImportError:
    from Crypto.Cipher import AES  # provided by pycryptodome


TEST_IP: str = "192.168.8.4"

TEST_PORT: int = 50222

DATA_IDENTITY: bytes = (
    b'\x00\xda\x00\x00{"type":"ident","ident":{"fw_version":"virtual","fw_build":"1","hw_version":"1","manufacturer_id":"59a58a9f-59ca-4c46-96fc-791a79839bc7","product_id":"@qcx.lighting.rgb-cw-ww.virtual","unit_id":"'
    + TEST_UNIT_ID.encode("utf-8")
    + b'"}}'
)


class UDPSynSocketRecvMock(mock.MagicMock):  # type: ignore[misc]
    """Mock the receive method of the UDP socket"""

    def __call__(self, *args: Any, **kwargs: Any) -> tuple:
        """Call mocked SYN send from device with 1 sec delay."""

        ret_val: bytes = b"NO_SYN"

        if self.call_count > 0:
            time.sleep(1.0)

        if self.call_count < 10:
            # mock 10 syns
            ret_val = QCX_SYN

        super().__call__(self, *args, **kwargs)
        self._mock_call(*args, **kwargs)

        return (ret_val, (TEST_IP, TEST_PORT))


@pytest.fixture
def tcp_con(lc_con_hdl: LocalConnectionHandler) -> TcpConnection:
    """Create example tcp connection."""

    con: TcpConnection = TcpConnection()
    con.address.ip = TEST_IP

    with mock.patch("socket.socket"):
        con.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    return con


class SocketRecvTCPMock(mock.MagicMock):  # type: ignore[misc]
    """Mock the receive method of the TCP socket"""

    remote_iv: bytes = get_random_bytes(8)
    tcp_con: TcpConnection | None = None
    msg: str = ""

    def __call__(self, *args: Any, **kwargs: Any) -> bytes:
        """Call the mocked function"""

        ret_val: bytes = b""

        if self.call_count == 0:
            ret_val = DATA_IDENTITY

        elif self.call_count == 1:
            ret_val = DataPackage.create(
                self.remote_iv, PackageType.IV
            ).serialize()

        elif self.call_count == 2 and self.tcp_con:
            plain: bytes = self.msg.encode("utf-8")

            _mock_sender_aes = AES.new(
                self.tcp_con.aes_key,
                AES.MODE_CBC,
                iv=self.tcp_con.remote_iv + self.tcp_con.local_iv,
            )

            ser_enc_data: bytes = DataPackage.create(
                plain, PackageType.ENC
            ).serialize(_mock_sender_aes)
            ret_val = ser_enc_data

        super().__call__(self, *args, **kwargs)
        self._mock_call(*args, **kwargs)

        return ret_val
