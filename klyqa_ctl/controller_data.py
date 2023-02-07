"""Controller data."""
from __future__ import annotations

from typing import Any

from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.light.light import Light
from klyqa_ctl.devices.response_identity_message import ResponseIdentityMessage
from klyqa_ctl.devices.vacuum.vacuum import VacuumCleaner
from klyqa_ctl.general.general import (
    AsyncIoLock,
    TypeJson,
    async_json_cache,
    task_log_debug,
)


class ControllerData:
    """Controller data holds the basis klyqa ctl data."""

    def __init__(
        self,
        interactive_prompts: bool = False,
        offline: bool = False,
        add_devices_lock: AsyncIoLock | None = None,
    ) -> None:
        """Initialize controller data."""

        self._attr_aes_keys: dict[str, bytes] = {}
        self._attr_interactive_prompts: bool = interactive_prompts
        self._attr_offline: bool = offline
        self._attr_device_configs: TypeJson = {}
        self._attr_devices: dict[str, Device] = {}
        self._attr_add_devices_lock: AsyncIoLock | None = add_devices_lock

    @property
    def aes_keys(self) -> dict[str, bytes]:
        return self._attr_aes_keys

    def add_aes_key(self, unit_id: str, aes_key: bytes | str) -> None:
        """Add AES key for a device (as string converted to bytes)."""

        if isinstance(aes_key, str):
            self.aes_keys[unit_id] = bytes.fromhex(aes_key)
        else:
            self.aes_keys[unit_id] = aes_key

    @property
    def interact_prompts(self) -> bool:
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
        """Initialize."""

        self.add_devices_lock = AsyncIoLock("add_devices_lock")

        await self.device_configs_cache()
        await self.aes_cache()

    async def device_configs_cache(self) -> None:
        """Store device configs for caching or read from cache if no device
        configs set."""

        device_configs_cache: dict | None = None
        cached: bool = False
        device_configs_cache, cached = await async_json_cache(
            device_configs_cache, "device.configs.json"
        )
        if cached and device_configs_cache:
            self.device_configs = device_configs_cache
            task_log_debug("Read device configs cache.")

    async def aes_cache(self) -> None:
        """Store AES keys for caching or read from cache if no AES keys
        set."""

        aes_cache: dict | None = None
        cached: bool = False
        aes_cache, cached = await async_json_cache(
            self.aes_keys or None, "aes.json"
        )
        if cached and aes_cache:
            self._attr_aes_keys = aes_cache
            task_log_debug("Read AES cache.")

    def create_device(self, unit_id: str, product_id: str) -> Device:
        """Create a device by product id in the controller data."""

        device: Device

        if ".lighting" in product_id:
            device = Light()
        elif ".cleaning" in product_id:
            device = VacuumCleaner()
        else:
            device = Device()
        device.u_id = unit_id
        device.product_id = product_id
        device.ident.unit_id = unit_id
        device.ident.product_id = product_id

        return device

    async def get_or_create_device(
        self, unit_id: str, product_id: str
    ) -> Device:
        """Get or create a device from the controller data. Read in device
        config when new device is created."""

        if unit_id in self.devices:
            return self.devices[unit_id]
        else:
            dev: Device = self.create_device(unit_id, product_id)
            if product_id in self.device_configs:
                dev.read_device_config(
                    device_config=self.device_configs[product_id]
                )

            if self.add_devices_lock:
                await self.add_devices_lock.acquire_within_task()

            self.devices[unit_id] = dev

            if self.add_devices_lock:
                self.add_devices_lock.release_within_task()

            return dev

    async def get_or_create_device_ident(
        self, identity: ResponseIdentityMessage
    ) -> Device:
        """Get or create device based on device identity."""
        return await self.get_or_create_device(
            unit_id=identity.unit_id, product_id=identity.product_id
        )

    @classmethod
    async def create_default(
        cls: Any,
        interactive_prompts: bool = False,
        offline: bool = False,
    ) -> ControllerData:
        """Factory for local only controller."""
        controller_data: ControllerData = ControllerData(
            interactive_prompts=interactive_prompts, offline=offline
        )
        await controller_data.init()
        return controller_data
