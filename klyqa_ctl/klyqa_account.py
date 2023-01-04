#!/usr/bin/env python3
"""Klyqa account."""
from __future__ import annotations

import getpass
import socket
import sys
import json
import datetime
import argparse
import select
import logging
import time
from typing import TypeVar, Any, TypedDict
from xml.dom.pulldom import default_bufsize

import requests, uuid, json
from threading import Thread, Event
from collections import ChainMap
from enum import Enum
import asyncio, aiofiles
import functools, traceback
from asyncio.exceptions import CancelledError, TimeoutError
from collections.abc import Callable
from klyqa_ctl.communication.local import AES_KEYs, Data_communicator, LocalConnection, send_msg

from klyqa_ctl.devices.device import *
from klyqa_ctl.devices.light import *
from klyqa_ctl.devices.light.commands import add_command_args_bulb, process_args_to_msg_lighting
from klyqa_ctl.devices.vacuum import *
from klyqa_ctl.devices.vacuum.commands import process_args_to_msg_cleaner
from klyqa_ctl.general.connections import *
from klyqa_ctl.general.general import *
from klyqa_ctl.general.message import *
from klyqa_ctl.general.parameters import get_description_parser

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
except:
    from Crypto.Cipher import AES  # provided by pycryptodome

from typing import TypeVar

