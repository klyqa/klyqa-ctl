from __future__ import annotations

import asyncio
import atexit
import datetime
from itertools import product
import json
import os
import time
from typing import Generator

import pytest

from klyqa_ctl.general.general import (
    TRACE,
    Command,
    TypeJson,
    set_debug_logger,
)
from klyqa_ctl.general.message import Message  # AES_KEY_DEV,
from klyqa_ctl.local_controller import LocalController

SUT_UNIT_ID: str = "00ac629de9ad2f4409dc"
SUT_DEVICE_KEY: str = "e901f036a5a119a91ca1f30ef5c207d6"


def test_message_start_times() -> None:

    msg1: Message = Message(
        [Command(_json={"type": "test"})],
        "no_uid",
    )
    time.sleep(1)

    msg2: Message = Message(
        [Command(_json={"type": "test"})],
        "no_uid",
    )

    assert (msg2.started - msg1.started) != datetime.timedelta(
        seconds=0
    ), "Expected different start times for messages."
