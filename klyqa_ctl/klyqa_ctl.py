#!/usr/bin/env python3
"""Klyqa control client.

Interactive Klyqa Control commandline client

Company: QConnex GmbH / Klyqa
Author: Frederick Stallmeyer

E-Mail: frederick.stallmeyer@gmx.de

Information:
The network_interface parameter for local connection handling (in
LocalConnectionHandler) will ONLY work on LINUX systems, as it uses the linux
specific socket option SO_BINDTODEVICE for communication.

Nice to haves/missing:
  -   list cloud connected devices in discovery.
  -   offer for selected devices possible commands and arguments in
      interactive mode based on their device profile
  -   Implementation for the different device config profile versions and
      check on send.
  -   start scene support in cloud mode

Current bugs:
 - vc1 interactive command selection support.
 - interactive light selection, command not applied

"""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
import datetime
import json
import logging
import sys
import time
from typing import Any, cast

from klyqa_ctl.__init__ import __version__
from klyqa_ctl.account import Account, AccountDevice
from klyqa_ctl.communication.cloud import CloudBackend
from klyqa_ctl.communication.device_connection_handler import DeviceConnectionHandler
from klyqa_ctl.communication.local.connection_handler import LocalConnectionHandler
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.light.commands import (
    add_device_command_to_queue as add_device_command_to_queue_light,
)
from klyqa_ctl.devices.light.commands import add_command_args_bulb
from klyqa_ctl.devices.light.light import Light
from klyqa_ctl.devices.light.response_status import ResponseStatus
from klyqa_ctl.devices.vacuum.commands import (
    create_device_message as create_device_message_vacuum,
)
from klyqa_ctl.devices.vacuum.commands import add_command_args_cleaner
from klyqa_ctl.devices.vacuum.vacuum import VacuumCleaner
from klyqa_ctl.general.general import (
    AES_KEY_DEV_BYTES,
    DEFAULT_SEND_TIMEOUT_MS,
    LOGGER,
    QCX_ACK,
    SEPARATION_WIDTH,
    TRACE,
    DeviceType,
    aes_key_to_bytes,
    get_asyncio_loop,
    get_obj_attrs_as_string,
    set_debug_logger,
    set_logger,
    task_log_debug,
    task_log_trace_ex,
)
from klyqa_ctl.general.message import Message, MessageState
from klyqa_ctl.general.parameters import add_config_args, get_description_parser
from klyqa_ctl.general.unit_id import UnitId


