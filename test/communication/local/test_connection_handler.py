from __future__ import annotations

import asyncio
from test.communication.local import TEST_IP, UDPSynSocketRecvMock
from typing import Any

import mock
import pytest

from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.devices.commands import PingCommand
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
    """Test time to live for message when hit limit."""

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

    with mock.patch("socket.socket"):
        lc_con_hdl.udp.recvfrom = UDPSynSocketRecvMock()
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
