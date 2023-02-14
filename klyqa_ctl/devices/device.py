"""General device"""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from dataclasses import dataclass
from typing import Any

from klyqa_ctl.communication.device_connection_handler import (
    DeviceConnectionHandler,
)
from klyqa_ctl.devices.cloud_state import DeviceCloudState
from klyqa_ctl.devices.response_identity_message import ResponseIdentityMessage
from klyqa_ctl.devices.response_message import ResponseMessage
from klyqa_ctl.general.general import (
    DEFAULT_SEND_TIMEOUT_MS,
    LOGGER,
    AsyncIoLock,
    Command,
    CommandTyped,
    task_log_debug,
    task_log_trace_ex,
)
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId


class Device:
    """Device"""

    # pylint: disable=too-many-instance-attributes
    # Amount of attributes as needed in this case.

    def __init__(self) -> None:
        self._attr_local_addr: dict[str, Any] = {"ip": "", "port": -1}
        # device specific cloud connection results
        self._attr_cloud: DeviceCloudState = DeviceCloudState()
        self._attr_ident: ResponseIdentityMessage = ResponseIdentityMessage()

        self._attr_u_id: str = UnitId("no_uid")
        self._attr_acc_sets: dict[Any, Any] = {}
        self._attr__use_lock: AsyncIoLock | None = None
        self._attr__use_thread: asyncio.Task[Any] | None = None

        self._attr_status: ResponseMessage | None = None
        self._attr_response_classes: dict[str, Any] = {
            "ident": ResponseIdentityMessage,
            "status": ResponseMessage,
        }
        self._attr_device_config: dict[str, Any] = {}
        self._attr_product_id: str = ""

        self.local_con: DeviceConnectionHandler | None = None

    async def send_msg(
        self,
        commands: list[Command],
        time_to_live_secs: int,
        con: DeviceConnectionHandler,
        **kwargs: Any,
    ) -> Message | None:
        """Send message to device via desired connection set in
        connection handler (param: con)."""

        return await con.send_command_to_device(  # type: ignore[no-any-return]
            unit_id=UnitId(self.u_id),
            send_msgs=commands,
            time_to_live_secs=time_to_live_secs,
            **kwargs,
        )

    async def send_msg_local(
        self,
        commands: list[Command],
        time_to_live_secs: int = DEFAULT_SEND_TIMEOUT_MS,
        **kwargs,
    ) -> Message | None:
        """Send message to device via local connection."""

        if not self.local_con:
            return None
        return await self.send_msg(
            commands, time_to_live_secs, self.local_con, **kwargs
        )

    @property
    def local_addr(self) -> dict[str, Any]:
        return self._attr_local_addr

    @local_addr.setter
    def local_addr(self, local_addr: dict[str, Any]) -> None:
        self._attr_local_addr = local_addr

    @property
    def cloud(self) -> DeviceCloudState:
        return self._attr_cloud

    @cloud.setter
    def cloud(self, cloud: DeviceCloudState) -> None:
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

    def save_device_message(self, msg: Any) -> None:
        """msg: json dict"""

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
            except Exception:
                task_log_trace_ex()
                LOGGER.error("Could not process device response: ")
                LOGGER.error(f"{msg}")

    def read_device_config(self, device_config: dict[str, Any]) -> None:
        self.device_config = device_config