class Client(ControllerData):
    """Major klyqa-ctl client class."""

    def __init__(
        self,
        accounts: dict[str, Account] | None = None,
    ) -> None:
        """Initialize the client."""

        super().__init__()
        self._attr_local: LocalConnectionHandler | None = None
        self._attr_cloud: CloudBackend | None = None
        self._attr_accounts: dict[str, Account] = (
            {} if accounts is None else accounts
        )

    @property
    def local(self) -> LocalConnectionHandler | None:
        return self._attr_local

    @local.setter
    def local(self, local: LocalConnectionHandler | None) -> None:
        self._attr_local = local

    @property
    def accounts(self) -> dict[str, Account]:
        return self._attr_accounts

    @accounts.setter
    def accounts(self, accounts: dict[str, Account]) -> None:
        self._attr_accounts = accounts

    @property
    def cloud(self) -> CloudBackend | None:
        return self._attr_cloud

    @cloud.setter
    def cloud(self, cloud: CloudBackend) -> None:
        self._attr_cloud = cloud

    # def backend_connected(self) -> bool:
    #     if self.cloud_backend:
    #         return bool(self.cloud_backend.access_token != "")
    #     return False

    async def discover_devices(self, ttl_secs: int = 3) -> None:
        """Discover devices from device list via cloud or with local UDP
        broadcast."""

        tasks: list[asyncio.Task] = []
        if self.local:
            tasks.append(
                asyncio.create_task(self.local.discover_devices(ttl_secs))
            )
        if self.cloud and False:
            device: Device
            for _, device in self.devices.items():
                tasks.append(
                    asyncio.create_task(
                        device.ping_con(device.cloud, ttl_ping_secs=ttl_secs)
                    )
                )

        for task in tasks:
            try:
                await asyncio.wait_for(task, timeout=ttl_secs)
            except asyncio.exceptions.TimeoutError:
                task_log_debug("Discover timeout.")
        # await asyncio.wait(tasks)

    def create_device(self, unit_id: str, product_id: str) -> Device:
        """Get or create a device from the controller data. Read in device
        config when new device is created."""

        dev: Device = super().create_device(unit_id, product_id)
        dev.local.con = cast(DeviceConnectionHandler, self.local)
        dev.cloud.con = cast(DeviceConnectionHandler, self.cloud)
        return dev

    async def add_account(
        self,
        username: str,
        password: str = "",
    ) -> Account:
        """Add user account to client."""

        account: Account = await Account.create_default(
            self,
            cloud=self.cloud,
            username=username,
            password=password,
        )
        self.accounts[account.username] = account

        return account

    async def shutdown(self) -> None:
        """Logout again from klyqa account."""

        for _, acc in self.accounts.items():
            await acc.shutdown()
        if self.local:
            await self.local.shutdown()

    # async def discover_devices(
    #     self,
    #     args: argparse.Namespace,
    #     message_queue_tx_local: list[Any],
    #     target_device_uids: set[Any],
    # ) -> None:
    #     """Discover devices."""
    #     if not self.local:
    #         return

    #     print(SEPARATION_WIDTH * "-")
    #     print("Search local network for devices ...")
    #     print(SEPARATION_WIDTH * "-")

    #     discover_timeout_secs: float = 2.5

    #     task_log_debug("discover ping start")
    #     # send a message to uid "all" which is fake but will get the
    #     # identification message from the devices in the aes_search and
    #     # send msg function and we can send then a real
    #     # request message to these discovered devices.
    #     await self.local.send_command_to_device(
    #         UnitId("all"),
    #         message_queue_tx_local,
    #         timeout_secs=discover_timeout_secs,
    #     )
    #     task_log_debug("discover ping end")
    # if self.devices:
    #     target_device_uids = set(
    # u_id for u_id, v in self.devices.items())
    # some code missing

    # def device_name_to_uid(
    #     self, args: argparse.Namespace, target_device_uids: set[str]
    # ) -> bool:
    #     """Set target device uid by device name argument."""

    #     if not self.account or not self.account.settings:
    #         LOGGER.error(
    #             'Missing account settings to resolve device name  "'
    #             + args.device_name
    #             + '"to unit id.'
    #         )
    #         return False
    #     dev: list[str] = [
    #         format_uid(device["localDeviceId"])
    #         for device in self.account.settings["devices"]
    #         if device["name"] == args.device_name
    #     ]
    #     if not dev:
    #         LOGGER.error(
    #             'Device name "'
    #             + args.device_name
    #             + '" not found in account settings.'
    #         )
    #         return False
    #     else:
    #         target_device_uids.add(format_uid(dev[0]))
    #     return True

    async def select_device(
        self, args: argparse.Namespace, send_started_local: datetime.datetime
    ) -> str | set[str]:
        """Interactive select device."""

        print(SEPARATION_WIDTH * "-")
        # devices_working = {
        #     k: v for k, v in self.devices.items() if
        # v.local.aes_key_confirmed
        # }
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
                f" (local {device.local_addr.ip}:{device.local_addr.port})"
                if device.local_addr.ip
                else ""
            )
            cloud: str = " (cloud connected)" if device.cloud.connected else ""
            status: str = (
                f" ({device.status})" if device.status else " (no status)"
            )
            print(f"{count}) {name}{status}{address}{cloud}")
            count = count + 1

        if self.devices:
            print("")
            device_num_s: str = input(
                "Choose bulb number(s) (comma seperated) a"
                " (all),[1-9]*{,[1-9]*}*: "
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

        # No devices found. Exit script.
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
            loop: asyncio.AbstractEventLoop = get_asyncio_loop()

            send_started: datetime.datetime = datetime.datetime.now()

            add_command_args_ch: dict[str, Callable[..., Any]] = {
                DeviceType.LIGHTING.value: add_command_args_bulb,
                DeviceType.CLEANER.value: add_command_args_cleaner,
            }
            add_command_args: Callable[..., Any] = add_command_args_ch[
                args.type
            ]

            if args.dev:
                args.local = True
                args.tryLocalThanCloud = False
                args.cloud = False

            if args.debug:
                set_debug_logger(level=logging.DEBUG)

            if args.trace:
                set_debug_logger(level=TRACE)

            if args.cloud or args.local:
                args.tryLocalThanCloud = False

            if args.aes is not None:
                self.aes_keys["all"] = aes_key_to_bytes(args.aes[0])

            if args.passive and self.local:
                self.local.broadcast_discovery = False

            target_device_uids: set[str] = set()

            message_queue_tx_local: list[Any] = []
            message_queue_tx_state_cloud: list[Any] = []
            message_queue_tx_command_cloud: list[Any] = []

            # if args.device_name is not None:
            #     if not self.device_name_to_uid(args, target_device_uids):
            #         return False

            if args.device_unitids is not None:
                target_device_uids = set(
                    map(str, set(args.device_unitids[0].split(",")))
                )
                LOGGER.info(
                    "Send to device: "
                    + ", ".join(args.device_unitids[0].split(","))
                )

            # if (
            #     not args.selectDevice
            #     and self.cloud_backend
            #     # and self.backend_connected()
            # ):
            #     await self.cloud_backend.update_device_configs()

            # device specific commands #

            async def send_to_devices_cb(
                args: argparse.Namespace,
            ) -> str | bool | int | set:
                """Send to devices callback for discover of devices option"""
                return await self.send_to_devices(
                    args,
                    args_in,
                    timeout_ms=3500,
                )

            scene: list[str] = []
            if args.type == DeviceType.LIGHTING.value:
                await add_device_command_to_queue_light(
                    args,
                    args_in,
                    send_to_devices_cb,
                    message_queue_tx_local,
                    scene,
                )
            elif args.type == DeviceType.CLEANER.value:
                await create_device_message_vacuum(
                    args,
                    args_in,
                    send_to_devices_cb,
                    message_queue_tx_local,
                    # message_queue_tx_command_cloud,
                    # message_queue_tx_state_cloud,
                )
            else:
                LOGGER.error("Missing device type.")
                return False

            success: bool = True
            to_send_device_uids: set[str] = set()

            if self.local and (args.local or args.tryLocalThanCloud):
                if args.passive:
                    if self.local and self.local.udp:
                        task_log_debug("Waiting for UDP broadcast")
                        data, address = self.local.udp.recvfrom(4096)
                        task_log_debug(
                            "\n\n 2. UDP server received: ",
                            data.decode("utf-8"),
                            "from",
                            address,
                            "\n\n",
                        )

                        task_log_debug("3a. Sending UDP ack.\n")
                        self.local.udp.sendto(QCX_ACK, address)
                        time.sleep(1)
                        task_log_debug("3b. Sending UDP ack.\n")
                        self.local.udp.sendto(QCX_ACK, address)
                else:

                    send_started_local: datetime.datetime = (
                        datetime.datetime.now()
                    )

                    if args.discover:
                        await self.local.discover_devices()
                        # await self.discover_devices(
                        #     args, message_queue_tx_local, target_device_uids
                        # )

                    to_send_device_uids = target_device_uids.copy()

                    send_tasks: list[asyncio.Task] = []
                    for uid in target_device_uids:

                        send_tasks.append(
                            loop.create_task(
                                self.local.send_command_to_device(
                                    unit_id=UnitId(uid),
                                    send_msgs=message_queue_tx_local.copy(),
                                    time_to_live_secs=(timeout_ms / 1000),
                                )
                            )
                        )

                    task_log_debug("wait for all target device uids done.")
                    for task in send_tasks:
                        try:
                            await asyncio.wait_for(
                                task, timeout=(timeout_ms / 1000)
                            )
                        except asyncio.CancelledError:
                            task_log_debug("Timeout for send.")
                        msg: Message = task.result()
                        if msg.state == MessageState.SENT:
                            to_send_device_uids.remove(UnitId(msg.target_uid))

                    if args.selectDevice:
                        return await self.select_device(
                            args, send_started_local
                        )

                if target_device_uids and len(to_send_device_uids) > 0:
                    # Error
                    sent_locally_error: str = (
                        "The commands "
                        + str([f"{k}={v}" for k, v in vars(args).items() if v])
                        + " failed to send locally to the device(s): "
                        + ", ".join(to_send_device_uids)
                    )
                    if args.tryLocalThanCloud:
                        LOGGER.info(sent_locally_error)
                    else:
                        LOGGER.error(sent_locally_error)
                    success = False

            if self.cloud and (args.cloud or args.tryLocalThanCloud):
                if args.username and args.username in self.accounts:
                    acc: Account = self.accounts[args.username]
                    for uid in target_device_uids:
                        acc_dev: AccountDevice = (
                            await acc.get_or_create_device(uid)
                        )
                        for command in message_queue_tx_local:
                            await acc.cloud_post_command_to_dev(
                                acc_dev, command
                            )
                else:
                    success = await self.cloud.send(
                        args,
                        target_device_uids,
                        to_send_device_uids,
                        timeout_ms,
                        message_queue_tx_state_cloud,
                        message_queue_tx_command_cloud,
                    )

            if success and scene:
                scene_start_args: list[str] = [
                    args.type,
                    "--routine_id",
                    "0",
                    "--routine_start",
                ]

                orginal_args_parser: argparse.ArgumentParser = (
                    get_description_parser()
                )
                scene_start_args_parser: argparse.ArgumentParser = (
                    get_description_parser()
                )

                add_config_args(parser=orginal_args_parser)
                add_config_args(parser=scene_start_args_parser)
                add_command_args(parser=scene_start_args_parser)

                (
                    original_config_args_parsed,
                    _,
                ) = orginal_args_parser.parse_known_args(args=args_in)

                scene_start_args_parsed = scene_start_args_parser.parse_args(
                    scene_start_args, namespace=original_config_args_parsed
                )

                async def async_print_answer(msg: Message, uid: str) -> None:
                    task_log_debug(f"{uid}: ")
                    if msg:
                        try:
                            LOGGER.info(f"Answer received from {uid}.")
                            format_answer: str = json.dumps(
                                json.loads(msg.answer),
                                sort_keys=True,
                                indent=4,
                            )
                            LOGGER.info(f"{format_answer}")
                        except json.JSONDecodeError:
                            task_log_trace_ex()
                    else:
                        LOGGER.error(f"Error no message returned from {uid}.")

                ret: str | bool | int | set = await self.send_to_devices(
                    scene_start_args_parsed,
                    args_in,
                    timeout_ms=timeout_ms
                    - int(
                        (
                            datetime.datetime.now() - send_started
                        ).total_seconds()
                    )
                    * 1000,
                    async_answer_callback=async_print_answer,
                )

                if isinstance(ret, bool) and ret:
                    success = True
                else:
                    LOGGER.error(f"Couldn't start scene {scene[0]}.")
                    success = False

            return success
        except Exception:
            task_log_trace_ex()
            return False

    async def send_to_devices_wrapped(
        self,
        args_parsed: argparse.Namespace,
        args_in: list[Any],
        timeout_ms: int = 5000,
    ) -> int:
        """Set up broadcast port and tcp reply connection port."""

        if args_parsed.cloud or args_parsed.local:
            args_parsed.tryLocalThanCloud = False

        if args_parsed.debug:
            set_debug_logger()

        if args_parsed.trace:
            set_debug_logger(level=TRACE)

        if args_parsed.dev:
            self.aes_keys["dev"] = AES_KEY_DEV_BYTES

        local_communication: bool = (
            args_parsed.local or args_parsed.tryLocalThanCloud
        )

        if local_communication and self.local:
            if not await self.local.bind_ports():
                return 1

        exit_ret: int = 0

        async def async_answer_callback(msg: Message, uid: str) -> None:
            task_log_debug(f"{uid}: ")
            if msg:
                try:
                    LOGGER.info(f"Answer received from {uid}.")

                    format_answer: str = json.dumps(
                        json.loads(msg.answer),
                        sort_keys=True,
                        indent=4,
                    )
                    LOGGER.info(f"{format_answer}")
                except (json.JSONDecodeError, ValueError):
                    task_log_trace_ex()
            else:
                LOGGER.error(f"Error no message returned from {uid}.")

        if not await self.send_to_devices(
            args_parsed,
            args_in,
            timeout_ms=timeout_ms,
            async_answer_callback=async_answer_callback,
        ):
            exit_ret = 1

        task_log_debug("Closing ports")
        if self.local:
            await self.local.shutdown()

        return exit_ret

    @classmethod
    async def create(
        cls: Any,
        interactive_prompts: bool = False,
        offline: bool = False,
        server_ip: str = "0.0.0.0",
        network_interface: str | None = None,
    ) -> Client:
        """Client factory."""

        client: Client = Client()
        client._attr_interactive_prompts = interactive_prompts
        client._attr_offline = offline
        await client.init()

        client.local = LocalConnectionHandler.create_default(
            client,
            server_ip=server_ip,
            network_interface=network_interface,
        )

        client.cloud = CloudBackend.create_default(client)

        return client

    @classmethod
    async def create_worker(
        cls: Any,
        offline: bool = False,
        server_ip: str = "0.0.0.0",
        network_interface: str | None = None,
    ) -> Client:
        """Factory client used as a non-interactive library."""

        return await Client.create(
            interactive_prompts=False,
            offline=offline,
            server_ip=server_ip,
            network_interface=network_interface,
        )


async def async_main() -> None:
    """Main function."""

    exit_ret: int = 0
    set_logger()

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
        print(__version__)
        sys.exit(0)

    if not args_parsed:
        sys.exit(1)

    if args_parsed.debug:
        set_debug_logger(level=logging.DEBUG)

    if args_parsed.trace:
        set_debug_logger(level=TRACE)

    if args_parsed.quiet:
        set_logger(level=logging.CRITICAL)

    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS
    if args_parsed.timeout:
        timeout_ms = int(args_parsed.timeout[0]) * 1000

    server_ip: str = args_parsed.myip[0] if args_parsed.myip else "0.0.0.0"

    client: Client = await Client.create(
        interactive_prompts=True,
        offline=args_parsed.offline,
        server_ip=server_ip,
    )

    print_onboarded_devices: bool = client.interact_prompts

    print_onboarded_devices = (
        not args_parsed.device_name
        and not args_parsed.device_unitids
        and not args_parsed.allDevices
        and not args_parsed.quiet
    )

    if not args_parsed.offline:

        if args_parsed.host and client.cloud:
            client.cloud.host = args_parsed.host[0]

        # if cloud_backend and not account.access_token:
        #     try:
        #         if await cloud_backend.login(
        #             print_onboarded_devices=print_onboarded_devices
        #         ):
        #             task_log_debug("login finished")
        #             klyqa_accs[account.username] = account
        #         else:
        #             raise Exception()
        #     except Exception:
        #         LOGGER.error("Error during login.")
        #         task_log_trace_ex()
        #         sys.exit(1)
    if args_parsed.dev:
        if args_parsed.dev:
            LOGGER.info("development mode. Using default aes key.")
        print_onboarded_devices = False

    else:
        acc: Account = await client.add_account(
            username=args_parsed.username[0] if args_parsed.username else "",
            password=args_parsed.password[0] if args_parsed.password else "",
        )
        await acc.login()
        await acc.get_account_state(
            print_onboarded_devices=print_onboarded_devices
        )

    exit_ret = 0

    if args_parsed.interface is not None and client.local:
        client.local.network_interface = args_parsed.interface[0]

    if (
        await client.send_to_devices_wrapped(
            args_parsed, args_in.copy(), timeout_ms=timeout_ms
        )
        > 0
    ):
        exit_ret = 1

    task_log_debug("Shutting down..")
    await client.shutdown()

    sys.exit(exit_ret)


def main() -> None:
    """Start main async function."""

    loop: asyncio.AbstractEventLoop = get_asyncio_loop()

    loop.run_until_complete(async_main())


if __name__ == "__main__":
    main()
