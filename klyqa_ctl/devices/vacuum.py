"""Vacuum cleaner"""
from __future__ import annotations
import argparse
from enum import Enum
import json
from typing import Type, Any
from .device import *
from ..general.general import get_obj_attr_values_as_string

## Vacuum Cleaner ##

VC_WORKINGSTATUS = Enum(
    "VC_WORKINGSTATUS",
    "SLEEP STANDBY CLEANING CLEANING_AUTO CLEANING_RANDOM CLEANING_SROOM CLEANING_EDGE CLEANING_SPOT CLEANING_COMP DOCKING CHARGING CHARGING_DC CHARGING_COMP ERROR",
)

VC_SUCTION_STRENGTHS = Enum(
    "VC_SUCTION_STRENGTHS",
    "NULL STRONG SMALL NORMAL MAX",
)

VC_WORKINGMODE = Enum(
    "VC_WORKINGMODE",
    "STANDBY RANDOM SMART WALL_FOLLOW MOP SPIRAL PARTIAL_BOW SROOM CHARGE_GO",
)


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
        **kwargs,
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

    def update(self, **kwargs) -> None:
        super().update(**kwargs)


class KlyqaVC(KlyqaDevice):
    """Klyqa vaccum cleaner"""

    # status: KlyqaVCResponseStatus = None

    def __init__(self) -> None:
        super().__init__()
        # self.status = KlyqaVCResponseStatus()
        self.response_classes["status"] = KlyqaVCResponseStatus


CommandType = Enum("CommandType", "get set reset")


def add_command_args_cleaner(parser: argparse.ArgumentParser) -> None:

    sub = parser.add_subparsers(title="subcommands", dest="command")

    pssv = sub.add_parser(
        "passive", help="vApp will passively listen for UDP SYN from devices"
    )

    ota = sub.add_parser("ota", help="allows over the air programming of the device")
    ota.add_argument("url", help="specify http URL for ota")

    ping = sub.add_parser("ping", help="send a ping and nothing else")

    frs = sub.add_parser(
        "factory-reset",
        help="trigger a factory reset on the device - the device has to be onboarded again afterwards)",
    )

    reb = sub.add_parser("reboot", help="trigger a reboot")

    prd = sub.add_parser("productinfo", help="get product information")

    req = sub.add_parser(CommandType.get.name, help="send state request")
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
        CommandType.set.name,
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
        choices=[m.name for m in VC_WORKINGMODE],
        help="set the working mode",
    )
    set_parser.add_argument(
        "--water", choices=["LOW", "MID", "HIGH"], help="set water quantity"
    )
    set_parser.add_argument(
        "--suction",
        choices=[m.name for m in VC_SUCTION_STRENGTHS],
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
        CommandType.reset.name, help="enables resetting consumables"
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


async def process_args_to_msg_cleaner(
    args,
    args_in,
    send_to_devices_cb,
    message_queue_tx_local,
    message_queue_tx_command_cloud,
    message_queue_tx_state_cloud,
) -> None:
    """process_args_to_msg_cleaner"""

    def local_and_cloud_command_msg(json_msg, timeout) -> None:
        message_queue_tx_local.append((json.dumps(json_msg), timeout))
        message_queue_tx_command_cloud.append(json_msg)

    if args.command is not None:

        if args.command == "productinfo":
            local_and_cloud_command_msg(
                {"type": "request", "action": "productinfo"}, 100
            )

        if args.command == CommandType.get.name:
            get_dict: dict[str, Any] = {
                "type": "request",
                "action": "get",
            }
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
            local_and_cloud_command_msg(get_dict, 1000)

        elif args.command == CommandType.set.name:
            set_dict: dict[str, Any] = {"type": "request", "action": "set"}
            if args.power is not None:
                set_dict["power"] = args.power
            if args.cleaning is not None:
                set_dict["cleaning"] = args.cleaning
            if args.beeping is not None:
                set_dict["beeping"] = args.beeping
            if args.carpetbooster is not None:
                set_dict["carpetbooster"] = args.carpetbooster
            if args.workingmode is not None:
                mode: int = VC_WORKINGMODE[args.workingmode].value
                set_dict["workingmode"] = mode
            if args.suction is not None:
                suction: int = VC_SUCTION_STRENGTHS[args.suction].value
                set_dict["suction"] = suction - 1
            if args.water is not None:
                set_dict["water"] = args.water
            if args.direction is not None:
                set_dict["direction"] = args.direction
            if args.commissioninfo is not None:
                set_dict["commissioninfo"] = args.commissioninfo
            if args.calibrationtime is not None:
                set_dict["calibrationtime"] = args.calibrationtime
            local_and_cloud_command_msg(set_dict, 1000)

        elif args.command == CommandType.reset.name:
            reset_dict: dict[str, Any] = {"type": "request", "action": "reset"}
            if args.sidebrush:
                reset_dict["sidebrush"] = None
            if args.rollingbrush:
                reset_dict["rollingbrush"] = None
            if args.filter:
                reset_dict["filter"] = None
            local_and_cloud_command_msg(reset_dict, 1000)

        elif args.command == "routine":
            routine_dict = {
                "type": "routine",
            }

            if args.count:
                routine_dict["action"] = "count"

            if args.list:
                routine_dict["action"] = "list"

            if args.put:
                if args.id and args.commands:
                    routine_dict["action"] = "put"
                    routine_dict["id"] = args.id
                    routine_dict["scene"] = "none"
                    routine_dict["commands"] = args.commands
                else:
                    print("No ID and/or Commands given!")

            if args.delete:
                if args.id:
                    routine_dict["action"] = "delete"
                    routine_dict["id"] = args.id
                else:
                    print("No ID to delete given!")

            if args.start:
                if args.id:
                    routine_dict["action"] = "start"
                    routine_dict["id"] = args.id
