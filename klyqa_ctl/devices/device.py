"""General device"""
from __future__ import annotations
import asyncio
import datetime
import traceback
from typing import Any

from ..general.connections import CloudConnection
from ..general.general import LOGGER, Device_config
from ..general.message import Message

import slugify


def format_uid(text: str) -> str:
    return slugify.slugify(text)


# Device profiles for limits and features (traits) for the devices.
#
device_configs: dict[str, Device_config] = dict()


class KlyqaDevice:
    """KlyqaDevice"""

    local_addr: dict[str, Any] = {"ip": "", "port": -1}
    cloud: CloudConnection

    u_id: str = "no_uid"
    acc_sets: dict = {}
    """ account settings """

    _use_lock: asyncio.Lock | None
    _use_thread: asyncio.Task | None

    recv_msg_unproc: list[Message]
    ident: KlyqaDeviceResponseIdent | None = None

    response_classes = {}
    status: KlyqaDeviceResponse | None

    def __init__(self) -> None:
        self.local_addr = {"ip": "", "port": -1}
        self.cloud = CloudConnection()
        self.ident = KlyqaDeviceResponseIdent()

        self.u_id: str = "no_uid"
        self.acc_sets = {}
        self._use_lock = None
        self._use_thread = None
        self.recv_msg_unproc = []

        self.status = None
        self.response_classes: dict[str, Any] = {
            "ident": KlyqaDeviceResponseIdent,
            "status": KlyqaDeviceResponse,
        }

    def process_msgs(self) -> None:
        for msg in self.recv_msg_unproc:
            LOGGER.debug(f"updating device {self.u_id} entity with msg:")
            self.recv_msg_unproc.remove(msg)

    def get_name(self) -> str:
        return (
            f"{self.acc_sets['name']} ({self.u_id})"
            if self.acc_sets and "name" in self.acc_sets and self.acc_sets
            else self.u_id
        )

    async def use_lock(self, timeout=30, **kwargs) -> bool:
        try:
            if not self._use_lock:
                self._use_lock = asyncio.Lock()

            LOGGER.debug(f"wait for lock... {self.get_name()}")

            if await self._use_lock.acquire():
                self._use_thread = asyncio.current_task()
                LOGGER.debug(f"got lock... {self.get_name()}")
                return True
        except asyncio.TimeoutError:
            LOGGER.error(f'Timeout for getting the lock for device "{self.get_name()}"')
        except Exception as excp:
            LOGGER.debug(f"different error while trying to lock.")

        return False

    async def use_unlock(self) -> None:
        if not self._use_lock:
            self._use_lock = asyncio.Lock()
        if self._use_lock.locked() and self._use_thread == asyncio.current_task():
            try:
                self._use_lock.release()
                self._use_thread = None
                LOGGER.debug(f"got unlock... {self.get_name()}")
            except:
                pass

    def save_device_message(self, msg) -> None:
        """msg: json dict"""

        status_update_types: set = {"status", "statechange"}
        if msg["type"] in status_update_types:
            msg["type"] = "status"
        if "type" in msg and hasattr(self, msg["type"]):  # and msg["type"] in msg:
            try:
                LOGGER.debug(f"save device msg {msg} {self.ident} {self.u_id}")
                if msg["type"] == "ident" and self.ident:
                    # setattr(self, "ident", self.ident.update(**msg))
                    # setattr(
                    #     self,
                    #     msg["type"],
                    #     self.response_classes[msg["type"]](**msg[msg["type"]]),
                    # )
                    self.ident.update(**msg["ident"])
                elif msg["type"] in status_update_types:  # and self.status:
                    # setattr(self, msg["type"], self.response_classes[msg["type"]](**msg))
                    # setattr(self, "status", self.status.update(**msg))
                    if self.status is None:
                        self.status = self.response_classes["status"](**msg)
                    else:
                        self.status.update(**msg)
            except Exception as e:
                LOGGER.error(f"{traceback.format_exc()}")
                LOGGER.error("Could not process device response: ")
                LOGGER.error(f"{msg}")


class KlyqaDeviceResponse:
    def __init__(self, **kwargs) -> None:
        """__init__"""
        self.type: str = ""
        self.ts: datetime.datetime | None = None
        self.update(**kwargs)

    def update(self, **kwargs) -> None:
        self.ts = datetime.datetime.now()
        # Walk through parsed kwargs dict and look if names in dict exists as attribute in class,
        # then apply the value in kwargs to the value in class.
        for attr in kwargs:
            if hasattr(self, attr):
                setattr(self, attr, kwargs[attr])


# eventually dataclass
class KlyqaDeviceResponseIdent(KlyqaDeviceResponse):
    """KlyqaDeviceResponseIdent"""

    def __init__(
        self,
        **kwargs,
    ) -> None:
        self.fw_version: str = ""
        self.fw_build: str = ""
        self.hw_version: str = ""
        self.manufacturer_id: str = ""
        self.product_id: str = ""
        self.sdk_version: str = ""
        self._unit_id: str = ""
        super().__init__(**kwargs)

    def update(self, **kwargs) -> None:
        super().update(**kwargs)

    @property
    def unit_id(self) -> str:
        return self._unit_id

    @unit_id.setter
    def unit_id(self, unit_id: str) -> None:
        self._unit_id = format_uid(unit_id)
