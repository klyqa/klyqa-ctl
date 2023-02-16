from __future__ import annotations

import argparse
import asyncio
import os
import sys

from klyqa_ctl.account import Account
from klyqa_ctl.communication.cloud import CloudBackend
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.light.commands import (
    ColorCommand,
    PingCommand,
    add_command_args_bulb,
    add_device_command_to_queue,
)
from klyqa_ctl.general.general import (
    DEFAULT_SEND_TIMEOUT_MS,
    PROD_HOST,
    TRACE,
    Command,
    RgbColor,
    set_debug_logger,
    set_logger,
    task_log_debug,
)
from klyqa_ctl.general.parameters import (
    add_config_args,
    get_description_parser,
)
from klyqa_ctl.klyqa_ctl import Client


async def main() -> None:
    """Main function."""

    exit_ret: int = 0

    username: str = os.environ["KLYQA_USERNAME"]
    password: str = os.environ["KLYQA_PASSWORD"]

    host: str = PROD_HOST
    if "KLYQA_HOST" in os.environ and os.environ["KLYQA_HOST"]:
        host = os.environ["KLYQA_HOST"]

    set_logger()
    set_debug_logger(level=TRACE)

    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS

    client: Client = await Client.create(
        interactive_prompts=True,
        offline=False,
    )

    if client.cloud:
        client.cloud.host = host

    print_onboarded_devices: bool = True

    acc: Account = await client.add_account(
        username=username,
        password=password,
    )
    await acc.login()
    await acc.get_account_state(
        print_onboarded_devices=print_onboarded_devices
    )

    exit_ret = 0

    # intf: str | None = None
    # if args_parsed.interface is not None:
    #     intf = args_parsed.interface[0]

    # local_con_hdl: LocalConnectionHandler = LocalConnectionHandler(
    #     controller_data, server_ip, network_interface=intf
    # )

    # unit_id: str = "00ac629de9ad2f4409dc"
    unit_id: str = "04256291add6f1b414d1"
    unit_id_real: str = "286dcd5c6bda"

    await client.discover_devices(33333)
    # if client.local:
    #     loop.run_until_complete(client.local.discover_devices(3))

    await acc.cloud_post_command_to_dev(
        acc.devices[unit_id_real],
        PingCommand(),
    )

    await acc.cloud_post_command_to_dev(
        acc.devices[unit_id_real],
        ColorCommand(color=RgbColor(2, 22, 222)),
    )

    # test args parse client
    args_in: list[str] = ["lighting", "--ping"]

    parser: argparse.ArgumentParser = get_description_parser()
    add_config_args(parser=parser)

    # (
    #     config_args_parsed,
    #     _,
    # ) = parser.parse_known_args(args=args_in)
    add_command_args_bulb(parser=parser)
    args_parsed: argparse.Namespace = parser.parse_args(args=args_in)

    msg_queue: list[Command] = []

    # args: argparse.Namespace,
    # args_in: list[Any],
    # send_to_devices_callable: Callable[[argparse.Namespace], Any],
    # message_queue_tx_local: list[Any],
    # message_queue_tx_command_cloud: list[Any],
    # message_queue_tx_state_cloud: list[Any],
    # scene_list: list[str],
    async def cal(args: argparse.Namespace) -> None:
        return

    await add_device_command_to_queue(args_parsed, args_in, cal, msg_queue, [])
    s: set[str] = set([unit_id])
    if client.cloud:
        ret = await client.cloud.send(
            args_parsed,
            s,
            s,
            300000,
            msg_queue,
            [],
        )

    # args: argparse.Namespace,
    # target_device_uids: set[str],
    # to_send_device_uids: set[
    #     str
    # ],  # the device unit ids remaining to send from --tryLocalThanCloud
    # timeout_ms: int,
    # message_queue_tx_state_cloud: list,
    # message_queue_tx_command_cloud: list

    # if (
    #     await client.send_to_devices_wrapped(
    #         args_parsed, args_in.copy(), timeout_ms=timeout_ms
    #     )
    #     > 0
    # ):
    #     exit_ret = 1

    task_log_debug("Shutting down..")
    await client.shutdown()

    sys.exit(exit_ret)


if __name__ == "__main__":
    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    loop.run_until_complete(main())
