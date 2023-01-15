"""Message"""

from __future__ import annotations
import argparse
from dataclasses import dataclass

import datetime
from enum import Enum
from typing import Any

from klyqa_ctl.general import *
from klyqa_ctl.general.general import LOGGER

class MessageState(Enum):
    SENT = 0
    ANSWERED = 1
    UNSENT = 2

MSG_COUNTER = 0

@dataclass
class Message:
    """Message"""

    started: datetime.datetime
    msg_queue: list[tuple]
    msg_queue_sent = []  #: list[str] = dataclasses.field(default_factory=list)
    args: argparse.Namespace
    target_uid: str
    state: MessageState = MessageState.UNSENT
    answered_datetime: datetime.datetime | None = None
    local_pause_after_answer_secs: float | None = None
    answer: bytes = b""
    answer_utf8: str = ""
    answer_json = {}
    # callback on error event or answer
    callback: Any | None = None
    time_to_live_secs: float = -1
    msg_counter: int = -1
    send_try: int = 0

    def __post_init__(self) -> None:
        global MSG_COUNTER
        self.msg_counter = MSG_COUNTER
        MSG_COUNTER = MSG_COUNTER + 1

    async def call_cb(self) -> None:
        if not self.callback is None:
            await self.callback(self, self.target_uid)

    async def check_msg_ttl(self) -> bool:
        """Verify time to live, if exceeded call the callback"""
        if datetime.datetime.now() - self.started > datetime.timedelta(
            seconds = self.time_to_live_secs
        ):
            LOGGER.debug(
                f"time to live {self.time_to_live_secs} seconds for message {self.msg_counter} {self.msg_queue} ended."
            )
            if self.callback:
                await self.call_cb()
            return False
        return True
