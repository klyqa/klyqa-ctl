from __future__ import annotations

import socket
from test.communication.local import (
    DATA_IDENTITY,
    TEST_IP,
    TCPDeviceConnectionMock,
    tcp_connection_mock,
)
from test.conftest import TEST_UNIT_ID
import time
from typing import Any

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
from klyqa_ctl.communication.local.data_package import DataPackage, PackageType
from klyqa_ctl.devices.commands import PingCommand
from klyqa_ctl.general.general import (
    LOGGER_DBG,
    TRACE,
    get_asyncio_loop,
    set_debug_logger,
)
from klyqa_ctl.general.message import Message

try:
    from Cryptodome.Random import get_random_bytes  # pycryptodome
except ImportError:
    from Crypto.Random import get_random_bytes  # pycryptodome

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
except ImportError:
    from Crypto.Cipher import AES  # provided by pycryptodome


@pytest.fixture
def data_pkg_iv(tcp_connection_mock: TcpConnection) -> bytes:
    """Get example identity data package from device."""
    return get_random_bytes(8)


@pytest.fixture
def pkg_identity() -> DataPackage:
    """Get example identity data package from device."""

    package: DataPackage = DataPackage.deserialize(DATA_IDENTITY)
    assert package.length > 0, "Package error no length"

    return package


@pytest.fixture
def msg_with_target_uid() -> Message:
    """Get message for local message queue."""
    return Message([PingCommand()], _attr_target_uid=TEST_UNIT_ID)


@pytest.fixture
def ping_msg_with_target_ip() -> Message:
    """Get message for local message queue."""
    return Message([PingCommand()], target_ip=TEST_IP)


def test_process_identity_package(
    lc_con_hdl: LocalConnectionHandler,
    tcp_connection_mock: TcpConnection,
    pkg_identity: DataPackage,
    msg_with_target_uid: Message,
) -> None:
    """Test the identity package processing in local tcp communication.
    Look that the initial vector is sent as well."""

    set_debug_logger(level=TRACE)
    LOGGER_DBG.propagate = False
    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_device_identity_package(
            tcp_connection_mock, pkg_identity.data
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
            tcp_connection_mock, pkg_identity.data
        )
    )

    assert ret == DeviceTcpReturn.NO_ERROR, f"Uncorrect return error {ret}"
    assert tcp_connection_mock.device, "No device set"
    assert tcp_connection_mock.device.u_id, "No device uid set"
    assert tcp_connection_mock.msg, "No message for sending selected"
    tcp_connection_mock.socket.send.assert_called_once()


def test_process_iv_package_standalone(
    lc_con_hdl: LocalConnectionHandler,
    tcp_connection_mock: TcpConnection,
    data_pkg_iv: bytes,
    msg_with_target_uid: Message,
) -> None:
    """Testing processing AES initial vector package."""

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR
    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_aes_initial_vector_package(
            tcp_connection_mock, data_pkg_iv
        )
    )
    assert (
        ret == DeviceTcpReturn.MISSING_AES_KEY
    ), f"Uncorrect return error for missing aes key {ret}"

    tcp_connection_mock.device.u_id = TEST_UNIT_ID
    tcp_connection_mock.aes_key = lc_con_hdl.controller_data.aes_keys[
        TEST_UNIT_ID
    ]

    wrong_iv: bytes = b"2d2ad3"

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_aes_initial_vector_package(
            tcp_connection_mock, wrong_iv
        )
    )
    assert (
        ret == DeviceTcpReturn.WRONG_AES
    ), f"Uncorrect return error for iv for aes key {ret}"

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_aes_initial_vector_package(
            tcp_connection_mock, data_pkg_iv
        )
    )
    assert ret == DeviceTcpReturn.NO_ERROR, f"Uncorrect return error {ret}"
    assert (
        tcp_connection_mock.state == AesConnectionState.CONNECTED
    ), "Connection is not in connected state"
    assert (
        tcp_connection_mock.sending_aes != None
    ), "Missing sending AES object!"
    assert (
        tcp_connection_mock.receiving_aes != None
    ), "Missing receiving AES object!"


