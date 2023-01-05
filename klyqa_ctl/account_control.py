 #!/usr/bin/env python3
"""Control all actions for the account."""

from __future__ import annotations
import datetime
import getpass
from typing import Any
from klyqa_ctl.account import Account
from klyqa_ctl.communication.cloud import CloudBackend
from klyqa_ctl.communication.local import Local_communicator

from klyqa_ctl.devices.device import KlyqaDevice
from klyqa_ctl.general.general import LOGGER

from klyqa_ctl.devices.device import *
from klyqa_ctl.general.general import *


class Account_control:
    """Cloud backend"""
    
    def __init__(self, devices, account: Account, cloud_backend: CloudBackend, local_communicator: Local_communicator,
                 interactive_prompts: bool) -> None:
        # self.offline = offline
        self.devices: dict[str, KlyqaDevice] = devices
        self.account: Account = account
        self.cloud_backend: CloudBackend = cloud_backend
        self.local_communicator: Local_communicator = local_communicator
        self.interactive_prompts: bool = interactive_prompts


    async def request_account_settings_eco(self, scan_interval: int = 60) -> bool:
        """Request the account settings from the cloud backend only within a scan interval."""
        if not await self.account.__settings_lock.acquire():
            return False
        ret: bool = True
        try:
            now: datetime.datetime = datetime.datetime.now()
            if not self.account._settings_loaded_ts or (
                now - self.account._settings_loaded_ts
                >= datetime.timedelta(seconds=scan_interval)
            ):
                """look that the settings are loaded only once in the scan interval"""
                await self.request_account_settings()
        finally:
            self.account.__settings_lock.release()
        return ret


    async def request_account_settings(self) -> None:
        """Request the account settings from the cloud backend."""
        try:
            acc_settings: dict[str, Any] | None = await self.cloud_backend.request("settings")
            if acc_settings:
                self.acc_settings = acc_settings
        except:
            LOGGER.debug(f"{traceback.format_exc()}")


    async def login_cache(self) -> bool:
        """Login cache."""

        if not self.account.username:
            try:
                user_name_cache: dict
                cached: bool
                user_name_cache, cached = await async_json_cache(
                    None, f"last_username.json"
                )
                if cached:
                    self.account.username = user_name_cache["username"]
                    LOGGER.info("Using Klyqa account %s.", self.account.username)
                else:
                    LOGGER.error("Username missing, username cache empty.")

                    if self.interactive_prompts:
                        self.account.username = input(
                            " Please enter your Klyqa Account username (will be cached for the script invoke): "
                        )
                    else:
                        LOGGER.info("Missing Klyqa account username. No login.")
                        return False

                # async with aiofiles.open(
                #     os.path.dirname(sys.argv[0]) + f"/last_username", mode="r"
                # ) as f:
                #     self.account.username = str(await f.readline()).strip()
            except:
                return False
            
        try:
            acc_settings: dict
            cached: bool
            acc_settings, cached = await async_json_cache(
                None, f"{self.account.username}.acc_settings.cache.json"
            )
            if cached:
                self.acc_settings = acc_settings
                # self.account.username, self.account.password = (user_acc_cache["user"], user_acc_cache["password"])
                if not self.account.password:
                    self.account.password = self.acc_settings["password"]

            if not self.account.password:
                raise Exception()

            # async with aiofiles.open(
            #     os.path.dirname(sys.argv[0]) + f"/last_username", mode="r"
            # ) as f:
            #     self.account.username = str(await f.readline()).strip()
        except:
            if self.interactive_prompts:
                self.account.password = getpass.getpass(
                    prompt=" Please enter your Klyqa Account password (will be saved): ",
                    stream=None,
                )
            else:
                LOGGER.error("Missing Klyqa account password. Login failed.")
                return False

        return True
    
    def backend_connected(self) -> bool:
        return not self.cloud_backend or self.cloud_backend.access_token != ""
    
    
    async def update_device_configs(self) -> None:
        """Request the account settings from the cloud backend."""
        
        product_ids: set[str] = {
            device.ident.product_id
            for uid, device in self.devices.items()
            if device.ident and device.ident.product_id
        }

        for product_id in list(product_ids):
            if self.device_configs and product_id in self.device_configs:
                continue
            LOGGER.debug("Try to request device config from server.")
            try:
                config: TypeJSON | None = await self.cloud_backend.request(
                    "config/product/" + product_id,
                    timeout=30,
                )
                device_config: Device_config | None = config
                if not isinstance(self.device_configs, dict):
                    self.device_configs: dict[str, Any] = {}
                self.device_configs[product_id] = device_config
            except:
                LOGGER.debug(f"{traceback.format_exc()}")


    async def load_username_cache(self) -> None:
        acc_settings_cache, cached = await async_json_cache(
            None, "last.acc_settings.cache.json"
        )

        self.account.username_cached = cached

        if cached:
            LOGGER.info(f"No username or no password given using cache.")
            if not acc_settings_cache or (
                self.account.username and list(acc_settings_cache.keys())[0] != self.account.username
            ):
                e = f"Account settings are from another account than {self.account.username}."
                LOGGER.error(e)
                raise ValueError(e)
            else:
                try:
                    self.account.username = list(acc_settings_cache.keys())[0]
                    self.account.password = acc_settings_cache[self.account.username]["password"]
                    e = f"Using cache account settings from account {self.account.username}."
                    LOGGER.info(e)
                except:
                    e = f"Could not load cached account settings."
                    LOGGER.error(e)
                    raise ValueError(e)
        else:
            e = f"Could not load cached account settings."
            LOGGER.error(e)
            raise ValueError(e)

    async def shutdown(self) -> None:
        """Logout again from klyqa account."""
                
        await self.local_communicator.shutdown()
        