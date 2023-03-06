from __future__ import annotations

import asyncio
from datetime import time
import json
from test.communication.local import (
    TEST_IP,
    UDPSocketRecvSynDeviceBootupMock,
    tcp_connection_mock,
)
from test.conftest import TEST_PRODUCT_ID, TEST_UNIT_ID
from typing import Any

import mock
import pytest

from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.devices.commands import PingCommand
from klyqa_ctl.devices.device import Device
from klyqa_ctl.general.general import TRACE, get_asyncio_loop, set_debug_logger
from klyqa_ctl.general.message import Message, MessageState


@pytest.fixture
def ping_msg_that_hit_ttl() -> Message:
    """Get message for local message queue that should hit ttl."""

    async def test_cb(*_: Any) -> None:
        print("Message callback called.")

    return Message(
        [PingCommand()],
        target_ip=TEST_IP,
        time_to_live_secs=1,
        callback=test_cb,
    )


def test_check_messages_time_to_live_hit(
    lc_con_hdl: LocalConnectionHandler,
    ping_msg_that_hit_ttl: Message,
) -> None:
    """Test time to live for message when timelimit hit."""

    set_debug_logger(level=TRACE)

    get_asyncio_loop().run_until_complete(
        lc_con_hdl.add_message(ping_msg_that_hit_ttl)
    )

    lc_con_hdl.check_messages_ttl_task_alive()

    get_asyncio_loop().run_until_complete(asyncio.sleep(2))

    assert len(lc_con_hdl.message_queue[TEST_IP]) == 0
    assert ping_msg_that_hit_ttl.cb_called
    assert ping_msg_that_hit_ttl.state == MessageState.UNSENT


def test_read_udp_socket_task(lc_con_hdl: LocalConnectionHandler) -> None:
    """Test udp syns received on boot up device"""

    set_debug_logger(level=TRACE)

    lc_con_hdl.udp.recvfrom = UDPSocketRecvSynDeviceBootupMock()
    lc_con_hdl.udp.sendto = mock.MagicMock()

    # disable the search and send loop task for receiving
    # the open tcp port connection to device after the ack.
    lc_con_hdl.search_and_send_loop_task_alive = mock.MagicMock()

    # mock send_msg as well now, for sending the ack
    lc_con_hdl.send_msg = mock.AsyncMock()

    lc_con_hdl.read_udp_socket_task()
    get_asyncio_loop().run_until_complete(asyncio.sleep(14))

    lc_con_hdl.udp.sendto.assert_called()
    lc_con_hdl.send_msg.assert_called()


def test_status_update_callback_on_device_power_on(
    lc_con_hdl: LocalConnectionHandler,
    tcp_connection_mock: TcpConnection,
) -> None:
    """Test status update callback that is called when a device
    get's powered on."""

    set_debug_logger(level=TRACE)

    get_asyncio_loop().run_until_complete(
        lc_con_hdl.controller_data.get_or_create_device(
            TEST_UNIT_ID, TEST_PRODUCT_ID
        )
    )
    status_updated: bool = False

    def status_update_cb() -> None:
        nonlocal status_updated
        print("status updated.")
        status_updated = True

    dev: Device | None = lc_con_hdl.controller_data.devices.get(TEST_UNIT_ID)

    assert dev is not None
    if dev:
        dev.add_status_update_cb(status_update_cb)

    lc_con_hdl.udp.recvfrom = UDPSocketRecvSynDeviceBootupMock()
    lc_con_hdl.udp.sendto = mock.MagicMock()

    lc_con_hdl.read_udp_socket_task()

    tcp_connection_mock.device = dev

    json_response: str = '{"type": "status", "brightness": {"percentage":88}}'
    tcp_connection_mock.device.save_device_message(json.loads(json_response))
    assert status_updated

    status_updated = False
    json_response = '{"type": "status", "temperature": 4488}'
    tcp_connection_mock.device.save_device_message(json.loads(json_response))
    assert status_updated
