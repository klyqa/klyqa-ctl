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
from klyqa_ctl.communication.local.communicator import LocalConnectionHandler
from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.light.light import Light
from klyqa_ctl.devices.light.commands import add_command_args_bulb
from klyqa_ctl.devices.light.commands import create_device_message as create_device_message_light
from klyqa_ctl.devices.light.response_status import ResponseStatus
from klyqa_ctl.devices.vacuum import VacuumCleaner, add_command_args_cleaner
from klyqa_ctl.devices.vacuum.commands import create_device_message as create_device_message_vacuum
from klyqa_ctl.general.connections import PROD_HOST, TEST_HOST
from klyqa_ctl.general.general import AES_KEY_DEV, DEFAULT_SEND_TIMEOUT_MS, KLYQA_CTL_VERSION, LOGGER, TRACE, DeviceType, TypeJson, SEPARATION_WIDTH, format_uid, get_obj_attrs_as_string, logging_hdl, task_log_trace_ex
from klyqa_ctl.general.parameters import add_config_args, get_description_parser
from klyqa_ctl.account import Account
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId

class Client:
    """Client"""

    def __init__(
        self,
        controller_data: ControllerData,
        local_connection_hdl: LocalConnectionHandler | None,
        cloud_backend: CloudBackend | None, 
        account: Account | None,
        devices: dict = dict()
    ) -> None:
        """! Initialize the account with the login data, tcp, udp datacommunicator and tcp
        communication tasks."""
        self._attr_controller_data: ControllerData = controller_data
        self._attr_local_con_hdl: LocalConnectionHandler | None = local_connection_hdl 
        self._attr_account: Account | None = account
        self._attr_devices: dict[str, Device] = devices
        self._attr_cloud_backend: CloudBackend | None = cloud_backend

    @property
    def controller_data(self) -> ControllerData:
        return self._attr_controller_data
    
    @controller_data.setter
    def controller_data(self, controller_data: ControllerData) -> None:
        self._attr_controller_data = controller_data

    @property
    def local_con_hdl(self) -> LocalConnectionHandler | None:
        return self._attr_local_con_hdl
    
    @local_con_hdl.setter
    def local_con_hdl(self, local_con_hdl: LocalConnectionHandler | None ) -> None:
        self._attr_local_con_hdl = local_con_hdl

    @property
    def account(self) -> Account | None:
        return self._attr_account
    
    @account.setter
    def account(self, account: Account) -> None:
        self._attr_account = account

    @property
    def devices(self) -> dict[str, Device]:
        return self._attr_devices
    
    @devices.setter
    def devices(self, devices: dict[str, Device]) -> None:
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
        if self.local_con_hdl:
            await self.local_con_hdl.shutdown()
        
    async def discover_devices(self, args: argparse.Namespace, message_queue_tx_local: list[Any],
        target_device_uids: set[Any]) -> None:
        """Discover devices."""
        if not self.local_con_hdl:
            return

        print(SEPARATION_WIDTH * "-")
        print("Search local network for devices ...")
        print(SEPARATION_WIDTH * "-")

        discover_end_event: asyncio.Event = asyncio.Event()
        discover_timeout_secs: float = 2.5

        async def discover_answer_end(
            answer: TypeJson, uid: str
        ) -> None:
            LOGGER.debug(f"discover ping end")
            discover_end_event.set()

        LOGGER.debug(f"discover ping start")
        # send a message to uid "all" which is fake but will get the identification message
        # from the devices in the aes_search and send msg function and we can send then a real
        # request message to these discovered devices.
        await self.local_con_hdl.add_message(
            message_queue_tx_local,
            UnitId("all"),
            discover_answer_end,
            discover_timeout_secs,
        )

        await discover_end_event.wait()
        if self.devices:
            target_device_uids = set(
                u_id for u_id, v in self.devices.items()
            )
            # some code missing

    def device_name_to_uid(self, args: argparse.Namespace, target_device_uids: set[UnitId]) -> bool:
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
        
        print(SEPARATION_WIDTH * "-")
        # devices_working = {k: v for k, v in self.devices.items() if v.local.aes_key_confirmed}
        devices_working: dict[str, Device] = {
            u_id: device
            for u_id, device in self.devices.items()
            if (
                (
                    args.type == DeviceType.LIGHTING.value
                    and isinstance(device, Light)
                )
                or (
                    args.type == DeviceType.CLEANER.value
                    and isinstance(device, VacuumCleaner)
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
        
        print(SEPARATION_WIDTH * "-")
        count: int = 1
        device_items: list[Device] = list(devices_working.values())

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
            loop = asyncio.get_event_loop()

            send_started: datetime.datetime = datetime.datetime.now()

            add_command_args_ch: dict[str, Callable[..., Any]] = {
                DeviceType.LIGHTING.value: add_command_args_bulb,
                DeviceType.CLEANER.value: add_command_args_cleaner,
            }
            add_command_args: Callable[..., Any] = add_command_args_ch[args.type]

            if args.dev:
                args.local = True
                args.tryLocalThanCloud = False
                args.cloud = False

            if args.debug:
                LOGGER.setLevel(level=logging.DEBUG)
                logging_hdl.setLevel(level=logging.DEBUG)
                
            if args.trace:
                LOGGER.setLevel(TRACE)
                logging_hdl.setLevel(TRACE)

            if args.cloud or args.local:
                args.tryLocalThanCloud = False

            if args.aes is not None:
                self.controller_data.aes_keys["all"] = bytes.fromhex(args.aes[0])

            target_device_uids: set[UnitId] = set()

            message_queue_tx_local: list[Any] = []
            message_queue_tx_state_cloud: list[Any] = []
            message_queue_tx_command_cloud: list[Any] = []

            if args.device_name is not None:
                if not self.device_name_to_uid(args, target_device_uids):
                    return False

            if args.device_unitids is not None:
                target_device_uids = set(
                    map(UnitId, set(args.device_unitids[0].split(",")))
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
            if args.type == DeviceType.LIGHTING.value:
                await create_device_message_light(
                    args,
                    args_in,
                    send_to_devices_cb,
                    message_queue_tx_local,
                    message_queue_tx_command_cloud,
                    message_queue_tx_state_cloud,
                    scene,
                )
            elif args.type == DeviceType.CLEANER.value:
                await create_device_message_vacuum(
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
            to_send_device_uids: set[UnitId] = set()
            
            if self.local_con_hdl and (args.local or args.tryLocalThanCloud):
                if args.passive:
                    if self.local_con_hdl and self.local_con_hdl.udp:
                        LOGGER.debug("Waiting for UDP broadcast")
                        data, address = self.local_con_hdl.udp.recvfrom(4096)
                        LOGGER.debug(
                            "\n\n 2. UDP server received: ",
                            data.decode("utf-8"),
                            "from",
                            address,
                            "\n\n",
                        )

                        LOGGER.debug("3a. Sending UDP ack.\n")
                        self.local_con_hdl.udp.sendto("QCX-ACK".encode("utf-8"), address)
                        time.sleep(1)
                        LOGGER.debug("3b. Sending UDP ack.\n")
                        self.local_con_hdl.udp.sendto("QCX-ACK".encode("utf-8"), address)
                else:

                    send_started_local: datetime.datetime = datetime.datetime.now()

                    if args.discover:
                        await self.discover_devices(args, message_queue_tx_local, target_device_uids)

                    msg_wait_tasks: dict[str, asyncio.Task] = {}

                    to_send_device_uids = target_device_uids.copy()

                    async def sleep_task(uid: str) -> None:
                        """Sleep task for timeout."""
                        try:
                            await asyncio.sleep(timeout_ms / 1000)
                        except CancelledError:
                            LOGGER.debug(f"sleep uid {uid} cancelled.")

                    for uid in target_device_uids:
                        msg_wait_tasks[uid] = loop.create_task(sleep_task(uid))

                    async def async_answer_callback_local(msg: Message, uid: str) -> None:
                        if msg and msg.msg_queue_sent:
                            LOGGER.debug(f"{uid} msg callback.")

                        if uid in to_send_device_uids:
                            to_send_device_uids.remove(UnitId(uid))
                        msg_wait_tasks[uid].cancel()
                        if async_answer_callback:
                            await async_answer_callback(msg, uid)

                    for uid in target_device_uids:
                        
                        await self.local_con_hdl.add_message(
                            send_msgs = message_queue_tx_local.copy(),
                            target_device_uid = uid,
                            callback=async_answer_callback_local,
                            time_to_live_secs=(timeout_ms / 1000)
                        )

                    for uid in target_device_uids:
                        LOGGER.debug(f"wait for send task {uid}.")
                        try:
                            await asyncio.wait([msg_wait_tasks[uid]])
                        except CancelledError as e:
                            LOGGER.debug(f"sleep wait for uid {uid} cancelled.")
                        LOGGER.debug(f"wait for send task {uid} end.")

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
            task_log_trace_ex()
            return False
    
    async def send_to_devices_wrapped(self, args_parsed: argparse.Namespace, args_in: list[Any], timeout_ms: int = 5000) -> int:
        """Set up broadcast port and tcp reply connection port."""

        if args_parsed.cloud or args_parsed.local:
            args_parsed.tryLocalThanCloud = False

        if args_parsed.debug:
            LOGGER.setLevel(level=logging.DEBUG)
            logging_hdl.setLevel(level=logging.DEBUG)
        
        if args_parsed.trace:
            LOGGER.setLevel(TRACE)
            logging_hdl.setLevel(TRACE)

        if args_parsed.dev:
            self.controller_data.aes_keys["dev"] = AES_KEY_DEV

        local_communication: bool = args_parsed.local or args_parsed.tryLocalThanCloud

        if local_communication and self.local_con_hdl:
            if not await self.local_con_hdl.bind_ports():
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
        if self.local_con_hdl:
            await self.local_con_hdl.shutdown()

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

    if config_args_parsed.type == DeviceType.CLEANER.value:
        add_command_args_cleaner(parser=parser)
    elif config_args_parsed.type == DeviceType.LIGHTING.value:
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
        
    if args_parsed.trace:
        LOGGER.setLevel(TRACE)
        logging_hdl.setLevel(TRACE)
    
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
    
    controller_data: ControllerData = ControllerData(interactive_prompts = True, offline = args_parsed.offline)
    await controller_data.init()

    account: Account | None = None

    host: str = PROD_HOST
    if args_parsed.test:
        host = TEST_HOST

    if args_parsed.dev:
        if args_parsed.dev:
            LOGGER.info("development mode. Using default aes key.")
        # account = Account()
        print_onboarded_devices=False

    else:
        LOGGER.debug("login")
        if args_parsed.username is not None and args_parsed.username[0] in klyqa_accs:
            account = klyqa_accs[args_parsed.username[0]]
        else:
            account = Account(
                args_parsed.username[0] if args_parsed.username else "",
                args_parsed.password[0] if args_parsed.password else "",
                # controller_data.device_configs
            )

    exit_ret = 0
        
    local_con_hdl: LocalConnectionHandler = LocalConnectionHandler(controller_data, account, server_ip)
    
    cloud_backend: CloudBackend | None = None
    if account:
        cloud_backend = CloudBackend(controller_data, account, host, args_parsed.offline)
    
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

    client: Client = Client(controller_data, local_con_hdl, cloud_backend, account)

    if (
        await client.send_to_devices_wrapped(
            args_parsed, args_in.copy(), timeout_ms=timeout_ms)
        > 0
    ):
        exit_ret = 1

    await client.shutdown()
    LOGGER.debug("Closing ports")
    await local_con_hdl.shutdown()
    
    if cloud_backend:
        await cloud_backend.shutdown()

    sys.exit(exit_ret)

if __name__ == "__main__":
    asyncio.run(main())
