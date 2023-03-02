"""Klyqa account."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime
from enum import Enum
import getpass
import json
from typing import Any

import httpx

from klyqa_ctl.communication.cloud import CloudBackend, RequestMethod
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.commands_device import CommandWithCheckValues
from klyqa_ctl.devices.device import Device
from klyqa_ctl.general.general import (
    ACC_SETS_REQUEST_TIMEDELTA,
    LOGGER,
    CloudStateCommand,
    Command,
    DeviceConfig,
    TypeJson,
    aes_key_to_bytes,
    async_json_cache,
    format_uid,
    get_asyncio_loop,
    task_log_debug,
    task_log_error,
)


class CloudDeviceTargets(str, Enum):
    """Rest calls, cloud device targets."""

    COMMAND = "command"
    STATE = "state"


@dataclass()
class AccountDevice:
    """Account device"""

    acc_settings: TypeJson
    device: Device


class Account:
    """Account"""

    # Set of current accepted connections to an IP. One connection is most of
    # the time enough to send all messages for that device behind that
    # connection (in the aes send message method).
    # If connection is currently finishing due to sent messages and no
    # messages left for that device and a new message appears in the
    # queue, send a new broadcast and establish a new connection.
    #

    def __init__(
        self, controller_data: ControllerData, cloud: CloudBackend | None
    ) -> None:
        """Initialize the account."""

        self._attr_username: str = ""
        self._attr_password: str = ""
        self._attr_access_token: str = ""
        self._attr_settings: TypeJson | None = {}
        self._attr_settings_lock: asyncio.Lock | None = None

        # Representation of unit_id and Account Device.
        self._attr_devices: dict[str, AccountDevice] = {}
        self._attr_controller_data: ControllerData = controller_data
        self._attr_cloud: CloudBackend | None = cloud
        self.print_onboarded_devices: bool = False  # for login print

        self._attr__settings_loaded_ts: datetime.datetime | None = None

    @property
    def username(self) -> str:
        """Get account username."""

        return self._attr_username

    @username.setter
    def username(self, username: str) -> None:
        self._attr_username = username

    @property
    def password(self) -> str:
        """Get account password."""

        return self._attr_password

    @password.setter
    def password(self, password: str) -> None:
        self._attr_password = password

    @property
    def access_token(self) -> str:
        """Get access token."""

        return self._attr_access_token

    @access_token.setter
    def access_token(self, access_token: str) -> None:
        self._attr_access_token = access_token

    @property
    def devices(self) -> dict[str, AccountDevice]:
        """Get devices list."""

        return self._attr_devices

    @devices.setter
    def devices(self, devices: dict[str, AccountDevice]) -> None:
        self._attr_devices = devices

    @property
    def settings(self) -> TypeJson | None:
        """Get account settings."""

        return self._attr_settings

    @settings.setter
    def settings(self, settings: TypeJson | None) -> None:
        raise NotImplementedError("Use set_settings()!")

    @property
    def settings_lock(self) -> asyncio.Lock | None:
        """Get account settings lock."""

        return self._attr_settings_lock

    @property
    def ctld(self) -> ControllerData:
        """Return or set the controller data object."""
        return self._attr_controller_data

    @property
    def cloud(self) -> CloudBackend | None:
        """Get cloud backend control."""

        return self._attr_cloud

    @cloud.setter
    def cloud(self, cloud: CloudBackend | None) -> None:
        self._attr_cloud = cloud

    @property
    def _settings_loaded_ts(self) -> datetime.datetime | None:
        return self._attr__settings_loaded_ts

    @_settings_loaded_ts.setter
    def _settings_loaded_ts(
        self, _settings_loaded_ts: datetime.datetime
    ) -> None:
        self._attr__settings_loaded_ts = _settings_loaded_ts

    def backend_connected(self) -> bool:
        """General cloud intended to be there check."""
        return (
            self.access_token != ""
            and self.cloud is not None
            and self.cloud.backend_connected()
        )

    async def request_beared(
        self, method: RequestMethod, url: str, **kwargs: Any
    ) -> TypeJson | None:
        """When the user logged in and an access token exists, use it for http
        requests."""

        if not self.cloud:
            return None
        resp: httpx.Response | None = await self.cloud.request(
            method,
            url,
            self.get_beared_request_header()
            if self.access_token
            else self.cloud.get_header_default(),
            **kwargs,
        )
        if resp:
            answer: TypeJson | None = await self.cloud.load_http_response(resp)
            return answer
        return None

    def get_beared_request_header(self) -> TypeJson:
        """Set default request header with cloud access token."""

        if not self.cloud:
            return TypeJson()

        return TypeJson(
            self.cloud.get_header_default()
            | {"Authorization": "Bearer " + self.access_token}
        )

    async def shutdown(self) -> None:
        """Logout again from klyqa account."""
        if self.access_token and self.cloud:
            task_log_debug("Logout user from cloud backend.")
            r: httpx.Response | None = await self.cloud.request(
                RequestMethod.POST, "/auth/logout"
            )
            if r and str(r.status_code)[0] in ["1", "2", "3"]:
                self.access_token = ""

    def run_password_prompt(self) -> bool:
        """Check if password is giving or prompt for it."""

        if not self.password:
            if self.ctld and self.ctld.interact_prompts:
                self.password = getpass.getpass(
                    prompt=(
                        " Please enter your Klyqa Account password (will be"
                        " saved): "
                    ),
                    stream=None,
                )
            else:
                LOGGER.error("Missing Klyqa account password. Login failed.")
                return False
        return True

    async def perform_login(self) -> bool:
        """Perform login in cloud backend and request account settings."""

        if not self.cloud or self.cloud.offline:
            return False

        self.run_password_prompt()
        if not self.password:
            return False

        if self.username is not None and self.password is not None:
            login_response: httpx.Response | None = None

            if not self.access_token:
                login_data: TypeJson = {
                    "email": self.username,
                    "password": self.password,
                }

                login_response = await self.cloud.request(
                    RequestMethod.POST,
                    "auth/login",
                    json=login_data,
                    timeout=10,
                )
                if not login_response:
                    return False

                if login_response.status_code == 401:
                    task_log_error("Login failed. Username or password wrong.")
                    return False

                login_json: TypeJson | None = (
                    await self.cloud.load_http_response(login_response)
                )

                if login_json:
                    self.access_token = str(login_json.get("accessToken"))
                else:
                    task_log_error("Could not load login response.")
                    return False

        return True

    async def read_username_cache(self) -> None:
        """Read username from cache."""

        cached: bool

        user_name_cache: dict | None
        user_name_cache, cached = await async_json_cache(
            None, "last_username.json"
        )
        if not self.username and cached and user_name_cache:
            self.username = user_name_cache["username"]
            LOGGER.info("Using Klyqa account %s.", self.username)

    async def request_device_configs_from_acc_sets(self) -> None:
        """Request the device config from the product ids in the
        account setting's devices."""

        if not self.settings or not self.cloud:
            return

        await self.cloud.get_device_configs(
            set(
                [
                    device_sets["productId"]
                    for device_sets in (self.settings["devices"])
                    if "productId" in device_sets and device_sets["productId"]
                ]
            )
        )

    async def get_or_create_device(
        self,
        unit_id: str,
        product_id: str = "",
        device_sets: TypeJson | None = None,
    ) -> AccountDevice:
        """Look for account device or create it. Create connected controller
        device as well."""

        if device_sets is None:
            device_sets = TypeJson()

        dev: AccountDevice
        if unit_id in self.devices:
            dev = self.devices[unit_id]
        else:
            device: Device = await self.ctld.get_or_create_device(
                unit_id, product_id
            )
            dev = AccountDevice(device_sets, device)
            self.devices[unit_id] = dev

        return dev

    async def set_settings(self, settings: TypeJson) -> None:
        """Async setter for account settings."""

        if self.settings_lock:
            await self.settings_lock.acquire()
        self._attr_settings = settings
        try:
            await self.sync_acc_settings_to_controller()
        finally:
            if self.settings_lock:
                self.settings_lock.release()

    async def sync_acc_settings_to_controller(self) -> bool:
        """Apply the account settings to the controller."""

        if not self.settings:
            return False

        for device_sets in self.settings["devices"]:

            self.ctld.aes_keys[
                format_uid(device_sets["localDeviceId"])
            ] = aes_key_to_bytes(device_sets["aesKey"])

            unit_id: str = format_uid(device_sets["localDeviceId"])

            await self.get_or_create_device(
                unit_id, device_sets["productId"], device_sets
            )

        return True

    async def read_acc_settings_cache(
        self,
    ) -> None:
        """Read user account settings cache."""

        acc_settings: TypeJson | None
        cached: bool
        acc_settings, cached = await async_json_cache(
            None, f"{self.username}.acc_settings.cache.json"
        )
        if cached and acc_settings:
            await self.set_settings(acc_settings)
            if self.settings and not self.password:
                self.password = self.settings["password"]

    # async def update_device_configs(self) -> None:

    #     await self.request_device_configs_from_acc_sets()

    #     for device_sets in self.settings["devices"]:

    #         unit_id: str = format_uid(device_sets["localDeviceId"])

    #         await self.get_or_create_device(
    #             unit_id, device_sets["productId"], device_sets
    #         )

    async def read_cache(self) -> None:
        """Get cached account data for login and check existing username and
        password."""

        await self.read_username_cache()
        await self.read_acc_settings_cache()

    async def init(self) -> None:
        """Initialize account."""

        self._attr_settings_lock = asyncio.Lock()
        await self.read_cache()

    async def device_request_and_print(
        self,
        dev: AccountDevice,
        print_onboarded_devices: bool = False,
        req_timeout: int = 30,
    ) -> None:
        """Request account device's states and print them."""

        cloud_state: TypeJson | None = None
        state_str: str
        device: Device

        if not self.backend_connected() or not self.cloud:
            return

        state_str = (
            f'Name: "{dev.acc_settings["name"]}"'
            + f'\tAES-KEY: {dev.acc_settings["aesKey"]}'
            + f'\tUnit-ID: {dev.acc_settings["localDeviceId"]}'
            + f'\tCloud-ID: {dev.acc_settings["cloudDeviceId"]}'
            + f'\tType: {dev.acc_settings["productId"]}'
        )

        device = dev.device
        cloud_state = await self.request_cloud_device_state(
            dev.acc_settings["cloudDeviceId"], timeout=req_timeout
        )
        if cloud_state:
            if "connected" in cloud_state:
                state_str = (
                    state_str
                    + f'\tCloud-Connected: {cloud_state["connected"]}'
                )
            device.cloud.connected = cloud_state["connected"]

            device.save_device_message(cloud_state | {"type": "status"})
        else:
            LOGGER.info(
                "No answer for cloud device state request %s",
                dev.acc_settings["localDeviceId"],
            )

        if print_onboarded_devices:
            print(state_str)

    async def device_request_and_print_task(
        self, print_onboarded_devices: bool = False
    ) -> None:
        """Print account devices state."""

        loop: asyncio.AbstractEventLoop = get_asyncio_loop()
        if self.cloud:
            await self.cloud.update_devices_configs_all()

        devices_tasks: list[asyncio.Task[Any]] = [
            loop.create_task(
                self.device_request_and_print(
                    acc_dev,
                    print_onboarded_devices=print_onboarded_devices,
                    req_timeout=30,
                )
            )
            for _, acc_dev in self.devices.items()
        ]
        await asyncio.wait(devices_tasks)

    async def login(self) -> bool:
        """Login on klyqa account, get account settings, get onboarded
        device profiles, print all devices if parameter set.

        Params:
            print_onboarded_devices:   print onboarded devices from the
                klyqa account to the stdout

        Returns:
            true:  on success of the login
            false: on error
        """

        if not self.cloud:
            return False

        if not self.settings:
            await self.read_cache()

        if not self.username:
            if self.ctld and self.ctld.interact_prompts:
                while not self.username:
                    LOGGER.error("Username missing, username cache empty.")
                    self.username = input(
                        " Please enter your Klyqa Account username (will"
                        " be cached for the script invoke): "
                    )
            else:
                LOGGER.info("Missing Klyqa account username. No login.")
                return False

        if not await self.perform_login():
            return False

        await async_json_cache(
            {"username": self.username}, "last_username.json"
        )

        return True

    async def request_cloud_device_state(
        self, device_id: str, timeout: int = 30, **kwargs: Any
    ) -> TypeJson | None:
        """Request device state from the cloud."""

        response: TypeJson | None = await self.request_beared(
            RequestMethod.GET,
            f"device/{device_id}/" + CloudDeviceTargets.STATE.value,
            timeout=timeout,
            **kwargs,
        )
        return response

    async def request_account_settings_eco(
        self, timedelta: int = ACC_SETS_REQUEST_TIMEDELTA
    ) -> bool:
        """Only send a new account settings http request when the last update
        was after the scan interval."""

        if not self.cloud:
            return False

        ret: bool = True
        now: datetime.datetime = datetime.datetime.now()
        if (
            not self.settings
            or not self._settings_loaded_ts
            or (
                now - self._settings_loaded_ts
                >= datetime.timedelta(seconds=timedelta)
            )
        ):
            # Look that the settings are loaded only once in the scan
            # interval
            await self.request_account_settings()
        return ret

    async def request_account_settings(
        self, add_to_cache: TypeJson | None = None
    ) -> None:
        """Request the account settings from cloud and apply it.
        Get device configs from the product ids as well."""

        if not self.cloud:
            return

        if not add_to_cache:
            add_to_cache = {}

        add_to_cache = add_to_cache | {
            "time_cached": datetime.datetime.now(),
            "password": self.password,
        }

        acc_settings: TypeJson | None = await self.request_beared(
            RequestMethod.GET, "settings"
        )
        if acc_settings:
            self._settings_loaded_ts = datetime.datetime.now()
            await self.set_settings(acc_settings)
            # save user account settings in cache
            if self.settings:
                await async_json_cache(
                    self.settings | add_to_cache,
                    f"{self.username}.acc_settings.cache.json",
                )

    async def get_account_state(
        self, print_onboarded_devices: bool = False
    ) -> None:
        """Get account state."""

        await self.request_account_settings()

        await self.device_request_and_print_task(
            print_onboarded_devices=print_onboarded_devices
        )

    async def update_device_configs(self) -> None:
        """Request the device configs from the cloud."""

        product_ids: set[str] = {
            acc_device.device.ident.product_id
            for uid, acc_device in self.devices.items()
            if acc_device.device.ident and acc_device.device.ident.product_id
        }

        for product_id in list(product_ids):
            if (
                self.ctld.device_configs
                and product_id in self.ctld.device_configs
            ):
                continue
            task_log_debug("Try to request device config from server.")

            config: TypeJson | None = await self.request_beared(
                RequestMethod.GET,
                "config/product/" + product_id,
                timeout=30,
            )
            device_config: DeviceConfig | None = config
            if device_config:
                self.ctld.device_configs[product_id] = device_config

    async def cloud_post_to_device(
        self,
        acc_dev: AccountDevice,
        json_message: TypeJson,
        target: str,
        **kwargs: Any,
    ) -> None:
        """Post json message to account device via cloud."""

        cloud_device_id: str = acc_dev.acc_settings["cloudDeviceId"]
        unit_id: str = format_uid(acc_dev.acc_settings["localDeviceId"])
        LOGGER.info(
            f"Post {target} to the device '{cloud_device_id}' (unit_id:"
            f" {unit_id}) over the cloud. Command: {json_message}"
        )
        response: TypeJson = {
            cloud_device_id: await self.request_beared(
                RequestMethod.POST,
                url=f"device/{cloud_device_id}/{target}",
                json=json_message,
                **kwargs,
            )
        }

        resp_print: str = ""
        name: str = acc_dev.device.u_id

        if acc_dev.acc_settings and "name" in acc_dev.acc_settings:
            name = acc_dev.acc_settings["name"]

        resp_print = f'Device "{name}" cloud response:'
        resp_print = json.dumps(response, sort_keys=True, indent=4)
        acc_dev.device.cloud.received_packages.append(response)
        print(resp_print)

    async def cloud_post_command_to_dev(
        self,
        device: AccountDevice,
        command: Command,
        target: CloudDeviceTargets | None = None,
        **kwargs: Any,
    ) -> None:
        """Post command to account device via cloud."""

        if not target:
            target = CloudDeviceTargets.COMMAND
            if isinstance(command, CloudStateCommand):
                target = CloudDeviceTargets.STATE

        if target:
            if isinstance(command, CommandWithCheckValues):
                cwcv: CommandWithCheckValues = command
                if not cwcv.check_values(device.device):
                    task_log_debug("Command values to send out of range!")
                    return

            await self.cloud_post_to_device(
                device, command.cloud(), target.value, **kwargs
            )

    # async def cloud_post_state_to_dev(
    #     self, device: Device, command: Command, target: str
    # ) -> None:
    #     json_message: TypeJson = {"payload": command.json()}
    #     await self.cloud_post_to_device(device, json_message, "state")

    @classmethod
    async def create_default(  # pylint: disable=too-many-arguments
        cls: Any,
        controller_data: ControllerData,
        cloud: CloudBackend | None,
        username: str = "",
        password: str = "",
    ) -> Account:
        """Create and initialize an account. Send login for access token."""

        acc: Account = Account(controller_data, cloud)
        acc.username = username
        acc.password = password

        await acc.init()
        return acc