class Klyqa_account:
    """

    Klyqa account
    * rest access token
    * devices
    * account settings
    * local communication
    * cloud communication

    """

    host: str
    access_token: str
    username: str
    password: str
    username_cached: bool

    devices: dict[str, KlyqaDevice]

    acc_settings: TypeJSON | None
    acc_settings_cached: bool

    __acc_settings_lock: asyncio.Lock
    _settings_loaded_ts: datetime.datetime | None

    __send_loop_sleep: asyncio.Task | None
    __tasks_done: list[tuple[asyncio.Task, datetime.datetime, datetime.datetime]]
    __tasks_undone: list[tuple[asyncio.Task, datetime.datetime]]
    __read_tcp_task: asyncio.Task | None
    message_queue: dict[str, list[Message]]
    search_and_send_loop_task: asyncio.Task | None

    # Set of current accepted connections to an IP. One connection is most of the time
    # enough to send all messages for that device behind that connection (in the aes send message method).
    # If connection is currently finishing due to sent messages and no messages left for that device and a new
    # message appears in the queue, send a new broadcast and establish a new connection.
    #
    current_addr_connections: set[str] = set()

    def __init__(
        self,
        data_communicator: Data_communicator,
        username: str = "",
        password: str = "",
        host: str = "",
        interactive_prompts: bool = False,
        offline: bool = False,
        device_configs: dict = {},
    ) -> None:
        """! Initialize the account with the login data, tcp, udp datacommunicator and tcp
        communication tasks."""
        self.username = username
        self.password = password
        self.devices = {}
        self.acc_settings = {}
        self.access_token: str = ""
        self.host = PROD_HOST if not host else host
        self.username_cached = False
        self.acc_settings_cached = False
        self.__acc_settings_lock = asyncio.Lock()
        self._settings_loaded_ts = None
        
        self.data_communicator: Data_communicator = data_communicator
        self.offline = offline
        self.device_configs = device_configs

    def backend_connected(self) -> bool:
        return self.access_token != ""


    async def request_account_settings_eco(self, scan_interval: int = 60) -> bool:
        if not await self.__acc_settings_lock.acquire():
            return False
        ret: bool = True
        try:
            now: datetime.datetime = datetime.datetime.now()
            if not self._settings_loaded_ts or (
                now - self._settings_loaded_ts
                >= datetime.timedelta(seconds=scan_interval)
            ):
                """look that the settings are loaded only once in the scan interval"""
                await self.request_account_settings()
        finally:
            self.__acc_settings_lock.release()
        return ret
    
    
    async def update_device_configs(self):
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
                config = await self.request(
                    "config/product/" + product_id,
                    timeout=30,
                )
                device_config: Device_config | None = config
                if not isinstance(self.device_configs, dict):
                    self.device_configs = {}
                self.device_configs[product_id] = device_config
            except:
                LOGGER.debug(f"{traceback.format_exc()}")


    async def load_username_cache(self) -> None:
        acc_settings_cache, cached = await async_json_cache(
            None, "last.acc_settings.cache.json"
        )

        self.username_cached = cached

        if cached:
            LOGGER.info(f"No username or no password given using cache.")
            if not acc_settings_cache or (
                self.username and list(acc_settings_cache.keys())[0] != self.username
            ):
                e = f"Account settings are from another account than {self.username}."
                LOGGER.error(e)
                raise ValueError(e)
            else:
                try:
                    self.username = list(acc_settings_cache.keys())[0]
                    self.password = acc_settings_cache[self.username]["password"]
                    e = f"Using cache account settings from account {self.username}."
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
        if self.access_token:
            try:
                requests.post(
                    self.host + "/auth/logout", headers=self.get_header_default()
                )
                self.access_token = ""
            except Exception:
                LOGGER.warning("Couldn't logout.")
                
        await self.data_communicator.shutdown()
        

    async def request_account_settings(self) -> None:
        try:
            acc_settings: dict[str, Any] | None = await self.request("settings")
            if acc_settings:
                self.acc_settings = acc_settings
        except:
            LOGGER.debug(f"{traceback.format_exc()}")
        
    
    async def select_device(self, args, send_started_local) -> str | set[str]:
        """Interactive select device."""
        
        print(sep_width * "-")
        # devices_working = {k: v for k, v in self.devices.items() if v.local.aes_key_confirmed}
        devices_working: dict[str, KlyqaDevice] = {
            u_id: device
            for u_id, device in self.devices.items()
            if (
                (
                    args.type == DeviceType.lighting.name
                    and isinstance(device, KlyqaBulb)
                )
                or (
                    args.type == DeviceType.cleaner.name
                    and isinstance(device, KlyqaVC)
                )
            )
            and (
                (
                    device.status
                    and device.status.ts
                    and isinstance(device.status.ts, datetime.datetime)
                    and device.status.ts > send_started_local
                )
                or (
                    (args.cloud or args.tryLocalThanCloud)
                    and device.cloud
                    and device.cloud.connected
                )
            )
        }
        print(
            "Found "
            + str(len(devices_working))
            + " "
            + ("device" if len(devices_working) == 1 else "devices")
            + " with working aes keys"
            + (" (dev aes key)" if args.dev else "")
            + "."
        )
        if len(devices_working) <= 0:
            return "no_devices"
        
        print(sep_width * "-")
        count: int = 1
        device_items: list[KlyqaDevice] = list(devices_working.values())

        if device_items:
            print(
                "Status attributes: ("
                + get_obj_attrs_as_string(KlyqaBulbResponseStatus)
                + ") (local IP-Address)"
            )
            print("")

        for device in device_items:
            name: str = f"Unit ID: {device.u_id}"
            if device.acc_sets and "name" in device.acc_sets:
                name = device.acc_sets["name"]
            address: str = (
                f" (local {device.local_addr['ip']}:{device.local_addr['port']})"
                if device.local_addr["ip"]
                else ""
            )
            cloud: str = (
                f" (cloud connected)" if device.cloud.connected else ""
            )
            status: str = (
                f" ({device.status})"
                if device.status
                else " (no status)"
            )
            print(f"{count}) {name}{status}{address}{cloud}")
            count = count + 1

        if self.devices:
            print("")
            device_num_s: str = input(
                "Choose bulb number(s) (comma seperated) a (all),[1-9]*{,[1-9]*}*: "
            )
            target_device_uids_lcl: set[str] = set()
            if device_num_s == "a":
                return set(b.u_id for b in device_items)
            else:
                for bulb_num in device_num_s.split(","):
                    bulb_num_nr: int = int(bulb_num)
                    if bulb_num_nr > 0 and bulb_num_nr < count:
                        target_device_uids_lcl.add(
                            device_items[bulb_num_nr - 1].u_id
                        )
            return target_device_uids_lcl

        """ no devices found. Exit script. """
        sys.exit(0)
            
    
    def device_name_to_uid(self, args: argparse.Namespace, target_device_uids: set[str]) -> bool:
        """Set target device uid by device name argument."""
        
        if not self.acc_settings:
            LOGGER.error(
                'Missing account settings to resolve device name  "'
                + args.device_name
                + '"to unit id.'
            )
            return False
        dev: list[str] = [
            format_uid(device["localDeviceId"])
            for device in self.acc_settings["devices"]
            if device["name"] == args.device_name
        ]
        if not dev:
            LOGGER.error(
                'Device name "'
                + args.device_name
                + '" not found in account settings.'
            )
            return False
        else:
            target_device_uids.add(format_uid(dev[0]))
        return True
    
    
    async def send_to_devices(
        self,
        args: argparse.Namespace,
        args_in: list[Any],
        udp: socket.socket | None = None,
        tcp: socket.socket | None = None,
        timeout_ms: int = 5000,
        async_answer_callback: Callable[[Message, str], Any] | None = None,
    ) -> str | bool | int | set:
        """Collect the messages for the devices to send to

        Args:
            args (Argsparse): Parsed args object
            args_in (list): List of arguments parsed to the script call
            timeout_ms (int, optional): Timeout to send. Defaults to 5000.

        Raises:
            Exception: Network or file errors

        Returns:
            bool: True if succeeded.
        """
        if not udp:
            udp = self.data_communicator.udp
        if not tcp:
            tcp = self.data_communicator.tcp
        try:
            global sep_width

            loop = asyncio.get_event_loop()

            send_started: datetime.datetime = datetime.datetime.now()

            add_command_args_ch: dict[str, Callable[..., Any]] = {
                DeviceType.lighting.name: add_command_args_bulb,
                DeviceType.cleaner.name: add_command_args_cleaner,
            }
            add_command_args: Callable[..., Any] = add_command_args_ch[args.type]

            if args.dev:
                args.local = True
                args.tryLocalThanCloud = False
                args.cloud = False

            if args.debug:
                LOGGER.setLevel(level=logging.DEBUG)
                logging_hdl.setLevel(level=logging.DEBUG)

            if args.cloud or args.local:
                args.tryLocalThanCloud = False

            if args.aes is not None:
                AES_KEYs["all"] = bytes.fromhex(args.aes[0])

            target_device_uids: set[str] = set()

            message_queue_tx_local: list[Any] = []
            message_queue_tx_state_cloud: list[Any] = []
            message_queue_tx_command_cloud: list[Any] = []

            if args.device_name is not None:
                if not self.device_name_to_uid(args, target_device_uids):
                    return False

            if args.device_unitids is not None:
                target_device_uids = set(
                    map(format_uid, set(args.device_unitids[0].split(",")))
                )
                print("Send to device: " + ", ".join(args.device_unitids[0].split(",")))

            if not args.selectDevice and self.backend_connected():
                await self.update_device_configs()

            ### device specific commands ###

            async def send_to_devices_cb(args: argparse.Namespace) -> str | bool | int | set:
                """Send to devices callback for discover of devices option"""
                return await self.send_to_devices(
                    args,
                    args_in,
                    udp=udp,
                    tcp=tcp,
                    timeout_ms=3500,
                )

            scene: list[str] = []
            if args.type == DeviceType.lighting.name:
                await process_args_to_msg_lighting(
                    args,
                    args_in,
                    send_to_devices_cb,
                    message_queue_tx_local,
                    message_queue_tx_command_cloud,
                    message_queue_tx_state_cloud,
                    scene,
                )
            elif args.type == DeviceType.cleaner.name:
                await process_args_to_msg_cleaner(
                    args,
                    args_in,
                    send_to_devices_cb,
                    message_queue_tx_local,
                    message_queue_tx_command_cloud,
                    message_queue_tx_state_cloud,
                )
            else:
                LOGGER.error("Missing device type.")
                return False

            success: bool = True
            to_send_device_uids: set[str] = set()
            
            if args.local or args.tryLocalThanCloud:
                if args.passive:
                    if udp:
                        LOGGER.debug("Waiting for UDP broadcast")
                        data, address = udp.recvfrom(4096)
                        LOGGER.debug(
                            "\n\n 2. UDP server received: ",
                            data.decode("utf-8"),
                            "from",
                            address,
                            "\n\n",
                        )

                        LOGGER.debug("3a. Sending UDP ack.\n")
                        udp.sendto("QCX-ACK".encode("utf-8"), address)
                        time.sleep(1)
                        LOGGER.debug("3b. Sending UDP ack.\n")
                        udp.sendto("QCX-ACK".encode("utf-8"), address)
                else:


                    send_started_local: datetime.datetime = datetime.datetime.now()

                    if args.discover:
                        await self.data_communicator.discover_devices(args, message_queue_tx_local, target_device_uids)

                    msg_wait_tasks: dict[str, asyncio.Task] = {}

                    to_send_device_uids = target_device_uids.copy()

                    async def sl(uid) -> None:
                        """Sleep task for timeout."""
                        try:
                            await asyncio.sleep(timeout_ms / 1000)
                        except CancelledError as e:
                            LOGGER.debug(f"sleep uid {uid} cancelled.")
                        except Exception as e:
                            pass

                    for uid in target_device_uids:
                        try:
                            msg_wait_tasks[uid] = loop.create_task(sl(uid))
                        except Exception as e:
                            pass

                    async def async_answer_callback_local(msg, uid) -> None:
                        if msg and msg.msg_queue_sent:
                            LOGGER.debug(f"{uid} msg callback.")

                        if uid in to_send_device_uids:
                            to_send_device_uids.remove(uid)
                        try:
                            msg_wait_tasks[uid].cancel()
                        except:
                            LOGGER.debug(f"{traceback.format_exc()}")
                        if async_answer_callback:
                            await async_answer_callback(msg, uid)

                    for uid in target_device_uids:
                        
                        await self.data_communicator.set_send_message(
                            send_msgs = message_queue_tx_local.copy(),
                            target_device_uid = uid,
                            args = args,
                            callback=async_answer_callback_local,
                            time_to_live_secs=(timeout_ms / 1000),
                        )

                    for uid in target_device_uids:
                        try:
                            LOGGER.debug(f"wait for send task {uid}.")
                            await asyncio.wait([msg_wait_tasks[uid]])
                            LOGGER.debug(f"wait for send task {uid} end.")
                        except CancelledError as e:
                            LOGGER.debug(f"sleep wait for uid {uid} cancelled.")
                        except Exception as e:
                            pass

                    LOGGER.debug(f"wait for all target device uids done.")

                    if args.selectDevice:
                        return await self.select_device(args, send_started_local)

                if target_device_uids and len(to_send_device_uids) > 0:
                    """error"""
                    sent_locally_error: str = (
                        "The commands " + str([f'{k}={v}' for k, v in vars(args).items() if v])
                        + " failed to send locally to the device(s): "
                        + ", ".join(to_send_device_uids)
                    )
                    if args.tryLocalThanCloud:
                        LOGGER.info(sent_locally_error)
                    else:
                        LOGGER.error(sent_locally_error)
                    success = False

            if args.cloud or args.tryLocalThanCloud:
                success = await self.cloud_send(args, target_device_uids, to_send_device_uids, timeout_ms, message_queue_tx_state_cloud, message_queue_tx_command_cloud)

            if success and scene:
                scene_start_args: list[str] = [
                    args.type,
                    "--routine_id",
                    "0",
                    "--routine_start",
                ]

                orginal_args_parser: argparse.ArgumentParser = get_description_parser()
                scene_start_args_parser: argparse.ArgumentParser = get_description_parser()

                add_config_args(parser=orginal_args_parser)
                add_config_args(parser=scene_start_args_parser)
                add_command_args(parser=scene_start_args_parser)

                original_config_args_parsed, _ = orginal_args_parser.parse_known_args(
                    args=args_in
                )

                scene_start_args_parsed = scene_start_args_parser.parse_args(
                    scene_start_args, namespace=original_config_args_parsed
                )

                async def async_print_answer(msg: Message, uid: str) -> None:
                    print(f"{uid}: ")
                    if msg:
                        try:
                            LOGGER.info(f"Answer received from {uid}.")
                            print(
                                f"{json.dumps(json.loads(msg.answer), sort_keys=True, indent=4)}"
                            )
                        except:
                            LOGGER.debug(f"{traceback.format_exc()}")
                    else:
                        LOGGER.error(f"Error no message returned from {uid}.")

                ret: str | bool | int | set = await self.send_to_devices(
                    scene_start_args_parsed,
                    args_in,
                    udp = udp,
                    tcp = tcp,
                    timeout_ms = timeout_ms
                    - int((datetime.datetime.now() - send_started).total_seconds())
                    * 1000,
                    async_answer_callback=async_print_answer,
                )

                if isinstance(ret, bool) and ret:
                    success = True
                else:
                    LOGGER.error(f"Couldn't start scene {scene[0]}.")
                    success = False

            return success
        except Exception as e:
            logger_debug_task(f"{traceback.format_exc()}")
            return False
    

    async def send_to_devices_wrapped(self, args_parsed, args_in, timeout_ms=5000) -> int:
        """Set up broadcast port and tcp reply connection port."""

        if args_parsed.cloud or args_parsed.local:
            args_parsed.tryLocalThanCloud = False

        if args_parsed.debug:
            LOGGER.setLevel(level=logging.DEBUG)
            logging_hdl.setLevel(level=logging.DEBUG)

        if args_parsed.dev:
            AES_KEYs["dev"] = AES_KEY_DEV

        local_communication = args_parsed.local or args_parsed.tryLocalThanCloud

        if local_communication:
            if not await self.data_communicator.bind_ports():
                return 1

        exit_ret: int = 0

        async def async_answer_callback(msg, uid) -> None:
            print(f"{uid}: ")
            if msg:
                try:
                    LOGGER.info(f"Answer received from {uid}.")
                    print(
                        f"{json.dumps(json.loads(msg.answer), sort_keys=True, indent=4)}"
                    )
                except:
                    LOGGER.debug(f"{traceback.format_exc()}")
            else:
                LOGGER.error(f"Error no message returned from {uid}.")

        if not await self.send_to_devices(
            args_parsed,
            args_in,
            udp = self.data_communicator.udp,
            tcp = self.data_communicator.tcp,
            timeout_ms = timeout_ms,
            async_answer_callback = async_answer_callback,
        ):
            exit_ret = 1

        LOGGER.debug("Closing ports")
        if local_communication or self.data_communicator:
            self.data_communicator.shutdown()

        return exit_ret