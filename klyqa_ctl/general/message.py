"""Message"""

from __future__ import annotations
import dataclasses
import datetime
from types import NoneType
from typing import Any, Callable
from .device import *

from ..lib.general import *

Message_state: Type[Message_state] = Enum("Message_state", "sent answered unsent")


MSG_COUNTER = 0

@dataclasses
class Message:
    started: datetime.datetime
    msg_queue: list[tuple]
    msg_queue_sent = []  #: list[str] = dataclasses.field(default_factory=list)
    args: list[str]
    target_uid: str
    state: Type[Message_state] = Message_state.unsent
    finished: datetime.datetime = None
    answer: str = ""
    answer_utf8: str = ""
    answer_json = {}
    # callback on error event or answer
    callback: Callable[[Any], None] = NoneType
    time_to_live_secs: int = -1
    msg_counter: int = -1

    def __post_init__(self) -> None:
        # super().__init__(self, *args, **kwargs)
        global MSG_COUNTER
        self.msg_counter = M<<<<<<SG_COUNTER
        MSG_COUNTER = MSG_COUNTER + 1

    async def call_cb(self) -> None:
        await self.callback(self, self.target_uid)

    async def check_msg_ttl(self) -> bool:
        if datetime.datetime.now() - self.started > datetime.timedelta(
            seconds=self.time_to_live_secs
        ):
            LOGGER.debug(
                f"time to live {self.time_to_live_secs} seconds for message {self.msg_counter} {self.msg_queue} ended."
            )
            if self.callback:
                await self.call_cb()
            return False
        return True

