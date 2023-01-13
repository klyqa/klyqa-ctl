#!/usr/bin/env python3

"""Local and cloud connections"""
from __future__ import annotations
import argparse
from asyncio import AbstractEventLoop, CancelledError, Task
from collections import ChainMap
import datetime
import functools
import getpass
import httpx
import json
from typing import Any
import requests, uuid, json
from klyqa_ctl.account import Account
from klyqa_ctl.controller_data import ControllerData

from klyqa_ctl.devices.device import KlyqaDevice, format_uid
from klyqa_ctl.devices.light import KlyqaBulb
from klyqa_ctl.devices.vacuum import KlyqaVC
from klyqa_ctl.general.connections import PROD_HOST
from klyqa_ctl.general.general import LOGGER, EventQueuePrinter

from klyqa_ctl.devices.device import *
from klyqa_ctl.general.general import *
        
        
class CloudBackend:
    """Cloud backend"""
    
    def __init__(self, controller_data: ControllerData, account: Account,
        host: str = "", offline: bool = False) -> None:
        self._attr_controller_data: ControllerData = controller_data
        self._attr_account: Account = account
        self._attr_offline: bool = offline
        self._attr_host: str = PROD_HOST if not host else host
        self._attr_access_token: str = ""
        self._attr_devices: dict[str, KlyqaDevice] = account.devices

    @property
    def devices(self) -> dict[str, KlyqaDevice]:
        """Return or set the devices dictionary."""
        return self._attr_devices

    @property
    def access_token(self) -> str:
        """Return or set the cloud access token."""
        return self._attr_access_token

    @property
    def host(self) -> str:
        """Return or set the host."""
        return self._attr_host

    @property
    def offline(self) -> bool:
        """Return or set the offline attribute."""
        return self._attr_offline

    @property
    def account(self) -> Account:
        """Return or set the account object."""
        return self._attr_account

    @property
    def controller_data(self) -> ControllerData:
        """Return or set the controller data object."""
        return self._attr_controller_data
    
    def backend_connected(self) -> bool:
        return self.access_token != ""
    
    
    async def login_cache(self) -> bool:
        """Get cached account data for login and check existing username and password."""

        cached: bool
        if not self.account.username:
            try:
                user_name_cache: dict | None
                user_name_cache, cached = await async_json_cache(
                    None, f"last_username.json"
                )
                if cached and user_name_cache:
                    self.account.username = user_name_cache["username"]
                    LOGGER.info("Using Klyqa account %s.", self.account.username)
                else:
                    LOGGER.error("Username missing, username cache empty.")

                    if self.controller_data and self.controller_data.interactive_prompts:
                        self.account.username = input(
                            " Please enter your Klyqa Account username (will be cached for the script invoke): "
                        )
                    else:
                        LOGGER.info("Missing Klyqa account username. No login.")
                        return False
            except:
                return False
            
        try:
            acc_settings: dict | None
            acc_settings, cached = await async_json_cache(
                None, f"{self.account.username}.acc_settings.cache.json"
            )
            if cached:
                self.account.settings = acc_settings
                # self.account.username, self.account.password = (user_acc_cache["user"], user_acc_cache["password"])
                if self.account and self.account.settings and not self.account.password:
                    self.account.password = self.account.settings["password"]

            if not self.account.password:
                raise Exception()

        except:
            if self.controller_data and self.controller_data.interactive_prompts:
                self.account.password = getpass.getpass(
                    prompt=" Please enter your Klyqa Account password (will be saved): ",
                    stream=None,
                )
            else:
                LOGGER.error("Missing Klyqa account password. Login failed.")
                return False

        return True
    
    # async def _run_login
    
    async def login(self, print_onboarded_devices: bool = False) -> bool:
        """! Login on klyqa account, get account settings, get onboarded device profiles,
        print all devices if parameter set.

        Params:
            print_onboarded_devices:   print onboarded devices from the klyqa account to the stdout

        Returns:
            true:  on success of the login
            false: on error
        """
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        if not await self.login_cache():
            return False

        acc_settings_cache: dict = {}

        if not self.offline and (
            self.account.username is not None and self.account.password is not None
        ):
            login_response: httpx.Response | None = None
            cached: bool
            login_data: dict[str, str] = {
                "email": self.account.username,
                "password": self.account.password,
            }
            try:

                login_response = await self.request("/auth/login", json=login_data, timeout=10)

                if not login_response or (
                    login_response.status_code != 200
                    and login_response.status_code != 201
                ):
                    if login_response:
                        LOGGER.error(
                            str(login_response.status_code)
                            + ", "
                            + str(login_response.text)
                        )
                        raise Exception(login_response.text)
                    else:
                        raise Exception("missing login response")
                    
                login_json: dict = json.loads(login_response.text)
                self.access_token = str(login_json.get("accessToken"))
                
                acc_settings: dict[str, Any] | None = await self.request_beared("settings", timeout=30)
                if acc_settings:
                    self.account.settings = acc_settings

            except Exception as e:
                if self.account.settings:
                    LOGGER.info(
                        f"Error during login. Using account settings for account {self.account.username} from cache."
                    )
                else:
                    LOGGER.error(f"Unable to login into account {self.account.username}.")
                    return False

            if not self.account.settings:
                return False

            try:
                acc_settings_cache = {
                    **self.account.settings,
                    **{
                        "time_cached": datetime.datetime.now(),
                        "password": self.account.password,
                    },
                }

                """save current account settings in cache"""
                await async_json_cache(
                    acc_settings_cache, f"{self.account.username}.acc_settings.cache.json"
                )

                # await async_json_cache(
                #     {"user": self.account.username, "password": self.account.password}, f"last.user.account.json"
                # )
                # async with aiofiles.open(
                #     os.path.dirname(sys.argv[0]) + f"/last_username", mode="w"
                # ) as f:
                #     await f.write(self.account.username)

            except Exception as e:
                pass

        await async_json_cache({"username": self.account.username}, f"last_username.json")

        device_configs_cache: dict[Any, Any] | None

        try:
            klyqa_acc_string: str = "Klyqa account " + self.account.username + ". Onboarded devices:"
            sep_width: int = len(klyqa_acc_string)

            if print_onboarded_devices:
                print(sep_width * "-")
                print(klyqa_acc_string)
                print(sep_width * "-")

            queue_printer: EventQueuePrinter = EventQueuePrinter()

            def device_request_and_print(device_settings: dict[str, Any]) -> None:
                state_str: str = (
                    f'Name: "{device_settings["name"]}"'
                    + f'\tAES-KEY: {device_settings["aesKey"]}'
                    + f'\tUnit-ID: {device_settings["localDeviceId"]}'
                    + f'\tCloud-ID: {device_settings["cloudDeviceId"]}'
                    + f'\tType: {device_settings["productId"]}'
                )
                cloud_state: dict[str, Any] | None = None

                device: KlyqaDevice
                if ".lighting" in device_settings["productId"]:
                    device = KlyqaBulb()
                elif ".cleaning" in device_settings["productId"]:
                    device = KlyqaVC()
                else:
                    return
                device.u_id = format_uid(device_settings["localDeviceId"])
                device.acc_sets = device_settings

                self.devices[format_uid(device_settings["localDeviceId"])] = device

                async def req() -> dict[str, Any] | None:
                    try:
                        ret: dict[str, Any] | None = await self.request_beared(
                            f'device/{device_settings["cloudDeviceId"]}/state',
                            timeout=30,
                        )
                        return ret
                    except Exception as e:
                        return None

                if self.backend_connected():
                    try:
                        cloud_state = asyncio.run(req())
                        if cloud_state:
                            if "connected" in cloud_state:
                                state_str = (
                                    state_str
                                    + f'\tCloud-Connected: {cloud_state["connected"]}'
                                )
                            device.cloud.connected = cloud_state["connected"]

                            device.save_device_message(
                                {**cloud_state, **{"type": "status"}}
                            )
                        else:
                            raise
                    except:
                        LOGGER.info(f'No answer for cloud device state request {device_settings["localDeviceId"]}')

                if print_onboarded_devices:
                    queue_printer.print(state_str)

            device_state_req_threads = []

            product_ids: set[str] = set()
            if self.account.settings and "devices" in self.account.settings:
                for device_sets in self.account.settings["devices"]:
                    
                    
                    thread: Thread = Thread(target=device_request_and_print, args=(device_sets,))
                    device_state_req_threads.append(thread)

                    if isinstance(self.controller_data.aes_keys, dict):
                        self.controller_data.aes_keys[
                            format_uid(device_sets["localDeviceId"])
                        ] = bytes.fromhex(device_sets["aesKey"])
                    product_ids.add(device_sets["productId"])

            for t in device_state_req_threads:
                t.start()
            for t in device_state_req_threads:
                t.join()

            queue_printer.stop()

            if not self.backend_connected():
                if not self.account.device_configs:
                    device_configs_cache, cached = await async_json_cache(
                        None, "device.configs.json"
                    )
                    if (
                        cached and not self.account.device_configs
                    ):
                        # using again not device_configs check cause asyncio await scheduling
                        LOGGER.info("Using devices config cache.")
                        if device_configs_cache:
                            self.account.device_configs = device_configs_cache

            elif self.backend_connected():

                def get_conf(id: str, device_configs: dict[str, Any]) -> None:
                    async def req() -> dict[str, Any] | None:
                        try:
                            ret: dict[str, Any] | None = await self.request_beared("config/product/" + id, timeout=30)
                            return ret
                        except:
                            return None

                    config: dict[str, Any] | None = asyncio.run(req())
                    if config:
                        device_config: Device_config = config
                        device_configs[id] = device_config

                if self.account.settings and product_ids:
                    threads: list[Thread] = [
                        Thread(target=get_conf, args=(i, self.account.device_configs))
                        for i in product_ids
                    ]
                    for t in threads:
                        LOGGER.debug(
                            "Try to request device config for "
                            + t._args[0]
                            + " from server."
                        )
                        t.start()
                    for t in threads:
                        t.join()
                
                device_configs_cache, cached = await async_json_cache(
                    self.account.device_configs, "device.configs.json"
                )
                if cached and device_configs_cache:
                    self.account.device_configs = device_configs_cache
                    LOGGER.info("No server reply for device configs. Using cache.")

            for uid in self.devices:
                if (
                    "productId" in self.devices[uid].acc_sets
                    and self.devices[uid].acc_sets["productId"] in self.account.device_configs
                ):
                    self.devices[uid].read_device_config(device_config = self.account.device_configs[
                        self.devices[uid].acc_sets["productId"]
                    ])
        except Exception as e:
            LOGGER.error("Error during login to klyqa: " + str(e))
            LOGGER.debug(f"{traceback.format_exc()}")
            return False
        return True

    def get_header_default(self) -> dict[str, str]:
        """Get default request header for cloud request."""
        header: dict[str, str] = {
            "X-Request-Id": str(uuid.uuid4()),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "accept-encoding": "gzip, deflate, utf-8",
        }
        return header

    def get_beared_request_header(self) -> dict[str, str]:
        """Set default request header with cloud access token."""
        return {
            **self.get_header_default(),
            **{"Authorization": "Bearer " + self.access_token},
        }
        
 
    async def request(self, url: str, headers: TypeJSON | None = None, **kwargs: Any) -> httpx.Response | None:
        response: httpx.Response | None = None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request("GET", url=self.host + "/" + url,                                    
                    headers=headers,
                    **kwargs)
                
        except EnvironmentError as ex: # parent of IOError, OSError *and* WindowsError where available
            LOGGER.error("Environment error occured during send request to cloud backend!")
            LOGGER.debug(f"{traceback.format_exc()}")
        except httpx.HTTPError as e:
            LOGGER.error("Connection error occured during send request to cloud backend!")
            LOGGER.debug(f"{traceback.format_exc()}")
            
        return response

    async def request_beared(self, url: str, **kwargs: Any) -> TypeJSON | None:
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        answer: TypeJSON | None = None
        response: httpx.Response | None = await self.request(self.host + "/" + url,
            self.get_beared_request_header() if self.access_token else self.get_header_default(), **kwargs)
        
        if not response:
            LOGGER.debug("No response from cloud request.")
            return None
        if response.status_code != 200:
            LOGGER.debug("Unvalid response from cloud request.")
            raise Exception(response.text)
        try:
            answer = json.loads(response.text)
        except json.JSONDecodeError as err:
            LOGGER.error(f"{err.msg}")
            LOGGER.debug(f"{traceback.format_exc()} {err.msg}")
            answer = None
        return answer
        
    async def request_account_settings_eco(self, scan_interval: int = 60) -> bool:
        if not await self.account.settings_lock.acquire():
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
            self.account.settings_lock.release()
        return ret

    async def request_account_settings(self) -> None:
        try:
            acc_settings: dict[str, Any] | None = await self.request_beared("settings")
            if acc_settings:
                self.account.settings = acc_settings
        except:
            LOGGER.debug(f"{traceback.format_exc()}")


    async def update_device_configs(self) -> None:
        """Request the account settings from the cloud backend."""
        
        product_ids: set[str] = {
            device.ident.product_id
            for uid, device in self.devices.items()
            if device.ident and device.ident.product_id
        }

        for product_id in list(product_ids):
            if self.account.device_configs and product_id in self.account.device_configs:
                continue
            LOGGER.debug("Try to request device config from server.")
            try:
                config: TypeJSON | None = await self.request_beared(
                    "config/product/" + product_id,
                    timeout=30,
                )
                device_config: Device_config | None = config
                if not isinstance(self.account.device_configs, dict):
                    self.account.device_configs = {}
                self.account.device_configs[product_id] = device_config
            except:
                LOGGER.debug(f"{traceback.format_exc()}")

    async def request_post_beared(self, url: str, **kwargs: Any) -> TypeJSON | None:
        """Post requests with."""
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        answer: TypeJSON | None = None
        try:
            response: httpx.Response = await loop.run_in_executor(
                None,
                functools.partial(
                    requests.post,
                    self.host + "/" + url,
                    headers=self.get_beared_request_header(),
                    **kwargs,
                ),
            )
            if response.status_code != 200:
                raise Exception(response.text)
            answer = json.loads(response.text)
        except:
            LOGGER.debug(f"{traceback.format_exc()}")
            answer = None
        return answer

    async def cloud_send(self,
        args: argparse.Namespace,
        target_device_uids: set[str],
        to_send_device_uids: set[str],
        timeout_ms: int,
        message_queue_tx_state_cloud: list,
        message_queue_tx_command_cloud: list) -> bool:
        """Cloud message processing."""
        queue_printer: EventQueuePrinter = EventQueuePrinter()
        response_queue: list[Any] = []
        
        success: bool = False

        async def _cloud_post(
            device: KlyqaDevice, json_message: dict[str, Any], target: str
        ) -> None:
            cloud_device_id: str = device.acc_sets["cloudDeviceId"]
            unit_id: str = format_uid(device.acc_sets["localDeviceId"])
            LOGGER.info(
                f"Post {target} to the device '{cloud_device_id}' (unit_id: {unit_id}) over the cloud."
            )
            resp = {
                cloud_device_id: await self.request_post_beared(
                    url=f"device/{cloud_device_id}/{target}",
                    json=json_message,
                )
            }
            resp_print: str = ""
            name: str = device.u_id
            if device.acc_sets and "name" in device.acc_sets:
                name = device.acc_sets["name"]
            resp_print = f'Device "{name}" cloud response:'
            resp_print = json.dumps(resp, sort_keys=True, indent=4)
            device.cloud.received_packages.append(resp)
            response_queue.append(resp_print)
            queue_printer.print(resp_print)

        async def cloud_post(device: KlyqaDevice, json_message: dict[str, Any], target: str) -> int:
            if not await device.use_lock():
                LOGGER.error(
                    f"Couldn't get use lock for device {device.get_name()})"
                )
                return 1
            try:
                await _cloud_post(device, json_message, target)
            except CancelledError as e:
                LOGGER.error(
                    f"Cancelled cloud send "
                    + (device.u_id if device.u_id else "")
                    + "."
                )
            finally:
                await device.use_unlock()
            return 0

        started: datetime.datetime = datetime.datetime.now()
        # timeout_ms = 30000

        async def process_cloud_messages(target_uids: set[str]) -> None:

            loop: AbstractEventLoop = asyncio.get_event_loop()
            threads: list[Any] = []
            target_devices: list[KlyqaDevice] = [
                b
                for b in self.devices.values()
                for t in target_uids
                if b.u_id == t
            ]

            def create_post_threads(target: str, msg: dict[str, Any]) -> list[tuple[Task[int], KlyqaDevice]]:
                return [
                    (loop.create_task(cloud_post(b, msg, target)), b)
                    for b in target_devices
                ]

            state_payload_message = dict(
                ChainMap(*message_queue_tx_state_cloud)
            )
            # state_payload_message = json.loads(*message_queue_tx_state_cloud) if message_queue_tx_state_cloud else ""

            command_payload_message = dict(
                ChainMap(*message_queue_tx_command_cloud)
            )
            # command_payload_message = json.loads(*message_queue_tx_command_cloud) if message_queue_tx_command_cloud else ""
            if state_payload_message:
                threads.extend(
                    create_post_threads(
                        "state", {"payload": state_payload_message}
                    )
                )
            if command_payload_message:
                threads.extend(
                    create_post_threads("command", command_payload_message)
                )

            count: int = 0
            timeout: float = timeout_ms / 1000
            for t, device in threads:
                count = count + 1
                """wait at most timeout_ms wanted minus seconds elapsed since sending"""
                try:
                    await asyncio.wait_for(
                        t,
                        timeout=timeout
                        - (datetime.datetime.now() - started).seconds,
                    )
                except asyncio.TimeoutError:
                    LOGGER.error(f'Timeout for "{device.get_name()}"!')
                    t.cancel()
                except:
                    LOGGER.debug(f"{traceback.format_exc()}")

        await process_cloud_messages(
            target_device_uids if args.cloud else to_send_device_uids
        )
        """if there are still target devices that the local send couldn't reach, try send the to_send_device_uids via cloud"""

        queue_printer.stop()

        if len(response_queue):
            success = True
        return success
            
    
    async def shutdown(self) -> None:
        """Logout again from klyqa account."""
        if self.access_token:
            try:
                requests.post(
                    self.host + "/auth/logout", headers=self.get_header_default()
                )
                self.access_token = ""
            except Exception:
                LOGGER.warning("Couldn't logout.")
                