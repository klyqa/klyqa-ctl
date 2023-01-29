"""Message class"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from enum import Enum
from typing import Awaitable, Callable

from klyqa_ctl.general.general import (
    LOGGER,
    Command,
    TypeJson,
    format_uid,
    task_log_debug,
)
from klyqa_ctl.general.unit_id import UnitId


class MessageState(Enum):
    SENT = 0
    ANSWERED = 1
    UNSENT = 2


MSG_COUNTER = 0


@dataclass
class Message:
    """Message"""

    started: datetime.datetime
    _attr_target_uid: str
    msg_queue: list[Command]
    msg_queue_sent: list[str] = field(default_factory=lambda: [])
    state: MessageState = MessageState.UNSENT
    exception: Exception | None = None
    answered_datetime: datetime.datetime | None = None
    local_pause_after_answer_secs: float | None = None
    answer: bytes = b""
    answer_utf8: str = ""
    answer_json: TypeJson = field(default_factory=lambda: {})
    # callback on error event or answer
    callback: Callable[[Message | None, str], Awaitable] | None = None
    cb_called: bool = False
    time_to_live_secs: float = -1
    msg_counter: int = -1
    send_try: int = 0
    aes_key: bytes | None = None

    def __post_init__(self) -> None:
        global MSG_COUNTER
        self.msg_counter = MSG_COUNTER
        MSG_COUNTER = MSG_COUNTER + 1

    async def call_cb(self) -> None:
        if self.callback is not None and not self.cb_called:
            await self.callback(self, self.target_uid)
            self.cb_called = True

    async def check_msg_ttl(self) -> bool:
        """Verify time to live, if exceeded call the callback"""
        if datetime.datetime.now() - self.started > datetime.timedelta(
            seconds=self.time_to_live_secs
        ):
            task_log_debug(
                f"time to live {self.time_to_live_secs} seconds for message"
                f" {self.msg_counter} {self.msg_queue} ended."
            )
            if self.callback:
                await self.call_cb()
            return False
        return True

    @property
    def target_uid(self) -> str:
        return self._attr_target_uid

    @target_uid.setter
    def target_uid(self, target_uid: str) -> None:
        self._attr_target_uid = format_uid(target_uid)


@dataclass
class BroadCastMessage(Message):
    sent_to_uids: set[str] = field(default_factory=lambda: set())


# @dataclass
# class DiscoverMessage(Message):
#     discovered_uids: set[str] = set()
