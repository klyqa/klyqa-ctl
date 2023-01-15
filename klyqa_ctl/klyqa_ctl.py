#!/usr/bin/env python3
"""Klyqa control client."""
from __future__ import annotations

###################################################################
#
# Interactive Klyqa Control commandline client
#
# Company: QConnex GmbH / Klyqa
# Author: Frederick Stallmeyer
#
# E-Mail: frederick.stallmeyer@gmx.de
#
# nice to haves/missing:
#   -   list cloud connected devices in discovery.
#   -   offer for selected devices possible commands and arguments in interactive
#       mode based on their device profile
#   -   Implementation for the different device config profile versions and
#       check on send.
#   -   start scene support in cloud mode
#
# current bugs:
#  - vc1 interactive command selection support.
#  - interactive light selection, command not applied
#
###################################################################

import random
import sys
import json
import datetime
import argparse
import logging
import time
from typing import Any

import json
import asyncio
import traceback
from asyncio.exceptions import CancelledError
from collections.abc import Callable
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.communication.cloud import CloudBackend
from klyqa_ctl.communication.local.communicator import LocalCommunicator

from klyqa_ctl.devices.device import *
from klyqa_ctl.devices.light import *
from klyqa_ctl.devices.light.commands import add_command_args_bulb, process_args_to_msg_lighting
from klyqa_ctl.devices.light.response_status import ResponseStatus
from klyqa_ctl.devices.vacuum import *
from klyqa_ctl.devices.vacuum.commands import process_args_to_msg_cleaner
from klyqa_ctl.general.connections import *
from klyqa_ctl.general.general import *
from klyqa_ctl.general.message import *
from klyqa_ctl.general.parameters import get_description_parser
from klyqa_ctl.account import Account

