


from __future__ import annotations
import asyncio
from enum import Enum, auto
import json
from typing import  Awaitable, Callable
from klyqa_ctl.communication.local.communicator import LocalCommunicator
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.general.general import LOGGER, TRACE, logging_hdl
from klyqa_ctl.general.message import Message


# class ErrorCode(Enum):
#     NO_ERROR = auto()
    
    
class LocalController:
    
    def __init__(self) -> None:
        self.local_communicator: LocalCommunicator = LocalCommunicator(
            ControllerData(False, offline=True), None, server_ip="0.0.0.0")
        
    
    async def sendToDevice(self, unit_id: str, key: str, command: str) -> str:
                           #answer_cb: Callable[[Message | None, str], Awaitable]
                        #    ) -> str: #-> ErrorCode:
        # return_val: ErrorCode = ErrorCode.NO_ERROR
        self.local_communicator.controller_data.aes_keys[unit_id] = key.encode("UTF-8")
        
        response_event: asyncio.Event = asyncio.Event()
        
        msg_answer: str = ""
        
        async def answer(msg: Message | None = None, str2: str = "") -> None:
            nonlocal msg_answer
            # await answer_cb(msg, str2)
            if msg is not None:
                msg_answer = msg.answer_utf8
            response_event.set()
        
        await self.local_communicator.set_send_message(
            send_msgs=[(json.dumps(command), 0)],
            target_device_uid=unit_id,
            callback=answer,
            time_to_live_secs = 30000
        )

        await response_event.wait()
        # return return_val
        return msg_answer
        

async def main() -> None:
    lc: LocalController = LocalController()

    LOGGER.setLevel(TRACE)
    logging_hdl.setLevel(TRACE)
    
    # async def answered(msg: Message | None = None, str2: str = "") -> None:
    #     print("answered")
    
    # callback: Callable[[], Coroutine[Message, str, None]] = test(Message(), "")
    # callback: Callable[[Message | None, str], Awaitable] = test
    # await callback(None, "ok")
    
    # response: str = await lc.sendToDevice("29daa5a4439969f57934", "53b962431abc7af6ef84b43802994424",
    #                       '{"type": "request"}') #, answered)
    response: str = await lc.sendToDevice("", "",
                          '{"type": "request"}') #, answered)
    print(response)
    
if __name__ == "__main__":
    asyncio.run(main())
        