"""Vacuum cleaner"""
from __future__ import annotations
import argparse
from enum import Enum
from typing import Any

from klyqa_ctl.devices.device import *
from klyqa_ctl.general.general import get_obj_attr_values_as_string

class VcWorkingStatus(Enum):
    SLEEP = 0
    STANDBY = 1
    CLEANING = 2
    CLEANING_AUTO = 3
    CLEANING_RANDOM = 4
    CLEANING_SROOM = 5
    CLEANING_EDGE = 6
    CLEANING_SPOT = 7
    CLEANING_COMP = 8
    DOCKING = 9
    CHARGING = 10
    CHARGING_DC = 11
    CHARGING_COMP = 12
    ERROR = 13

class VcSuctionStrengths(Enum):
    NULL = 0
    STRONG = 1
    SMALL = 2
    NORMAL = 3
    MAX = 4

class VcWorkingMode(Enum):
    STANDBY = 0
    RANDOM = 1
    SMART = 2
    WALL_FOLLOW = 3
    MOP = 4
    SPIRAL = 5
    PARTIAL_BOW = 6
    SROOM = 7
    CHARGE_GO = 8

class CommandType(Enum):
    GET = 0
    SET = 1
    RESET = 2


class KlyqaVCResponseStatus(KlyqaDeviceResponse):
    """KlyqaVCResponseStatus"""

    # Decrypted:  b'{"type":"statechange","mcu":"online","power":"on",
    # "cleaning":"on","beeping":"off","battery":57,"sidebrush":10,
    # "rollingbrush":30,"filter":60,"carpetbooster":200,"area":999,
    # "time":999,"calibrationtime":19999999,"workingmode":null,
    # "workingstatus":"STANDBY","suction":"MID","water":"LOW","direction":"STOP",
    # "errors":["COLLISION","GROUND_CHECK","LEFT_WHEEL","RIGHT_WHEEL","SIDE_SCAN","MID_SWEEP","FAN","TRASH","BATTERY","ISSUES"],
    # "cleaningrec":[],"equipmentmodel":"","alarmmessages":"","commissioninfo":"","action":"get"}

    def __str__(self) -> str:
        """__str__"""
        return get_obj_attr_values_as_string(self)

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        """__init__"""
        self.action: str = ""
        self.active_command: int = -1
        self.alarmmessages: str = ""
        self.area: int = -1
        self.beeping: str = ""
        self.battery: str = ""
        self.calibrationtime: int = -1
        self.carpetbooster: int = -1
        self.cleaning: str = ""
        self.cleaningrec: list[str] = []
        self.connected: bool = False
        self.commissioninfo: str = ""
        self.direction: str = ""
        self.errors: list[str] = []
        self.equipmentmodel: str = ""
        self.filter: int = -1
        self.filter_tresh: int = -1
        self.fwversion: str = ""
        self.id: str = ""
        self.lastActivityTime: str = ""
        self.map_parameter: str = ""
        self.mcuversion: str = ""
        self.open_slots: int = -1
        self.power: str = ""
        self.rollingbrush_tresh: int = -1
        self.rollingbrush: int = -1
        self.sdkversion: str = ""
        self.sidebrush: str = ""
        self.sidebrush_tresh: int = -1
        self.suction: int | None = None
        self.time: int = -1
        self.ts: datetime.datetime = datetime.datetime.now()
        self.watertank: str = ""
        self.workingmode: int | None = None
        self.workingstatus: int | None = None

        LOGGER.debug(f"save status {self}")
        super().__init__(**kwargs)

    def update(self, **kwargs: Any) -> None:
        super().update(**kwargs)


class VacuumCleaner(Device):
    """vaccum cleaner"""

    def __init__(self) -> None:
        super().__init__()
        # self.status = KlyqaVCResponseStatus()
        self.response_classes["status"] = KlyqaVCResponseStatus


def add_command_args_cleaner(parser: argparse.ArgumentParser) -> None:
    """Add command parse arguments."""

    sub: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(title="subcommands", dest="command")

    sub.add_parser(
        "passive", help="vApp will passively listen for UDP SYN from devices"
    )

    ota: argparse.ArgumentParser = sub.add_parser("ota", help="allows over the air programming of the device")
    ota.add_argument("url", help="specify http URL for ota")

    sub.add_parser("ping", help="send a ping and nothing else")

    sub.add_parser(
        "factory-reset",
        help="trigger a factory reset on the device - the device has to be onboarded again afterwards)",
    )

    sub.add_parser("reboot", help="trigger a reboot")

    sub.add_parser("productinfo", help="get product information")

    req: argparse.ArgumentParser = sub.add_parser(CommandType.GET.name, help="send state request")
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
    set_parser.add_argument("--power", choices=["on", "off"], help="turn power on/off")
    set_parser.add_argument(
        "--cleaning", choices=["on", "off"], help="turn cleaning on/off"
    )
    set_parser.add_argument(
        "--beeping", choices=["on", "off"], help="enable/disable the find-vc function"
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
        "--sidebrush", help="resets the sidebrush life counter", action="store_true"
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
        "--start", help="start routine", action="store_const", const=True, default=False
    )
    routine_parser.add_argument(
        "--id", help="specify routine id to act on (for put, start, delete)"
    )
    routine_parser.add_argument("--scene", help="specify routine scene label (for put)")
    routine_parser.add_argument(
        "--count", help="get the current free slots for routines", type=bool
    )
    routine_parser.add_argument("--commands", help="specify routine program (for put)")
    # routine_parser.set_defaults(func=routine_request)

