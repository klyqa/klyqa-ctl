from __future__ import annotations

import socket
from test.conftest import TEST_UNIT_ID

import mock
import pytest

from klyqa_ctl.communication.local.connection import (
    DeviceTcpReturn,
    TcpConnection,
)
from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.communication.local.data_package import DataPackage
from klyqa_ctl.devices.commands import PingCommand
from klyqa_ctl.general.general import TRACE, get_asyncio_loop, set_debug_logger
from klyqa_ctl.general.message import Message
from klyqa_ctl.local_controller import LocalController


@pytest.fixture
def tcp_con(lc_con_hdl: LocalConnectionHandler) -> TcpConnection:
    """Create example tcp connection."""

    con: TcpConnection = TcpConnection()

    return con


@pytest.fixture
def data_pkg(tcp_con: TcpConnection) -> DataPackage:
    """Get example identity data package from device."""

    tcp_con.data = b'\x00\xda\x00\x00{"type":"ident","ident":{"fw_version":"virtual","fw_build":"1","hw_version":"1","manufacturer_id":"59a58a9f-59ca-4c46-96fc-791a79839bc7","product_id":"@qcx.lighting.rgb-cw-ww.virtual","unit_id":"29daa5a4439969f57934"}}'

    package: DataPackage = DataPackage.deserialize(tcp_con.data)
    assert package.length > 0, "Package error no length"

    return package


@pytest.fixture
def msg() -> Message:
    """Get message for local message queue."""
    return Message([PingCommand()], _attr_target_uid=TEST_UNIT_ID)


def test_process_identity_package(
    lc_con_hdl: LocalConnectionHandler,
    tcp_con: TcpConnection,
    data_pkg: DataPackage,
    msg: Message,
) -> None:
    """The identity package processing in local tcp communication."""

    set_debug_logger(level=TRACE)

    ret: DeviceTcpReturn = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_device_identity_package(tcp_con, data_pkg.data)
    )

    assert (
        ret == DeviceTcpReturn.NO_MESSAGE_TO_SEND
    ), f"Uncorrect return error {ret}"

    lc_con_hdl.broadcast_discovery = False
    get_asyncio_loop().run_until_complete(lc_con_hdl.add_message(msg))

    with mock.patch("socket.socket"):
        get_asyncio_loop().run_until_complete(lc_con_hdl.bind_ports())
        tcp_con.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_device_identity_package(tcp_con, data_pkg.data)
    )

    assert ret == DeviceTcpReturn.NO_ERROR, f"Uncorrect return error {ret}"
    assert tcp_con.device, "No device set"
    assert tcp_con.device.u_id, "No device uid set"
    assert tcp_con.msg, "No message for sending selected"
    tcp_con.socket.send.assert_called_once()
