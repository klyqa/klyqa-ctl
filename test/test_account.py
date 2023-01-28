from __future__ import annotations

import argparse
import asyncio
import sys

import uvloop

from klyqa_ctl.account import Account
from klyqa_ctl.communication.cloud import CloudBackend
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.light.commands import (
    ColorCommand,
    PingCommand,
    add_command_args_bulb,
    create_device_message,
)
from klyqa_ctl.general.general import (
    DEFAULT_SEND_TIMEOUT_MS,
    PROD_HOST,
    TRACE,
    RgbColor,
    set_debug_logger,
    task_log_debug,
)
from klyqa_ctl.general.parameters import (
    add_config_args,
    get_description_parser,
)
from klyqa_ctl.klyqa_ctl import Client

client: Client | None = None


async def main() -> None:
    """Main function."""

    exit_ret: int = 0

    username = "frederick.stallmeyer@qconnex.com"

    set_debug_logger(level=TRACE)

    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS

    controller_data: ControllerData = await ControllerData.create_default(
        interactive_prompts=True,
        # user_account=account,
        offline=False,
    )

    print_onboarded_devices: bool = True

    cloud_backend: CloudBackend | None = None

    host: str = PROD_HOST

    cloud_backend = CloudBackend.create_default(controller_data, host)

    account: Account | None = None
    accounts: dict[str, Account] = dict()

    account = await Account.create_default(
        controller_data,
        cloud=cloud_backend,
        username=username,
        # password=password,
        print_onboarded_devices=print_onboarded_devices,
    )
    accounts[account.username] = account

    exit_ret = 0

    # intf: str | None = None
    # if args_parsed.interface is not None:
    #     intf = args_parsed.interface[0]

    # local_con_hdl: LocalConnectionHandler = LocalConnectionHandler(
    #     controller_data, server_ip, network_interface=intf
    # )

    client: Client = Client(
        controller_data=controller_data,
        local_connection_hdl=None,
        cloud_backend=cloud_backend,
        accounts=accounts,
    )
    # unit_id: str = "00ac629de9ad2f4409dc"
    unit_id: str = "04256291add6f1b414d1"
    unit_id_real: str = "286dcd5c6bda"

    await account.cloud_post_command_to_dev(
        account.devices[unit_id_real],
        PingCommand(),
    )

    await account.cloud_post_command_to_dev(
        account.devices[unit_id_real],
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

    msg_q_s: list = []
    msg_q_c: list = []

    # args: argparse.Namespace,
    # args_in: list[Any],
    # send_to_devices_callable: Callable[[argparse.Namespace], Any],
    # message_queue_tx_local: list[Any],
    # message_queue_tx_command_cloud: list[Any],
    # message_queue_tx_state_cloud: list[Any],
    # scene_list: list[str],
    async def cal(args: argparse.Namespace) -> None:
        return

    await create_device_message(
        args_parsed, args_in, cal, [], msg_q_c, msg_q_s, []
    )
    s: set[str] = set([unit_id])
    ret = await cloud_backend.cloud_send(
        args_parsed,
        s,
        s,
        300000,
        msg_q_s,
        msg_q_c,
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
    uvloop.install()
    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    loop.run_until_complete(main())
