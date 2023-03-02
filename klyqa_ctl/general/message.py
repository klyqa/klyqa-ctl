"""Message class"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from enum import Enum, auto
from typing import Awaitable, Callable, Set

from klyqa_ctl.general.general import (
    DEFAULT_SEND_TIMEOUT_MS,
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
    VALUE_RANGE_LIMITS = 3
    SELECTED = auto()


MSG_COUNTER = 0


@dataclass
class Message:
    """Message"""

    msg_queue: list[Command]
    _attr_target_uid: str = ""
    target_ip: str = ""
    msg_queue_sent: list[str] = field(default_factory=lambda: [])
    started: datetime.datetime = datetime.datetime.now()
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
    time_to_live_secs: float = DEFAULT_SEND_TIMEOUT_MS
    msg_counter: int = -1
    send_try: int = 0
    aes_key: bytes | None = None
    broadcast_syn: bool = False

    def __post_init__(self) -> None:
        global MSG_COUNTER
        self.msg_counter = MSG_COUNTER
        MSG_COUNTER = MSG_COUNTER + 1
        self.started = datetime.datetime.now()

    async def call_cb(self, uid_answered: str = "") -> None:
        if self.callback is not None and not self.cb_called:
            await self.callback(self, uid_answered)
            self.cb_called = True

    def is_ttl_end(self) -> bool:
        """Check time to live ended."""

        return datetime.datetime.now() - self.started > datetime.timedelta(
            seconds=self.time_to_live_secs
        )

    async def check_msg_ttl_cb(self) -> bool:
        """Verify time to live, if exceeded call the callback"""

        if self.is_ttl_end():
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
class BroadcastMessage(Message):
    """Broadcast message to all devices.
    Callback on reply can be called multiple times.
    Devices that answered to that message will be remember in sent_to and
    not send to them again."""

    sent_to: Set[str] = field(default_factory=set)

    async def call_cb(self, uid_answered: str = "") -> None:
        if self.callback is not None:
            await self.callback(self, uid_answered)
            self.cb_called = True
