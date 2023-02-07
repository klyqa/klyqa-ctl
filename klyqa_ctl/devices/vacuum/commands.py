"""Vacuum cleaner commands"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Callable
from klyqa_ctl.devices.commands import CommandAutoBuild

from klyqa_ctl.devices.light.commands import RequestCommand
from klyqa_ctl.devices.vacuum.general import VcSuctionStrengths, VcWorkingMode
from klyqa_ctl.general.general import (
    Command,
    CommandType as MessageCommandType,
)
from klyqa_ctl.general.general import LOGGER
from klyqa_ctl.general.general import TypeJson
from symbol import power


class CommandType(Enum):
    GET = 0
    SET = 1
    RESET = 2


class ProductinfoCommand(RequestCommand):
    def productinfo_json(self) -> TypeJson:
        return {"action": "productinfo"}

    def json(self) -> TypeJson:
        return super().json() | self.productinfo_json()


class RequestGetCommand(RequestCommand):
    def get_json(self) -> TypeJson:
        return {"action": "get"}

    def json(self) -> TypeJson:
        return super().json() | self.get_json()


class RequestResetCommand(RequestCommand):
    def reset_json(self) -> TypeJson:
        return {"action": "reset"}

    def json(self) -> TypeJson:
        return super().json() | self.reset_json()


@dataclass
class VacuumRequestCommand(CommandAutoBuild):

    type: str = "request"


@dataclass
class RequestSetCommand(VacuumRequestCommand):

    action: str = "set"

    power: str | None = None
    cleaning: str | None = None
    beeping: str | None = None
    carpetbooster: str | None = None
    workingmode: VcWorkingMode | None = None
    suction: VcSuctionStrengths | None = None
    water: str | None = None
    direction: str | None = None
    commissioninfo: str | None = None
    calibrationtime: str | None = None

    # def set_json(self) -> TypeJson:
    #     return {"action": "set"}

    # def json(self) -> TypeJson:
    #     return super().json() | self.set_json()


class RoutineCommandActions(str, Enum):
    ACTION = "action"
    COUNT = "count"
    LIST = "list"
    DELETE = "delete"
    START = "start"
    PUT = "put"


@dataclass
class RoutineCommand(RequestCommand):
    type: MessageCommandType = MessageCommandType.ROUTINE
    action: RoutineCommandActions = RoutineCommandActions.ACTION
    id: str | None = None
    scene: str | None = None
    commands: str | None = None

    def routine_json(self) -> TypeJson:
        r: TypeJson = TypeJson()
        r["action"] = self.action
        if self.id is not None:
            r["id"] = self.id
        if self.scene is not None:
            r["scene"] = self.scene
        if self.commands is not None:
            r["commands"] = self.commands
        return r

    def json(self) -> TypeJson:
        return super().json() | self.routine_json()


async def create_device_message(
    args: argparse.Namespace,
    args_in: list[Any],
    send_to_devices_callable: Callable[[argparse.Namespace], Any],
    msg_queue: list[Command],
    # message_queue_tx_command_cloud: list[Any],
    # message_queue_tx_state_cloud: list[Any],
) -> None:
    """process_args_to_msg_cleaner"""

    # def local_and_cloud_command_msg(json_msg: TypeJson, timeout: int) -> None:
    #     message_queue_tx_local.append((json.dumps(json_msg), timeout))
    #     message_queue_tx_command_cloud.append(json_msg)

    if args.command is not None:

        if args.command == "productinfo":
            msg_queue.append(ProductinfoCommand())  # .json(), 100)

        if args.command == CommandType.GET.name:
            get_command(args, msg_queue)

        elif args.command == CommandType.SET.name:
            set_command(args, msg_queue)

        elif args.command == CommandType.RESET.name:
            reset_command(args, msg_queue)

        elif args.command == "routine":
            routine(args)


def get_command(args: argparse.Namespace, msq_queue: list[Command]) -> None:
    """Get command."""

    get_dict: dict[str, Any] = RequestGetCommand().json()
    if args.power or args.all:
        get_dict["power"] = None
    if args.cleaning or args.all:
        get_dict["cleaning"] = None
    if args.beeping or args.all:
        get_dict["beeping"] = None
    if args.battery or args.all:
        get_dict["battery"] = None
    if args.sidebrush or args.all:
        get_dict["sidebrush"] = None
    if args.rollingbrush or args.all:
        get_dict["rollingbrush"] = None
    if args.filter or args.all:
        get_dict["filter"] = None
    if args.carpetbooster or args.all:
        get_dict["carpetbooster"] = None
    if args.area or args.all:
        get_dict["area"] = None
    if args.time or args.all:
        get_dict["time"] = None
    if args.calibrationtime or args.all:
        get_dict["calibrationtime"] = None
    if args.workingmode or args.all:
        get_dict["workingmode"] = None
    if args.workingstatus or args.all:
        get_dict["workingstatus"] = None
    if args.suction or args.all:
        get_dict["suction"] = None
    if args.water or args.all:
        get_dict["water"] = None
    if args.direction or args.all:
        get_dict["direction"] = None
    if args.errors or args.all:
        get_dict["errors"] = None
    if args.cleaningrec or args.all:
        get_dict["cleaningrec"] = None
    if args.equipmentmodel or args.all:
        get_dict["equipmentmodel"] = None
    if args.alarmmessages or args.all:
        get_dict["alarmmessages"] = None
    if args.commissioninfo or args.all:
        get_dict["commissioninfo"] = None
    if args.mcu or args.all:
        get_dict["mcu"] = None
    msq_queue.append(Command(_json=get_dict))  # , 1000)


def reset_command(args: argparse.Namespace, msq_queue: list[Command]) -> None:
    """Reset command."""

    reset_dict: dict[str, Any] = RequestResetCommand().json()

    if args.sidebrush:
        reset_dict["sidebrush"] = None
    if args.rollingbrush:
        reset_dict["rollingbrush"] = None
    if args.filter:
        reset_dict["filter"] = None
    msq_queue.append(Command(_json=reset_dict))


def set_command(args: argparse.Namespace, msq_queue: list[Command]) -> None:
    """Set command."""

    cmd: Command | None = None

    if args.power is not None:
        cmd = RequestSetCommand(power=args.power)
    if args.cleaning is not None:
        cmd = RequestSetCommand(cleaning=args.cleaning)
    if args.beeping is not None:
        cmd = RequestSetCommand(beeping=args.beeping)
    if args.carpetbooster is not None:
        cmd = RequestSetCommand(carpetbooster=args.carpetbooster)
    if args.workingmode is not None:
        cmd = RequestSetCommand(workingmode=VcWorkingMode[args.workingmode])
    if args.suction is not None:
        suction: VcSuctionStrengths = VcSuctionStrengths[args.suction]
        cmd = RequestSetCommand(suction=suction)
    if args.water is not None:
        cmd = RequestSetCommand(water=args.water)
    if args.direction is not None:
        cmd = RequestSetCommand(direction=args.direction)
    if args.commissioninfo is not None:
        cmd = RequestSetCommand(commissioninfo=args.commissioninfo)
    if args.calibrationtime is not None:
        cmd = RequestSetCommand(calibrationtime=args.calibrationtime)

    if cmd:
        msq_queue.append(cmd)


def routine(args: argparse.Namespace) -> None:
    """Set routine."""

    routine_dict: dict[str, str] = RoutineCommand().json()

    if args.count:
        # routine_dict["action"] = "count"
        routine_dict = RoutineCommand(
            action=RoutineCommandActions.COUNT
        ).json()

    if args.list:
        # routine_dict["action"] = "list"
        routine_dict = RoutineCommand(action=RoutineCommandActions.LIST).json()

    if args.put:
        if args.id and args.commands:
            routine_dict = RoutineCommand(
                action=RoutineCommandActions.PUT,
                id=args.id,
                scene="none",
                commands=args.commands,
            ).json()
            # routine_dict["action"] = "put"
            # routine_dict["id"] = args.id
            # routine_dict["scene"] = "none"
            # routine_dict["commands"] = args.commands
        else:
            LOGGER.error("No ID and/or Commands given!")

    if args.delete:
        if args.id:
            routine_dict["action"] = "delete"
            routine_dict["id"] = args.id
        else:
            LOGGER.error("No ID to delete given!")

    if args.start:
        if args.id:
            routine_dict["action"] = "start"
            routine_dict["id"] = args.id


def add_command_args_cleaner(parser: argparse.ArgumentParser) -> None:
    """Add command parse arguments."""

    sub: argparse._SubParsersAction[
        argparse.ArgumentParser
    ] = parser.add_subparsers(title="subcommands", dest="command")

    sub.add_parser(
        "passive", help="vApp will passively listen for UDP SYN from devices"
    )

    ota: argparse.ArgumentParser = sub.add_parser(
        "ota", help="allows over the air programming of the device"
    )
    ota.add_argument("url", help="specify http URL for ota")

    sub.add_parser("ping", help="send a ping and nothing else")

    sub.add_parser(
        "factory-reset",
        help=(
            "trigger a factory reset on the device - the device has to be"
            " onboarded again afterwards)"
        ),
    )

    sub.add_parser("reboot", help="trigger a reboot")

    sub.add_parser("productinfo", help="get product information")

    req: argparse.ArgumentParser = sub.add_parser(
        CommandType.GET.name, help="send state request"
    )
    req.add_argument(
        "--all",
        help="If this flag is set, the whole state will be requested",
        action="store_true",
    )
    req.add_argument(
        "--power",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--cleaning",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--beeping",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--battery",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--sidebrush",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--rollingbrush",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--filter",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--carpetbooster",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--area",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--time",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--calibrationtime",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--workingmode",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--workingstatus",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--suction",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--water",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--direction",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--errors",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--cleaningrec",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--equipmentmodel",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--alarmmessages",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument(
        "--commissioninfo",
        help="If this flag is set, the state element will be requested",
        action="store_true",
    )
    req.add_argument("--mcu", help="Ask if mcu is online", action="store_true")

    # device specific
    set_parser = sub.add_parser(
        CommandType.SET.name,
        help="enables use of the vc1 control arguments and will control vc1",
    )
    set_parser.add_argument(
        "--power", choices=["on", "off"], help="turn power on/off"
    )
    set_parser.add_argument(
        "--cleaning", choices=["on", "off"], help="turn cleaning on/off"
    )
    set_parser.add_argument(
        "--beeping",
        choices=["on", "off"],
        help="enable/disable the find-vc function",
    )
    set_parser.add_argument(
        "--carpetbooster",
        metavar="strength",
        type=int,
        help="set the carpet booster strength (0-255)",
    )
    set_parser.add_argument(
        "--workingmode",
        choices=[m.name for m in VcWorkingMode],
        help="set the working mode",
    )
    set_parser.add_argument(
        "--water", choices=["LOW", "MID", "HIGH"], help="set water quantity"
    )
    set_parser.add_argument(
        "--suction",
        choices=[m.name for m in VcSuctionStrengths],
        help="set suction power",
    )
    set_parser.add_argument(
        "--direction",
        choices=["FORWARDS", "BACKWARDS", "TURN_LEFT", "TURN_RIGHT", "STOP"],
        help="manually control movement",
    )
    set_parser.add_argument(
        "--commissioninfo",
        type=str,
        help="set up to 256 characters of commisioning info",
    )
    set_parser.add_argument(
        "--calibrationtime",
        metavar="time",
        type=int,
        help="set the calibration time (1-1999999999)",
    )

    reset_parser = sub.add_parser(
        CommandType.RESET.name, help="enables resetting consumables"
    )
    reset_parser.add_argument(
        "--sidebrush",
        help="resets the sidebrush life counter",
        action="store_true",
    )
    reset_parser.add_argument(
        "--rollingbrush",
        help="resets the rollingbrush life counter",
        action="store_true",
    )
    reset_parser.add_argument(
        "--filter", help="resets the filter life counter", action="store_true"
    )

    routine_parser = sub.add_parser("routine", help="routine functions")
    routine_parser.add_argument(
        "--list",
        help="lists stored routines",
        action="store_const",
        const=True,
        default=False,
    )
    routine_parser.add_argument(
        "--put",
        help="store new routine",
        action="store_const",
        const=True,
        default=False,
    )
    routine_parser.add_argument(
        "--delete",
        help="delete routine",
        action="store_const",
        const=True,
        default=False,
    )
    routine_parser.add_argument(
        "--start",
        help="start routine",
        action="store_const",
        const=True,
        default=False,
    )
    routine_parser.add_argument(
        "--id", help="specify routine id to act on (for put, start, delete)"
    )
    routine_parser.add_argument(
        "--scene", help="specify routine scene label (for put)"
    )
    routine_parser.add_argument(
        "--count", help="get the current free slots for routines", type=bool
    )
    routine_parser.add_argument(
        "--commands", help="specify routine program (for put)"
    )
    # routine_parser.set_defaults(func=routine_request)