class Client:
    """Client"""

    def __init__(
        self,
        controller_data: ControllerData,
        local_communicator: LocalCommunicator | None,
        cloud_backend: CloudBackend | None, 
        account: Account | None,
    ) -> None:
        """! Initialize the account with the login data, tcp, udp datacommunicator and tcp
        communication tasks."""
        self._attr_controller_data: ControllerData = controller_data
        self._attr_local_communicator: LocalCommunicator | None = local_communicator 
        self._attr_account: Account | None = account
        self._attr_devices: dict[str, KlyqaDevice] = dict()
        self._attr_cloud_backend: CloudBackend | None = cloud_backend

    @property
    def controller_data(self) -> ControllerData:
        return self._attr_controller_data
    
    @controller_data.setter
    def controller_data(self, controller_data: ControllerData) -> None:
        self._attr_controller_data = controller_data

    @property
    def local_communicator(self) -> LocalCommunicator | None:
        return self._attr_local_communicator
    
    @local_communicator.setter
    def local_communicator(self, local_communicator: LocalCommunicator | None ) -> None:
        self._attr_local_communicator = local_communicator

    @property
    def account(self) -> Account | None:
        return self._attr_account
    
    @account.setter
    def account(self, account: Account) -> None:
        self._attr_account = account

    @property
    def devices(self) -> dict[str, KlyqaDevice]:
        return self._attr_devices
    
    @devices.setter
    def devices(self, devices: dict[str, KlyqaDevice]) -> None:
        self._attr_devices = devices

    @property
    def cloud_backend(self) -> CloudBackend | None:
        return self._attr_cloud_backend
    
    @cloud_backend.setter
    def cloud_backend(self, cloud_backend: CloudBackend) -> None:
        self._attr_cloud_backend = cloud_backend

    def backend_connected(self) -> bool:
        if self.cloud_backend:
            return bool(self.cloud_backend.access_token != "")
        return False

    async def shutdown(self) -> None:
        """Logout again from klyqa account."""
                
        if self.cloud_backend:
            await self.cloud_backend.shutdown()
        if self.local_communicator:
            await self.local_communicator.shutdown()
        
    async def discover_devices(self, args: argparse.Namespace, message_queue_tx_local: list[Any],
        target_device_uids: set[Any]) -> None:
        """Discover devices."""
        if not self.local_communicator:
            return

        print(sep_width * "-")
        print("Search local network for devices ...")
        print(sep_width * "-")

        discover_end_event: asyncio.Event = asyncio.Event()
        discover_timeout_secs: float = 2.5

        async def discover_answer_end(
            answer: TypeJSON, uid: str
        ) -> None:
            LOGGER.debug(f"discover ping end")
            discover_end_event.set()

        LOGGER.debug(f"discover ping start")
        # send a message to uid "all" which is fake but will get the identification message
        # from the devices in the aes_search and send msg function and we can send then a real
        # request message to these discovered devices.
        await self.local_communicator.set_send_message(
            message_queue_tx_local,
            "all",
            args,
            discover_answer_end,
            discover_timeout_secs,
        )

        await discover_end_event.wait()
        if self.devices:
            target_device_uids = set(
                u_id for u_id, v in self.devices.items()
            )
            # some code missing

    def device_name_to_uid(self, args: argparse.Namespace, target_device_uids: set[str]) -> bool:
        """Set target device uid by device name argument."""
        
        if not self.account or not self.account.settings:
            LOGGER.error(
                'Missing account settings to resolve device name  "'
                + args.device_name
                + '"to unit id.'
            )
            return False
        dev: list[str] = [
            format_uid(device["localDeviceId"])
            for device in self.account.settings["devices"]
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
    
    async def select_device(self, args: argparse.Namespace, send_started_local: datetime.datetime) -> str | set[str]:
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
                + get_obj_attrs_as_string(ResponseStatus)
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
    
    async def send_to_devices(
        self,
        args: argparse.Namespace,
        args_in: list[Any],
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
                self.controller_data.aes_keys["all"] = bytes.fromhex(args.aes[0])

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
                LOGGER.info("Send to device: " + ", ".join(args.device_unitids[0].split(",")))

            if not args.selectDevice and self.cloud_backend and self.backend_connected():
                await self.cloud_backend.update_device_configs()

            ### device specific commands ###

            async def send_to_devices_cb(args: argparse.Namespace) -> str | bool | int | set:
                """Send to devices callback for discover of devices option"""
                return await self.send_to_devices(
                    args,
                    args_in,
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
            
            if self.local_communicator and (args.local or args.tryLocalThanCloud):
                if args.passive:
                    if self.local_communicator and self.local_communicator.udp:
                        LOGGER.debug("Waiting for UDP broadcast")
                        data, address = self.local_communicator.udp.recvfrom(4096)
                        LOGGER.debug(
                            "\n\n 2. UDP server received: ",
                            data.decode("utf-8"),
                            "from",
                            address,
                            "\n\n",
                        )

                        LOGGER.debug("3a. Sending UDP ack.\n")
                        self.local_communicator.udp.sendto("QCX-ACK".encode("utf-8"), address)
                        time.sleep(1)
                        LOGGER.debug("3b. Sending UDP ack.\n")
                        self.local_communicator.udp.sendto("QCX-ACK".encode("utf-8"), address)
                else:

                    send_started_local: datetime.datetime = datetime.datetime.now()

                    if args.discover:
                        await self.discover_devices(args, message_queue_tx_local, target_device_uids)

                    msg_wait_tasks: dict[str, asyncio.Task] = {}

                    to_send_device_uids = target_device_uids.copy()

                    async def sl(uid: str) -> None:
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

                    async def async_answer_callback_local(msg: Message, uid: str) -> None:
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
                        
                        await self.local_communicator.set_send_message(
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

            if self.cloud_backend and (args.cloud or args.tryLocalThanCloud):
                success = await self.cloud_backend.cloud_send(args, target_device_uids, to_send_device_uids, timeout_ms, message_queue_tx_state_cloud, message_queue_tx_command_cloud)

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
                    LOGGER.debug(f"{uid}: ")
                    if msg:
                        try:
                            LOGGER.info(f"Answer received from {uid}.")
                            LOGGER.info(
                                f"{json.dumps(json.loads(msg.answer), sort_keys=True, indent=4)}"
                            )
                        except:
                            LOGGER.debug(f"{traceback.format_exc()}")
                    else:
                        LOGGER.error(f"Error no message returned from {uid}.")

                ret: str | bool | int | set = await self.send_to_devices(
                    scene_start_args_parsed,
                    args_in,
                    timeout_ms = timeout_ms
                    - int((datetime.datetime.now() - send_started).total_seconds())
                    * 1000,
                    async_answer_callback = async_print_answer,
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
    

    async def send_to_devices_wrapped(self, args_parsed: argparse.Namespace, args_in: list[Any], timeout_ms: int = 5000) -> int:
        """Set up broadcast port and tcp reply connection port."""

        if args_parsed.cloud or args_parsed.local:
            args_parsed.tryLocalThanCloud = False

        if args_parsed.debug:
            LOGGER.setLevel(level=logging.DEBUG)
            logging_hdl.setLevel(level=logging.DEBUG)

        if args_parsed.dev:
            self.controller_data.aes_keys["dev"] = AES_KEY_DEV

        local_communication: bool = args_parsed.local or args_parsed.tryLocalThanCloud

        if local_communication and self.local_communicator:
            if not await self.local_communicator.bind_ports():
                return 1

        exit_ret: int = 0

        async def async_answer_callback(msg: Message, uid: str) -> None:
            LOGGER.debug(f"{uid}: ")
            if msg:
                try:
                    LOGGER.info(f"Answer received from {uid}.")
                    LOGGER.info(
                        f"{json.dumps(json.loads(msg.answer), sort_keys=True, indent=4)}"
                    )
                except:
                    LOGGER.debug(f"{traceback.format_exc()}")
            else:
                LOGGER.error(f"Error no message returned from {uid}.")

        if not await self.send_to_devices(
            args_parsed,
            args_in,
            timeout_ms = timeout_ms,
            async_answer_callback = async_answer_callback,
        ):
            exit_ret = 1

        LOGGER.debug("Closing ports")
        if self.local_communicator:
            await self.local_communicator.shutdown()

        return exit_ret

async def main() -> None:
    """Main function."""
    
    klyqa_accs: dict[str, Account] | None = None
    if not klyqa_accs:
        klyqa_accs = dict()

    parser: argparse.ArgumentParser = get_description_parser()

    add_config_args(parser=parser)

    args_in: list[str] = sys.argv[1:]

    (
        config_args_parsed,
        _,
    ) = parser.parse_known_args(args=args_in)

    if config_args_parsed.type == DeviceType.cleaner.name:
        add_command_args_cleaner(parser=parser)
    elif config_args_parsed.type == DeviceType.lighting.name:
        add_command_args_bulb(parser=parser)
    else:
        LOGGER.error("Unknown command type.")
        sys.exit(1)

    if len(args_in) < 2 or config_args_parsed.help:
        parser.print_help()
        sys.exit(1)

    args_parsed: argparse.Namespace = parser.parse_args(args=args_in)

    if args_parsed.version:
        print(KLYQA_CTL_VERSION)
        sys.exit(0)

    if not args_parsed:
        sys.exit(1)

    if args_parsed.debug:
        LOGGER.setLevel(level=logging.DEBUG)
        logging_hdl.setLevel(level=logging.DEBUG)
    
    if args_parsed.quiet:
        LOGGER.setLevel(level=logging.CRITICAL)
        logging_hdl.setLevel(level=logging.CRITICAL)

    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS
    if args_parsed.timeout:
        timeout_ms = int(args_parsed.timeout[0]) * 1000

    server_ip: str = args_parsed.myip[0] if args_parsed.myip else "0.0.0.0"

    print_onboarded_devices: bool = (
        not args_parsed.device_name
        and not args_parsed.device_unitids
        and not args_parsed.allDevices
        and not args_parsed.quiet
    )

    account: Account | None = None

    host: str = PROD_HOST
    if args_parsed.test:
        host = TEST_HOST

    if args_parsed.dev:
        if args_parsed.dev:
            LOGGER.info("development mode. Using default aes key.")
        account = Account()
        print_onboarded_devices=False

    else:
        LOGGER.debug("login")
        if args_parsed.username is not None and args_parsed.username[0] in klyqa_accs:
            account = klyqa_accs[args_parsed.username[0]]
        else:
            account = Account(
                args_parsed.username[0] if args_parsed.username else "",
                args_parsed.password[0] if args_parsed.password else ""
            )

    exit_ret = 0
        
    controller_data: ControllerData = ControllerData(interactive_prompts = True, offline = args_parsed.offline)    
    local_communicator: LocalCommunicator = LocalCommunicator(controller_data, account, server_ip)
    cloud_backend: CloudBackend = CloudBackend(controller_data, account, host, args_parsed.offline)

    client: Client = Client(controller_data, local_communicator, cloud_backend, account)
    
    if cloud_backend and not account.access_token:
        try:
            if await cloud_backend.login(print_onboarded_devices = print_onboarded_devices):
                LOGGER.debug("login finished")
                klyqa_accs[account.username] = account
            else:
                raise Exception()
        except:
            LOGGER.error("Error during login.")
            LOGGER.debug(f"{traceback.format_exc()}")
            sys.exit(1)

    if (
        await client.send_to_devices_wrapped(
            args_parsed, args_in.copy(), timeout_ms=timeout_ms)
        > 0
    ):
        exit_ret = 1

    await client.shutdown()
    LOGGER.debug("Closing ports")
    await local_communicator.shutdown()
    await cloud_backend.shutdown()

    sys.exit(exit_ret)

if __name__ == "__main__":
    asyncio.run(main())
