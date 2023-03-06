"""General device"""
from __future__ import annotations

import asyncio
import datetime
from typing import Any, Callable

from klyqa_ctl.devices.commands import PingCommand
from klyqa_ctl.devices.connection import DeviceConnection
from klyqa_ctl.devices.response_identity_message import ResponseIdentityMessage
from klyqa_ctl.devices.response_message import ResponseMessage
from klyqa_ctl.general.general import (
    DEFAULT_SEND_TIMEOUT_MS,
    LOGGER,
    Address,
    AsyncIoLock,
    Command,
    TypeJson,
    task_log_debug,
    task_log_trace_ex,
)
from klyqa_ctl.general.message import Message, MessageState
from klyqa_ctl.general.unit_id import UnitId


class Device:
    """Device"""

    # pylint: disable=too-many-instance-attributes
    # Amount of attributes as needed in this case.

    def __init__(self) -> None:
        """Initialize a general device without much details."""

        self._attr_local_addr: Address = Address()
        # device specific cloud connection results
        self._attr_local: DeviceConnection = DeviceConnection()
        self._attr_cloud: DeviceConnection = DeviceConnection()
        self._attr_ident: ResponseIdentityMessage = ResponseIdentityMessage()

        self._attr_u_id: str = ""
        self._attr_acc_sets: dict[Any, Any] = {}
        self._attr__use_lock: AsyncIoLock | None = None
        self._attr__use_thread: asyncio.Task[Any] | None = None

        self._attr_status: ResponseMessage | None = None

        self._attr_status_update_cb: list[Callable[[], None]] = []

        self._attr_response_classes: dict[str, Any] = {
            "ident": ResponseIdentityMessage,
            "status": ResponseMessage,
        }
        self._attr_device_config: dict[str, Any] = {}
        self._attr_product_id: str = ""
        self._attr_last_ping_con: datetime.datetime | None = None

    async def ping_con(
        self, dcon: DeviceConnection, ttl_ping_secs: int = 10
    ) -> Message | None:
        """Try reach out device via connection and set connection state."""

        if (
            self._attr_last_ping_con
            and datetime.datetime.now() - self._attr_last_ping_con
            < datetime.timedelta(seconds=ttl_ping_secs)
        ):
            return None
        self._attr_last_ping_con = datetime.datetime.now()

        msg: Message | None = await self.send_msg(
            [PingCommand()], time_to_live_secs=ttl_ping_secs, dcon=dcon
        )

        # if msg and msg.state == MessageState.ANSWERED:
        #     dcon.connected = True
        # else:
        #     dcon.connected = False
        return msg

    async def send_msg(
        self,
        commands: list[Command],
        time_to_live_secs: int,
        dcon: DeviceConnection,
        **kwargs: Any,
    ) -> Message | None:
        """Send message to device via desired connection set in
        connection handler (param: con)."""

        if not dcon.con:
            return None

        msg: Message | None = await dcon.con.send_command_to_device(
            unit_id=UnitId(self.u_id),
            send_msgs=commands,
            time_to_live_secs=time_to_live_secs,
            **kwargs,
        )
        # if msg and msg.state == MessageState.ANSWERED:
        #     dcon.connected = True
        # else:
        #     dcon.connected = False

        return msg

    async def send_msg_local(
        self,
        commands: list[Command],
        time_to_live_secs: int = DEFAULT_SEND_TIMEOUT_MS,
        **kwargs: Any,
    ) -> Message | None:
        """Send message to device via local connection."""

        if not self.local.con:
            return None
        return await self.send_msg(commands, time_to_live_secs, self.local)

    async def send_msg_auto(
        self,
        commands: list[Command],
        time_to_live_secs: int = DEFAULT_SEND_TIMEOUT_MS,
        **kwargs: Any,
    ) -> Message | None:
        """Send message to device via local or cloud connection and restore
        connection states."""

        msg: Message | None = None
        for con in [self.local, self.cloud]:
            if con:
                if con.connected and (
                    not msg or msg.state != MessageState.ANSWERED
                ):
                    msg = await self.send_msg(
                        commands,
                        time_to_live_secs,
                        self.local,
                        **kwargs,
                    )
                elif not con.connected:
                    asyncio.create_task(self.ping_con(con))
        return msg

    @property
    def status_update_cb(self) -> list[Callable[[], None]]:
        return self._attr_status_update_cb

    def add_status_update_cb(self, cb: Callable[[], None]) -> None:
        if cb not in self.status_update_cb:
            self.status_update_cb.append(cb)

    @property
    def local(self) -> DeviceConnection:
        return self._attr_local

    @local.setter
    def local(self, local: DeviceConnection) -> None:
        self._attr_local = local

    @property
    def local_addr(self) -> Address:
        return self._attr_local_addr

    @local_addr.setter
    def local_addr(self, local_addr: Address) -> None:
        self._attr_local_addr = local_addr

    @property
    def cloud(self) -> DeviceConnection:
        return self._attr_cloud

    @cloud.setter
    def cloud(self, cloud: DeviceConnection) -> None:
        self._attr_cloud = cloud

    @property
    def ident(self) -> ResponseIdentityMessage:
        return self._attr_ident

    @ident.setter
    def ident(self, ident: ResponseIdentityMessage) -> None:
        self._attr_ident = ident

    @property
    def u_id(self) -> str:
        return self._attr_u_id

    @u_id.setter
    def u_id(self, u_id: str) -> None:
        self._attr_u_id = str(UnitId(u_id))

    @property
    def acc_sets(self) -> dict[Any, Any]:
        return self._attr_acc_sets

    @acc_sets.setter
    def acc_sets(self, acc_sets: dict) -> None:
        self._attr_acc_sets = acc_sets

    @property
    def _use_lock(self) -> AsyncIoLock | None:
        return self._attr__use_lock

    @_use_lock.setter
    def _use_lock(self, _use_lock: AsyncIoLock | None) -> None:
        self._attr__use_lock = _use_lock

    @property
    def _use_thread(self) -> asyncio.Task[Any] | None:
        return self._attr__use_thread

    @_use_thread.setter
    def _use_thread(self, _use_thread: asyncio.Task[Any] | None) -> None:
        self._attr__use_thread = _use_thread

    @property
    def status(self) -> ResponseMessage | None:
        return self._attr_status

    @status.setter
    def status(self, status: ResponseMessage | None) -> None:
        self._attr_status = status

    @property
    def response_classes(self) -> dict[str, Any]:
        return self._attr_response_classes

    @response_classes.setter
    def response_classes(self, response_classes: dict[str, Any]) -> None:
        self._attr_response_classes = response_classes

    @property
    def device_config(self) -> dict[str, Any]:
        return self._attr_device_config

    @device_config.setter
    def device_config(self, device_config: dict[str, Any]) -> None:
        self._attr_device_config = device_config

    @property
    def product_id(self) -> str:
        return self._attr_product_id

    @product_id.setter
    def product_id(self, product_id: str) -> None:
        self._attr_product_id = product_id

    def get_name(self) -> str:
        return (
            f"{self.acc_sets['name']} ({self.u_id})"
            if self.acc_sets and "name" in self.acc_sets and self.acc_sets
            else self.u_id
        )

    async def use_lock(self, timeout: int = 30, **kwargs: Any) -> bool:
        """Get device lock."""
        if not self._use_lock:
            self._use_lock = AsyncIoLock(self.u_id)

        if not await self._use_lock.acquire_within_task(timeout, **kwargs):
            return False

        return True

    def use_unlock(self) -> None:
        if not self._use_lock:
            return
        self._use_lock.release_within_task()

    def save_device_message(self, msg: TypeJson) -> None:
        """Save a device response message into the device object."""

        status_update_types: set = {"status", "statechange"}
        if msg["type"] in status_update_types:
            msg["type"] = "status"
        if "type" in msg and hasattr(self, msg["type"]):
            try:
                task_log_debug(
                    f"save device msg {msg} {self.ident} {self.u_id}"
                )
                if msg["type"] == "ident" and self.ident:
                    self.ident.update(**msg["ident"])
                elif msg["type"] in status_update_types:
                    if self.status is None:
                        self.status = self.response_classes["status"](**msg)
                    else:
                        self.status.update(**msg)
                    for update_cb in self.status_update_cb:
                        try:
                            update_cb()
                        except ValueError:
                            task_log_trace_ex()
                else:
                    raise ValueError
            except Exception:
                task_log_trace_ex()
                LOGGER.error("Could not process device response: ")
                LOGGER.error(f"{msg}")

    def read_device_config(self, device_config: dict[str, Any]) -> None:
        self.device_config = device_config