def test_handle_send_msg_no_msg(
    lc_con_hdl: LocalConnectionHandler,
    tcp_connection_mock: TcpConnection,
) -> None:
    """Test handle send message with no message to send"""

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.handle_send_msg(tcp_connection_mock)
    )
    assert (
        ret == DeviceTcpReturn.NO_MESSAGE_TO_SEND
    ), f"Uncorrect return error for missing aes key {ret}"


def test_handle_send_msg_target_unit_id(
    lc_con_hdl: LocalConnectionHandler,
    tcp_connection_mock: TcpConnection,
    msg_with_target_uid: Message,
) -> None:
    """Test handle send message with target unit ID"""

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

    # Message with target Unit ID
    get_asyncio_loop().run_until_complete(
        lc_con_hdl.add_message(msg_with_target_uid)
    )
    assert (
        TEST_UNIT_ID in lc_con_hdl.message_queue
    ), f"Message queue for {TEST_UNIT_ID} should be not empty!"
    tcp_connection_mock.device.u_id = TEST_UNIT_ID

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.handle_send_msg(tcp_connection_mock)
    )
    assert (
        ret == DeviceTcpReturn.NO_ERROR
    ), f"Uncorrect return error for missing aes key {ret}"

    assert (
        TEST_UNIT_ID not in lc_con_hdl.message_queue
        or not lc_con_hdl.message_queue[TEST_UNIT_ID]
    ), f"Message queue for {TEST_UNIT_ID} should be empty!"

    tcp_connection_mock.socket.send.assert_called_once()


def test_handle_send_msg_target_ip(
    lc_con_hdl: LocalConnectionHandler,
    tcp_connection_mock: TcpConnection,
    ping_msg_with_target_ip: Message,
) -> None:
    """Test handle send message with target IP"""

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

    get_asyncio_loop().run_until_complete(
        lc_con_hdl.add_message(ping_msg_with_target_ip)
    )

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.handle_send_msg(tcp_connection_mock)
    )
    assert (
        ret == DeviceTcpReturn.NO_ERROR
    ), f"Uncorrect return error for missing aes key {ret}"

    assert (
        TEST_IP not in lc_con_hdl.message_queue
        or not lc_con_hdl.message_queue[TEST_IP]
    ), f"Message queue for {TEST_IP} should be empty!"

    tcp_connection_mock.socket.send.assert_called_once()


def test_process_tcp_package(
    lc_con_hdl: LocalConnectionHandler,
    tcp_connection_mock: TcpConnection,
    ping_msg_with_target_ip: Message,
    pkg_identity: DataPackage,
) -> None:
    """Test process TCP identity package"""

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

    get_asyncio_loop().run_until_complete(
        lc_con_hdl.add_message(ping_msg_with_target_ip)
    )

    tcp_connection_mock.pkg = pkg_identity

    ret = get_asyncio_loop().run_until_complete(
        lc_con_hdl.process_tcp_package(tcp_connection_mock)
    )
    assert (
        ret == DeviceTcpReturn.NO_ERROR
    ), f"Uncorrect return error process package {ret}"

    tcp_connection_mock.socket.send.assert_called_once()


def test_handle_connection(
    lc_con_hdl: LocalConnectionHandler,
    tcp_connection_mock: TcpConnection,
    ping_msg_with_target_ip: Message,
    pkg_identity: DataPackage,
) -> None:
    """Test handle connection"""

    set_debug_logger(level=TRACE)

    ret: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

    get_asyncio_loop().run_until_complete(
        lc_con_hdl.add_message(ping_msg_with_target_ip)
    )

    if tcp_connection_mock.socket:
        tcp_connection_mock.socket.recv = TCPDeviceConnectionMock()
        tcp_connection_mock.socket.recv.tcp_con = tcp_connection_mock
        tcp_connection_mock.socket.recv.msg = (
            '{"type":"pong","ts":"' + str(int(time.time())) + '"}'
        )
        ret = get_asyncio_loop().run_until_complete(
            lc_con_hdl.handle_connection(tcp_connection_mock)
        )
        assert (
            ret == DeviceTcpReturn.ANSWERED
        ), f"Uncorrect return error process package {ret}"
