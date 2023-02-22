from __future__ import annotations

import socket
from test.conftest import TEST_AES_KEY, TEST_UNIT_ID

import mock
import pytest

from klyqa_ctl.communication.local.connection import (
    AesConnectionState,
    DeviceTcpReturn,
    TcpConnection,
)
from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.communication.local.data_package import DataPackage
from klyqa_ctl.devices.commands import PingCommand
from klyqa_ctl.devices.device import Device
from klyqa_ctl.general.general import TRACE, get_asyncio_loop, set_debug_logger
from klyqa_ctl.general.message import Message
from klyqa_ctl.local_controller import LocalController

try:
    from Cryptodome.Random import get_random_bytes  # pycryptodome
except ImportError:
    from Crypto.Random import get_random_bytes  # pycryptodome

TEST_IP: str = "192.168.8.4"


@pytest.fixture
def tcp_con(lc_con_hdl: LocalConnectionHandler) -> TcpConnection:
    """Create example tcp connection."""

    con: TcpConnection = TcpConnection()
    con.address.ip = TEST_IP

    with mock.patch("socket.socket"):
        con.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    return con


@pytest.fixture
def data_pkg_iv(tcp_con: TcpConnection) -> bytes:
    """Get example identity data package from device."""
    return get_random_bytes(8)


@pytest.fixture
def data_pkg_identity(tcp_con: TcpConnection) -> DataPackage:
    """Get example identity data package from device."""

    tcp_con.data = b'\x00\xda\x00\x00{"type":"ident","ident":{"fw_version":"virtual","fw_build":"1","hw_version":"1","manufacturer_id":"59a58a9f-59ca-4c46-96fc-791a79839bc7","product_id":"@qcx.lighting.rgb-cw-ww.virtual","unit_id":"29daa5a4439969f57934"}}'

    package: DataPackage = DataPackage.deserialize(tcp_con.data)
    assert package.length > 0, "Package error no length"

    return package


@pytest.fixture
def msg_with_target_uid() -> Message:
    """Get message for local message queue."""
    return Message([PingCommand()], _attr_target_uid=TEST_UNIT_ID)


@pytest.fixture
def msg_with_target_ip() -> Message:
    """Get message for local message queue."""
    return Message([PingCommand()], target_ip=TEST_IP)


def test_process_identity_package(
    lc_con_hdl: LocalConnectionHandler,
    tcp_con: TcpConnection,
    data_pkg_identity: DataPackage,
    msg_with_target_uid: Message,
) -> None:
    """Test the identity package processing in local tcp communication.
    Look that the initial vector is sent as well."""

    set_debug_logger(level=TRACE)

    ret: DeviceTcpReturn = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_device_identity_package(
            tcp_con, data_pkg_identity.data
        )
    )

    assert (
        ret == DeviceTcpReturn.NO_MESSAGE_TO_SEND
    ), f"Uncorrect return error {ret}"

    lc_con_hdl.broadcast_discovery = False
    get_asyncio_loop().run_until_complete(
        lc_con_hdl.add_message(msg_with_target_uid)
    )

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_device_identity_package(
            tcp_con, data_pkg_identity.data
        )
    )

    assert ret == DeviceTcpReturn.NO_ERROR, f"Uncorrect return error {ret}"
    assert tcp_con.device, "No device set"
    assert tcp_con.device.u_id, "No device uid set"
    assert tcp_con.msg, "No message for sending selected"
    tcp_con.socket.send.assert_called_once()


# @pytest.mark.dependency(depends=["test_process_identity_package"])
# def test_process_iv_package_dependent(
#     lc_con_hdl: LocalConnectionHandler,
#     tcp_con: TcpConnection,
#     data_pkg_iv: bytes,
#     msg: Message,
# ) -> None:
#     obj = test_process_identity_package
#     ret: DeviceTcpReturn = get_asyncio_loop().run_until_complete(
#         lc_con_hdl.process_aes_initial_vector_package(tcp_con, data_pkg_iv)
#     )
#     pass


def test_process_iv_package_standalone(
    lc_con_hdl: LocalConnectionHandler,
    tcp_con: TcpConnection,
    data_pkg_iv: bytes,
    msg_with_target_uid: Message,
) -> None:
    """Testing processing AES initial vector package."""

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR
    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_aes_initial_vector_package(tcp_con, data_pkg_iv)
    )
    assert (
        ret == DeviceTcpReturn.MISSING_AES_KEY
    ), f"Uncorrect return error for missing aes key {ret}"

    tcp_con.device.u_id = TEST_UNIT_ID
    tcp_con.aes_key = lc_con_hdl.controller_data.aes_keys[TEST_UNIT_ID]

    wrong_iv: bytes = b"2d2ad3"

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_aes_initial_vector_package(tcp_con, wrong_iv)
    )
    assert (
        ret == DeviceTcpReturn.WRONG_AES
    ), f"Uncorrect return error for iv for aes key {ret}"

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_aes_initial_vector_package(tcp_con, data_pkg_iv)
    )
    assert ret == DeviceTcpReturn.NO_ERROR, f"Uncorrect return error {ret}"
    assert (
        tcp_con.state == AesConnectionState.CONNECTED
    ), "Connection is not in connected state"
    assert tcp_con.sending_aes != None, "Missing sending AES object!"
    assert tcp_con.receiving_aes != None, "Missing receiving AES object!"


def test_handle_send_msg_no_msg(
    lc_con_hdl: LocalConnectionHandler,
    tcp_con: TcpConnection,
    msg_with_target_uid: Message,
) -> None:
    """Test handle send message no message to send"""

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.handle_send_msg(tcp_con)
    )
    assert (
        ret == DeviceTcpReturn.NO_MESSAGE_TO_SEND
    ), f"Uncorrect return error for missing aes key {ret}"


def test_handle_send_msg_target_unit_id(
    lc_con_hdl: LocalConnectionHandler,
    tcp_con: TcpConnection,
    msg_with_target_uid: Message,
) -> None:
    """Test handle send message with target unit ID"""

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

    # Message with target Unit ID
    get_asyncio_loop().run_until_complete(
        lc_con_hdl.add_message(msg_with_target_uid)
    )
    tcp_con.device.u_id = TEST_UNIT_ID

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.handle_send_msg(tcp_con)
    )
    assert (
        ret == DeviceTcpReturn.NO_ERROR
    ), f"Uncorrect return error for missing aes key {ret}"

    assert (
        TEST_UNIT_ID not in lc_con_hdl.message_queue
    ), f"Message queue for {TEST_UNIT_ID} should be empty!"

    tcp_con.socket.send.assert_called_once()


def test_handle_send_msg_target_ip(
    lc_con_hdl: LocalConnectionHandler,
    tcp_con: TcpConnection,
    msg_with_target_ip: Message,
) -> None:
    """Test handle send message with target IP"""

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

    get_asyncio_loop().run_until_complete(
        lc_con_hdl.add_message(msg_with_target_ip)
    )

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.handle_send_msg(tcp_con)
    )
    assert (
        ret == DeviceTcpReturn.NO_ERROR
    ), f"Uncorrect return error for missing aes key {ret}"

    assert (
        TEST_IP not in lc_con_hdl.message_queue
    ), f"Message queue for {TEST_IP} should be empty!"

    tcp_con.socket.send.assert_called_once()
