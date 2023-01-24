"""Controller data."""
from __future__ import annotations

from typing import Any

from klyqa_ctl.account import Account
from klyqa_ctl.devices.device import Device
from klyqa_ctl.general.general import (
    AsyncIoLock,
    async_json_cache,
    task_log_debug,
)


class ControllerData:
    """Controller data."""

    def __init__(
        self,
        interactive_prompts: bool = False,
        offline: bool = False,
        user_account: Account | None = None,
        add_devices_lock: AsyncIoLock | None = None,
    ) -> None:
        self._attr_aes_keys: dict[str, bytes] = {}
        self._attr_interactive_prompts: bool = interactive_prompts
        self._attr_offline: bool = offline
        self._attr_device_configs: dict[Any, Any] = {}
        self._attr_devices: dict[str, Device] = {}
        self._attr_add_devices_lock: AsyncIoLock | None = add_devices_lock
        self._attr_account: Account | None = user_account

    @property
    def account(self) -> Account | None:
        return self._attr_account

    @account.setter
    def account(self, account: Account | None) -> None:
        self._attr_account = account

    @property
    def aes_keys(self) -> dict[str, bytes]:
        return self._attr_aes_keys

    @property
    def interactive_prompts(self) -> bool:
        return self._attr_interactive_prompts

    @property
    def offline(self) -> bool:
        return self._attr_offline

    @property
    def add_devices_lock(self) -> AsyncIoLock | None:
        return self._attr_add_devices_lock

    @add_devices_lock.setter
    def add_devices_lock(self, add_devices_lock: AsyncIoLock | None) -> None:
        self._attr_add_devices_lock = add_devices_lock

    @property
    def device_configs(self) -> dict[Any, Any]:
        return self._attr_device_configs

    @device_configs.setter
    def device_configs(self, device_configs: dict[Any, Any]) -> None:
        self._attr_device_configs = device_configs

    @property
    def devices(self) -> dict[str, Device]:
        """Return or set the devices dictionary."""
        return self._attr_devices

    async def init(self) -> None:
        device_configs_cache: dict | None = None
        cached: bool = False
        device_configs_cache, cached = await async_json_cache(
            device_configs_cache, "device.configs.json"
        )
        if cached and device_configs_cache:
            self.device_configs = device_configs_cache
            task_log_debug("Read device configs cache.")

    @classmethod
    async def create_default(
        cls: Any,
        interactive_prompts: bool = False,
        user_account: Account | None = None,
        offline: bool = False,
    ) -> ControllerData:
        """Factory for local only controller."""
        controller_data: ControllerData = ControllerData(
            interactive_prompts=interactive_prompts,
            user_account=user_account,
            offline=offline,
            add_devices_lock=AsyncIoLock("add_devices_lock"),
        )
        await controller_data.init()
        return controller_data
