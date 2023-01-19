


from __future__ import annotations
import asyncio
from klyqa_ctl.communication.local.communicator import LocalCommunicator
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId
 
class LocalController:
    
    def __init__(self) -> None:
        self.local_communicator: LocalCommunicator = LocalCommunicator(
            ControllerData(False, offline = True), None, server_ip = "0.0.0.0")
        
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
            time_to_live_secs = 30
        )

        await response_event.wait()

        return msg_answer
        
    async def shutdown(self) -> None:
        await self.local_communicator.shutdown()
        