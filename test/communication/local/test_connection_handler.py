from __future__ import annotations

import asyncio
import socket
from test.communication.local import DATA_IDENTITY, TEST_IP
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
from klyqa_ctl.general.message import Message, MessageState

try:
    from Cryptodome.Random import get_random_bytes  # pycryptodome
except ImportError:
    from Crypto.Random import get_random_bytes  # pycryptodome

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
except ImportError:
    from Crypto.Cipher import AES  # provided by pycryptodome


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
