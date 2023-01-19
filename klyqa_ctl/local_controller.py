


from __future__ import annotations
import asyncio
import json
from klyqa_ctl.communication.local.communicator import LocalCommunicator
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.general.general import LOGGER, TRACE, logging_hdl
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId


# class ErrorCode(Enum):
#     NO_ERROR = auto()
    
    
class LocalController:
    
    def __init__(self) -> None:
        self.local_communicator: LocalCommunicator = LocalCommunicator(
            ControllerData(False, offline=True), None, server_ip="0.0.0.0")
        
    
    async def sendToDevice(self, unit_id: UnitId, key: str, command: str) -> str:

        self.local_communicator.controller_data.aes_keys[str(unit_id)] = bytes.fromhex(key)
        
        response_event: asyncio.Event = asyncio.Event()
        msg_answer: str = ""
        
        async def answer(msg: Message | None = None, unit_id: str = "") -> None:
            nonlocal msg_answer
            if msg is not None:
                msg_answer = msg.answer_utf8
            response_event.set()
        
        await self.local_communicator.set_send_message(
            send_msgs=[(command, 0)],
            target_device_uid=unit_id,
            callback=answer,
            time_to_live_secs = 30000
        )

        await response_event.wait()

        return msg_answer
        

async def main() -> None:
    
    lc: LocalController = LocalController()

    LOGGER.setLevel(TRACE)
    logging_hdl.setLevel(TRACE)
    
    # response: str = await lc.sendToDevice(UnitId("286DCD5C6BDA"), "0c2ff6f6aa0ede2c454ca712ecfa1dfd",
    #                       '{"type": "request"}')
    unit_id: UnitId = UnitId("")
    aes_key: str = ""
    response: str = await lc.sendToDevice(unit_id, aes_key,
                          '{"type": "request"}')
    print(response)
    
if __name__ == "__main__":
    asyncio.run(main())
        