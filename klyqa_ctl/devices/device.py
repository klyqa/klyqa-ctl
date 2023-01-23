"""General device"""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from dataclasses import dataclass
import traceback
from typing import Any

from klyqa_ctl.devices.response_identity_message import ResponseIdentityMessage
from klyqa_ctl.devices.response_message import ResponseMessage
from klyqa_ctl.general.connections import CloudConnection
from klyqa_ctl.general.general import LOGGER, AsyncIoLock, CommandTyped
from klyqa_ctl.general.unit_id import UnitId


@dataclass
class CommandWithCheckValues(CommandTyped):
    force: bool = False

    @abstractmethod
    def check_values(self, device: Device) -> bool:
        return False


class Device:
    """Device"""

    def __init__(self) -> None:
        self._attr_local_addr: dict[str, Any] = {"ip": "", "port": -1}
        self._attr_cloud: CloudConnection = CloudConnection()
        self._attr_ident: ResponseIdentityMessage | None = (
            ResponseIdentityMessage()
        )

        self._attr_u_id: str = UnitId("no_uid")
        self._attr_acc_sets: dict[Any, Any] = {}
        self._attr__use_lock: AsyncIoLock | None = None
        self._attr__use_thread: asyncio.Task[Any] | None = None
        # self._attr_recv_msg_unproc: list[Message] = []

        self._attr_status: ResponseMessage | None = None
        self._attr_response_classes: dict[str, Any] = {
            "ident": ResponseIdentityMessage,
            "status": ResponseMessage,
        }
        self._attr_device_config: dict[str, Any] = {}

    @property
    def local_addr(self) -> dict[str, Any]:
        return self._attr_local_addr

    @local_addr.setter
    def local_addr(self, local_addr: dict[str, Any]) -> None:
        self._attr_local_addr = local_addr

    @property
    def cloud(self) -> CloudConnection:
        return self._attr_cloud

    @cloud.setter
    def cloud(self, cloud: CloudConnection) -> None:
        self._attr_cloud = cloud

    @property
    def ident(self) -> ResponseIdentityMessage | None:
        return self._attr_ident

    @ident.setter
    def ident(self, ident: ResponseIdentityMessage | None) -> None:
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

    # @property
    # def recv_msg_unproc(self) -> list[Message]:
    #     return self._attr_recv_msg_unproc

    # @recv_msg_unproc.setter
    # def recv_msg_unproc(self, recv_msg_unproc: list[Message]) -> None:
    #     self._attr_recv_msg_unproc = recv_msg_unproc

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

    # def process_msgs(self) -> None:
    #     for msg in self.recv_msg_unproc:
    #         LOGGER.debug(f"updating device {self.u_id} entity with msg:")
    #         self.recv_msg_unproc.remove(msg)

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

        # try:
        #     LOGGER.debug(f"wait for lock... {self.get_name()}")

        #     await asyncio.wait_for(self._use_lock.acquire(), timeout)

        #     self._use_thread = asyncio.current_task()

        #     task_log(f"got lock... {self.get_name()}")
        #     return True
        # except asyncio.TimeoutError:
        #     LOGGER.error(f'Timeout for getting the lock for device '
        # f'"{self.get_name()}"')
        # except Exception:
        #     task_log_error(f"Error while trying to get device lock!")
        #     task_log_trace()

        # return False

    def use_unlock(self) -> None:
        if not self._use_lock:
            return
        self._use_lock.release_within_task()
        # if (self._use_lock.locked() and self._use_thread ==
        # asyncio.current_task()):
        #     try:
        #         self._use_lock.release()
        #         self._use_thread = None
        #         LOGGER.debug(f"got unlock... {self.get_name()}")
        #     except:
        #         task_log_error(f"Error while trying to unlock the device! "
        # f"(Probably now locked until restart)")
        #         task_log_trace()

    def save_device_message(self, msg: Any) -> None:
        """msg: json dict"""

        status_update_types: set = {"status", "statechange"}
        if msg["type"] in status_update_types:
            msg["type"] = "status"
        if "type" in msg and hasattr(self, msg["type"]):
            try:
                LOGGER.debug(f"save device msg {msg} {self.ident} {self.u_id}")
                if msg["type"] == "ident" and self.ident:
                    self.ident.update(**msg["ident"])
                elif msg["type"] in status_update_types:
                    if self.status is None:
                        self.status = self.response_classes["status"](**msg)
                    else:
                        self.status.update(**msg)
            except Exception:
                LOGGER.error(f"{traceback.format_exc()}")
                LOGGER.error("Could not process device response: ")
                LOGGER.error(f"{msg}")

    def read_device_config(self, device_config: dict[str, Any]) -> None:
        self.device_config = device_config
