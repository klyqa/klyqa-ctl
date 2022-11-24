"""General parameters"""

from __future__ import annotations
import argparse

from .general import DeviceType


def get_description_parser() -> argparse.ArgumentParser:
    """Make an argument parse object."""

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Interactive klyqa device client (local/cloud). In default the client script tries to send the commands via local connection. Therefore a broadcast on udp port 2222 for discovering the lamps is sent in the local network. When the lamp receives the broadcast it answers via tcp on socket 3333 with a new socket tcp connection. On that tcp connection the commands are sent and the replies are received. "
    )

    return parser


def add_config_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments to the argument parser object.

    Args:
        parser: Parser object
    """
    parser.add_argument("--myip", nargs=1, help="specify own IP for broadcast sender")

    # parser.add_argument(
    #     "--rerun",
    #     help="keep rerunning command",
    #     action="store_const",
    #     const=True,
    #     default=False,
    # )

    parser.add_argument(
        "--passive",
        help="vApp will passively listen vor UDP SYN from devices",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument("--aes", nargs=1, help="give aes key for the lamp")
    parser.add_argument("--username", nargs=1, help="give your username")
    parser.add_argument("--password", nargs=1, help="give your klyqa password")
    parser.add_argument(
        "--timeout",
        nargs=1,
        help="timeout in seconds for the response of the devices",
    )
    parser.add_argument(
        "--version",
        action="store_const",
        const=True,
        default=False,
        help="print klyqa-ctl module version",
    )
    parser.add_argument(
        "--device_name",
        nargs=1,
        help="give the name of the device from your account settings for the command to send to",
    )
    parser.add_argument(
        "--device_unitids",
        nargs=1,
        help="give the device unit id from your account settings for the command to send to",
    )

    required = parser.add_argument_group("required arguments")
    optional = parser.add_argument_group("optional arguments")
    required.add_argument(
        "type",
        choices=[m.name for m in DeviceType],
        help="choose device type to control",
    )

    parser.add_argument(
        "--allDevices",
        help="send commands to all devices",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--discover",
        help="discover lamps",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--debug",
        help="Enable debug logging messages.",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--selectDevice",
        help="Select device.",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--force",
        help="If no configs (profiles) about the device available, send the command anyway (can be dangerous).",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--test",
        help="Test host server.",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--prod",
        help="Production host server.",
        action="store_const",
        const=True,
        default=True,
    )
    parser.add_argument(
        "--local",
        help="Local connection to the devices only.",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--cloud",
        help="Cloud connection to the devices only.",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--tryLocalThanCloud",
        help="Try local if fails then cloud connection to the devices. [This is default behaviour]",
        action="store_const",
        const=True,
        default=True,
    )
    parser.add_argument(
        "--dev",
        help="Developing mode. Use development AES key.",
        action="store_const",
        const=True,
        default=False,
    )
