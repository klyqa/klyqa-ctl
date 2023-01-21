from __future__ import annotations
import asyncio
import json
from typing import Any
from klyqa_ctl.communication.local.communicator import LocalCommunicator
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.general.general import Command
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId
 
class LocalController:
    
    def __init__(self, local_communicator: LocalCommunicator, controller_data: ControllerData) -> None:
        self.local_communicator: LocalCommunicator = local_communicator
        self.controller_data: ControllerData = controller_data
        
    async def sendToDevice(self, unit_id: UnitId, key: str, command: str) -> str:

        self.controller_data.aes_keys[str(unit_id)] = bytes.fromhex(key)
        
        response_event: asyncio.Event = asyncio.Event()
        msg_answer: str = ""
    
        async def answer(msg: Message | None = None, unit_id: str = "") -> None:
            nonlocal msg_answer
            if msg is not None:
                msg_answer = msg.answer_utf8
            response_event.set()
        
        await self.local_communicator.set_send_message(
            send_msgs = [Command(_json=json.loads(command))],
            target_device_uid = unit_id,
            callback = answer,
            time_to_live_secs = 11111
        )

        await response_event.wait()

        return msg_answer
        
    async def sendToDeviceNative(self, unit_id: UnitId, key: str, command: Command) -> str:

        self.local_communicator.controller_data.aes_keys[str(unit_id)] = bytes.fromhex(key)
        
        response_event: asyncio.Event = asyncio.Event()
        msg_answer: str = ""
    
        async def answer(msg: Message | None = None, unit_id: str = "") -> None:
            nonlocal msg_answer
            if msg is not None:
                msg_answer = msg.answer_utf8
            response_event.set()
        
        await self.local_communicator.set_send_message(
            send_msgs = [command],
            target_device_uid = unit_id,
            callback = answer,
            time_to_live_secs = 11111
        )

        await response_event.wait()

        return msg_answer
        
    async def shutdown(self) -> None:
        await self.local_communicator.shutdown()
        
    @classmethod
    async def create_local_only(
        cls: Any, interactive_prompts: bool = False
    ) -> LocalController:
        """Factory for local only controller."""
        controller_data: ControllerData = ControllerData(interactive_prompts = interactive_prompts, offline = True)
        await controller_data.init()
        lcc: LocalCommunicator = LocalCommunicator(
            controller_data, None, server_ip = "0.0.0.0")
        
        # lc: LocalController = LocalController(lcc)
        # lc: LocalController = LocalController(lcc)
        lc: LocalController  = cls(lcc, controller_data)
   
        # if cls._instance is None:
        #     LOGGER.debug("Creating new AsyncIOLock instance")
        #     cls._instance = cls.__new__(cls)
        #     # Put any initialization here.
        #     cls._instance.__init__()
        # return self
        return lc