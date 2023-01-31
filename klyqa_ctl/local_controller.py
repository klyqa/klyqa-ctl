"""Local connection controller. Should be merged with local
in connection controller, they are basically the same."""

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
    """Controls local connections via tcp and udp for broadcasts and
    connections directly to devices."""

    def __init__(
        self,
        controller_data: ControllerData,
    ) -> None:
        """Initializes the local controller."""

        self.connection_hdl: LocalConnectionHandler | None = None
        self.controller_data: ControllerData = controller_data

    def send_to_device(self, unit_id: str, key: str, command: str) -> str:
        """Sends command string to device with unit id and aes key."""

        if not self.connection_hdl:
            return ""

        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        result: str = loop.run_until_complete(
            self.send_to_device_native(
                UnitId(unit_id), key, Command(_json=json.loads(command))
            )
        )

        return result

    async def send_to_device_native(
        self, unit_id: UnitId, key: str, command: Command
    ) -> str:
        """Sends json message from command object to device with unit id and
        aes key."""

        if not self.connection_hdl:
            return ""

        self.connection_hdl.controller_data.aes_keys[
            str(unit_id)
        ] = bytes.fromhex(key)

        msg_answer: str = ""

        msg: Message | None = await self.connection_hdl.send_message(
            send_msgs=[command],
            target_device_uid=unit_id,
            time_to_live_secs=11111,
        )
        if msg:
            if msg.exception:
                raise msg.exception
            msg_answer = msg.answer_utf8

        return msg_answer

    async def shutdown(self) -> None:
        """Shuts down the local controller."""

        if self.connection_hdl:
            await self.connection_hdl.shutdown()

    @classmethod
    def create_default(
        cls: Any,
        controller_data: ControllerData,
        server_ip: str = "0.0.0.0",
        network_interface: str | None = None,
    ) -> LocalController:
        """Builds a default local controller.

        Params:
            network_interface: leave it on None if you are unsure, else e. g.
                eth0, wlan0, etc.
            server_ip: The host IP to bind the server for incoming tcp
                connections on port 3333.
        """

        lc_hdl: LocalConnectionHandler = LocalConnectionHandler.create_default(
            controller_data=controller_data,
            server_ip=server_ip,
            network_interface=network_interface,
        )

        lc: LocalController = LocalController(controller_data)
        lc.connection_hdl = lc_hdl

        return lc

    @classmethod
    async def create_standalone(
        cls: Any,
        server_ip: str = "0.0.0.0",
        network_interface: str | None = None,
        interactive_prompts: bool = False,
    ) -> LocalController:
        """Factories a standalone local controller.

        Params:
            network_interface: eth0, wlan0 or None (uses default interface)
        """
        controller_data: ControllerData = await ControllerData.create_default(
            interactive_prompts=interactive_prompts, offline=True
        )

        lc: LocalController = LocalController.create_default(
            controller_data, server_ip, network_interface
        )
        return lc
