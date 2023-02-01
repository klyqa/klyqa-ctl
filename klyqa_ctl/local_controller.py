"""Local connection controller. Should be merged with local
in connection controller, they are basically the same."""

from __future__ import annotations

import asyncio
from typing import Any

from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.general.general import ShutDownHandler, get_asyncio_loop


class LocalController(ShutDownHandler):
    """Controls local connections via tcp and udp for broadcasts and
    connections directly to devices."""

    def __init__(
        self,
        controller_data: ControllerData,
    ) -> None:
        """Initializes the local controller."""

        super().__init__()

        self.connection_hdl: LocalConnectionHandler | None = None
        self.controller_data: ControllerData = controller_data

    def send_to_device(self, unit_id: str, key: str, command: str) -> str:
        """Sends command string to device with unit id and aes key."""

        if not self.connection_hdl:
            return ""

        loop: asyncio.AbstractEventLoop = get_asyncio_loop()

        result: str = loop.run_until_complete(
            self.connection_hdl.send_to_device(unit_id, command, key)
        )

        return result

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

        lctlr: LocalController = LocalController(controller_data)
        lctlr.connection_hdl = lc_hdl

        return lctlr

    @classmethod
    async def async_create_standalone(
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

        ctrl: LocalController = LocalController.create_default(
            controller_data, server_ip, network_interface
        )
        if ctrl.connection_hdl:
            ctrl._shutdown_handler.append(ctrl.connection_hdl.shutdown)

        return ctrl

    @classmethod
    def create_standalone(
        cls: Any,
        server_ip: str = "0.0.0.0",
        network_interface: str | None = None,
        interactive_prompts: bool = False,
    ) -> LocalController:
        """Factories a standalone local controller.

        Params:
            network_interface: eth0, wlan0 or None (uses default interface)
        """

        loop: asyncio.AbstractEventLoop = get_asyncio_loop()

        return loop.run_until_complete(
            LocalController.async_create_standalone(
                server_ip,
                network_interface,
                interactive_prompts=interactive_prompts,
            )
        )
