from __future__ import annotations

import asyncio
import json
from typing import Any

from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.general.general import Command
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId


class LocalController:
    def __init__(
        self,
        local_communicator: LocalConnectionHandler,
        controller_data: ControllerData,
    ) -> None:
        self.connection_hdl: LocalConnectionHandler = local_communicator
        self.controller_data: ControllerData = controller_data

    async def sendToDevice(
        self, unit_id: UnitId, key: str, command: str
    ) -> str:

        self.controller_data.aes_keys[str(unit_id)] = bytes.fromhex(key)

        response_event: asyncio.Event = asyncio.Event()
        msg_answer: str = ""

        async def answer(
            msg: Message | None = None, unit_id: str = ""
        ) -> None:
            nonlocal msg_answer
            if msg is not None:
                msg_answer = msg.answer_utf8
            response_event.set()

        await self.connection_hdl.add_message(
            send_msgs=[Command(_json=json.loads(command))],
            target_device_uid=unit_id,
            callback=answer,
            time_to_live_secs=11111,  # DEFAULT_SEND_TIMEOUT_MS
        )

        await response_event.wait()

        return msg_answer

    async def sendToDeviceNative(
        self, unit_id: UnitId, key: str, command: Command
    ) -> str:

        self.connection_hdl.controller_data.aes_keys[
            str(unit_id)
        ] = bytes.fromhex(key)

        response_event: asyncio.Event = asyncio.Event()
        msg_answer: str = ""

        async def answer(
            msg: Message | None = None, unit_id: str = ""
        ) -> None:
            nonlocal msg_answer
            if msg is not None:
                msg_answer = msg.answer_utf8
            response_event.set()

        await self.connection_hdl.add_message(
            send_msgs=[command],
            target_device_uid=unit_id,
            callback=answer,
            time_to_live_secs=11111,
        )

        await response_event.wait()

        return msg_answer

    async def shutdown(self) -> None:
        await self.connection_hdl.shutdown()

    @classmethod
    async def create_local_only(
        cls: Any,
        server_ip: str = "0.0.0.0",
        network_interface: str | None = None,
        interactive_prompts: bool = False,
    ) -> LocalController:
        """Factory for local only controller.

        param:
            network_interface: leave it on None if you are unsure, else e. g.
                eth0, wlan0, etc.
        """
        controller_data: ControllerData = await ControllerData.create_default(
            interactive_prompts=False, offline=True
        )
        lc_hdl: LocalConnectionHandler = (
            await LocalConnectionHandler.create_default(
                controller_data,
                server_ip=server_ip,
                network_interface=network_interface,
            )
        )

        lc: LocalController = cls(lc_hdl, controller_data)

        return lc
