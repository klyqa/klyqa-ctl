"""Contains all functions for light commands."""
from __future__ import annotations

from abc import abstractmethod
import argparse
from dataclasses import dataclass
from enum import Enum
import json
import sys
from typing import Any, Callable

from klyqa_ctl.devices.device import CommandWithCheckValues, Device
from klyqa_ctl.devices.light.light import Light
from klyqa_ctl.devices.light.scenes import SCENES
from klyqa_ctl.general.general import (
    LOGGER,
    CloudStateCommand,
    Command,
    CommandType,
    CommandTyped,
    DeviceType,
    RgbColor,
    TypeJson,
)
from klyqa_ctl.general.parameters import (
    add_config_args,
    get_description_parser,
)

COMMANDS_TO_SEND: list[str] = [
    "request",
    "ping",
    "color",
    "temperature",
    "brightness",
    "routine_list",
    "routine_put",
    "routine_id",
    "routine_commands",
    "routine_delete",
    "routine_start",
    "power",
    "reboot",
    "factory_reset",
    "WW",
    "daylight",
    "CW",
    "nightlight",
    "relax",
    "TVtime",
    "comfort",
    "focused",
    "fireplace",
    "club",
    "romantic",
    "gentle",
    "summer",
    "jungle",
    "ocean",
    "fall",
    "sunset",
    "party",
    "spring",
    "forest",
    "deep_sea",
    "tropical",
    "magic",
    "mystic",
    "cotton",
    "ice",
]


class CheckDeviceParameter(Enum):
    COLOR = (0,)
    BRIGHTNESS = 1
    TEMPERATURE = 2
    SCENE = 3


@dataclass
class RequestCommand(CommandTyped):
    def __post_init__(self) -> None:
        self.type = CommandType.REQUEST.value


@dataclass
class PingCommand(CommandTyped):
    def __post_init__(self) -> None:
        self.type = CommandType.PING.value


@dataclass
class FwUpdateCommand(CommandTyped):
    url: str = ""

    def __post_init__(self) -> None:
        self.type = CommandType.FW_UPDATE.value

    def url_json(self) -> TypeJson:
        return {"url": self.url}

    def json(self) -> TypeJson:
        return super().json() | self.url_json()


@dataclass
class TransitionCommand(RequestCommand):
    transition_time: int = 0

    def json(self) -> TypeJson:
        return super().json() | {"transitionTime": self.transition_time}


@dataclass
class CommandWithCheckValuesLight(CommandWithCheckValues):
    _light: Light | None = None

    @abstractmethod
    def check_values(self, device: Device) -> bool:
        if not isinstance(device, Light):
            return False
        self._light = device
        return True


@dataclass
class ColorCommand(
    CommandWithCheckValuesLight, TransitionCommand, CloudStateCommand
):
    color: RgbColor = RgbColor(0, 0, 0)

    def color_json(self) -> TypeJson:
        return {
            "color": {
                "red": self.color.r,
                "green": self.color.g,
                "blue": self.color.b,
            }
        }

    def json(self) -> TypeJson:
        return super().json() | self.color_json()

    def check_values(self, device: Device) -> bool:
        """Check device color range."""
        if not super().check_values(device) or not self._light:
            return False
        values: list = [self.color.r, self.color.g, self.color.b]
        if (not self._light.ident or not self._light.color_range) and (
            not self._light.ident
            or missing_config(self._force, self._light.ident.product_id)
        ):
            return False
        elif self._light.color_range:
            for value in values:
                if (
                    int(value) < self._light.color_range.min
                    or int(value) > self._light.color_range.max
                ):
                    return forced_continue(
                        self._force,
                        f"Color {value} out of range"
                        f" [{self._light.color_range.min}.."
                        f"{self._light.color_range.max}].",
                    )
        return True


@dataclass
class TemperatureCommand(
    CommandWithCheckValuesLight, TransitionCommand, CloudStateCommand
):
    temperature: int = 0

    def temperature_json(self) -> TypeJson:
        return {"temperature": self.temperature}

    def json(self) -> TypeJson:
        return super().json() | self.temperature_json()

    def check_values(self, device: Device) -> bool:
        """Check device temperature range."""
        if not super().check_values(device) or not self._light:
            return False
        value: int = self.temperature

        if (not self._light.ident or not self._light.temperature_range) and (
            not self._light.ident
            or missing_config(self._force, self._light.ident.product_id)
        ):
            return False
        elif self._light.temperature_range:
            if (
                int(value) < self._light.temperature_range.min
                or int(value) > self._light.temperature_range.max
            ):
                return forced_continue(
                    self._force,
                    f"Temperature {value} out of range"
                    f" [{self._light.temperature_range.min}.."
                    f"{self._light.temperature_range.max}].",
                )
        return True


@dataclass
class BrightnessCommand(
    CommandWithCheckValuesLight, TransitionCommand, CloudStateCommand
):
    brightness: int = 0

    def brightness_json(self) -> TypeJson:
        return {
            "brightness": {
                "percentage": self.brightness,
            }
        }

    def json(self) -> TypeJson:
        return super().json() | self.brightness_json()

    def check_values(self, device: Device) -> bool:
        if not super().check_values(device) or not self._light:
            return False
        value: int = self.brightness

        if (not self._light.ident or not self._light.brightness_range) and (
            not self._light.ident
            or missing_config(self._force, self._light.ident.product_id)
        ):
            return False
        elif self._light.brightness_range:
            if (
                int(value) < self._light.brightness_range.min
                or int(value) > self._light.brightness_range.max
            ):
                return forced_continue(
                    self._force,
                    f"Brightness {value} out of range"
                    f" [{self._light.brightness_range.min}.."
                    f"{self._light.brightness_range.max}].",
                )
        return True

        # return check_brightness_range(force, device, value = self.brightness)


class ExternalSourceProtocol(str, Enum):
    EXT_OFF = "EXT_OFF"
    EXT_UDP = "EXT_UDP"
    EXT_E131 = "EXT_E131"
    EXT_TPM2 = "EXT_TPM2"


@dataclass
class ExternalSourceCommand(CommandWithCheckValues, RequestCommand):
    protocol: ExternalSourceProtocol = ExternalSourceProtocol.EXT_OFF
    port: int = 0
    channel: int = 0

    def json(self) -> TypeJson:
        return super().json() | {
            "external": {
                "mode": self.protocol,
                "port": self.port,
                "channel": self.channel,
            }
        }

    def check_values(self, device: Device) -> bool:
        return True

        # return check_external_source_command(
        #     force, device, value=self.brightness
        # )


# Functions
# def color_message(red: str, green: str, blue: str, transition_time: int
#                   ) -> Command:
#     """Create message for color change."""
#     return Command(
#         {
#             "type": "request",
#             "color": {
#                 "red": red,
#                 "green": green,
#                 "blue": blue,
#             },
#             "transitionTime": transition_time,
#         },
#         transition_time,
#     )

# def temperature_message(temperature: str, transition_time: int
# ) -> CommandTyped:
#     """Create message for temperature change in kelvin."""
#     return CommandTyped(
#         {
#             "type": "request",
#             "temperature": temperature,
#             "transitionTime": transition_time,
#         }        ,
#         transition_time,
#     )


def percent_color_message(
    red: str, green: str, blue: str, warm: str, cold: str, transition_time: int
) -> tuple[str, int]:
    """Create message for color change in percent."""
    return (
        json.dumps(
            {
                "type": "request",
                "p_color": {
                    "red": red,
                    "green": green,
                    "blue": blue,
                    "warm": warm,
                    "cold": cold,
                    # "brightness" : brightness
                },
                "transitionTime": transition_time,
            }
        ),
        transition_time,
    )


# def brightness_message(brightness: str, transition: int) -> tuple[str, int]:
#     """Create message for brightness set."""
#     return (
#         json.dumps(
#             {
#                 "type": "request",
#                 "brightness": {
#                     "percentage": brightness,
#                 },
#                 "transitionTime": transition,
#             }
#         ),
#         transition,
#     )


def external_source_message(
    protocol: int, port: int, channel: int
) -> TypeJson:
    """Create external source protocol message."""
    protocol_str: str
    if protocol == 0:
        protocol_str = "EXT_OFF"
    elif protocol == 1:
        protocol_str = "EXT_UDP"
    elif protocol == 2:
        protocol_str = "EXT_E131"
    elif protocol == 3:
        protocol_str = "EXT_TPM2"
    else:
        protocol_str = "EXT_OFF"
    return {
        "type": "request",
        "external": {
            "mode": protocol_str,
            "port": int(port),
            "channel": int(channel),
        },
    }


def add_command_args_bulb(parser: argparse.ArgumentParser) -> None:
    """Add arguments to the argument parser object.

    Args:
        parser: Parser object
    """
    parser.add_argument(
        "--transitionTime",
        nargs=1,
        help="transition time in milliseconds",
        default=[0],
    )

    parser.add_argument(
        "--color", nargs=3, help="set color command (r,g,b) 0-255"
    )
    parser.add_argument(
        "--temperature",
        nargs=1,
        help=(
            "set temperature command (in kelvin, range depends on lamp"
            " profile) (lower: warm, higher: cold)"
        ),
    )
    parser.add_argument(
        "--brightness", nargs=1, help="set brightness in percent 0-100"
    )
    parser.add_argument(
        "--percent_color",
        nargs=5,
        metavar=("RED", "GREEN", "BLUE", "WARM", "COLD"),
        help="set colors and white tones in percent 0 - 100",
    )
    parser.add_argument("--ota", nargs=1, help="specify http URL for ota")
    parser.add_argument(
        "--ping",
        help="send ping",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--request",
        help="send status request",
        action="store_const",
        const=True,
        default=False,
    )

    # TODO: currently not fully implemented
    # parser.add_argument(
    #     "--identity",
    #     help="send status request",
    #     action="store_const",
    #     const=True,
    #     default=False,
    # )

    parser.add_argument(
        "--factory_reset",
        help=(
            "trigger a factory reset on the device (Warning: device has to be"
            " onboarded again afterwards)"
        ),
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_list",
        help="lists stored routines",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_put",
        help="store new routine",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_delete",
        help="delete routine",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_start",
        help="start routine",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_id",
        help="specify routine id to act on (for put, start, delete)",
    )
    parser.add_argument(
        "--routine_scene", help="specify routine scene label (for put)"
    )
    parser.add_argument(
        "--routine_commands", help="specify routine program (for put)"
    )
    parser.add_argument(
        "--reboot",
        help="trigger a reboot",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--power", nargs=1, metavar='"on"/"off"', help="turns the bulb on/off"
    )
    parser.add_argument(
        "--enable_tb", nargs=1, help="enable thingsboard connection (yes/no)"
    )

    parser.add_argument(
        "--fade",
        nargs=2,
        help="fade in/out time in milliseconds on powering device on/off",
        metavar=("IN", "OUT"),
    )

    parser.add_argument(
        "--external_source",
        nargs=3,
        metavar=("MODE", "PORT", "CHANNEL"),
        help="set external protocol receiver 0=OFF 1=RAWUDP 2=E131 2=TMP2",
    )

    # parser.add_argument("--loop", help="loop", action="store_true")
    parser.add_argument("--WW", help="Warm White", action="store_true")
    parser.add_argument("--daylight", help="daylight", action="store_true")
    parser.add_argument("--CW", help="Cold White", action="store_true")
    parser.add_argument("--nightlight", help="nightlight", action="store_true")
    parser.add_argument("--relax", help="relax", action="store_true")
    parser.add_argument("--TVtime", help="TVtime", action="store_true")
    parser.add_argument("--comfort", help="comfort", action="store_true")
    parser.add_argument("--focused", help="focused", action="store_true")
    parser.add_argument("--fireplace", help="fireplace", action="store_true")
    parser.add_argument("--club", help="club", action="store_true")
    parser.add_argument("--romantic", help="romantic", action="store_true")
    parser.add_argument("--gentle", help="gentle", action="store_true")
    parser.add_argument("--summer", help="summer", action="store_true")
    parser.add_argument("--jungle", help="jungle", action="store_true")
    parser.add_argument("--ocean", help="ocean", action="store_true")
    parser.add_argument("--fall", help="fall", action="store_true")
    parser.add_argument("--sunset", help="sunset", action="store_true")
    parser.add_argument("--party", help="party", action="store_true")
    parser.add_argument("--spring", help="spring", action="store_true")
    parser.add_argument("--forest", help="forest", action="store_true")
    parser.add_argument("--deep_sea", help="deep_sea", action="store_true")
    parser.add_argument("--tropical", help="tropical", action="store_true")
    parser.add_argument("--magic", help="magic Mood", action="store_true")
    parser.add_argument(
        "--mystic", help="Mystic Mountain", action="store_true"
    )
    parser.add_argument("--cotton", help="Cotton Candy", action="store_true")
    parser.add_argument("--ice", help="Ice Cream", action="store_true")


async def discover_devices(
    args: argparse.Namespace,
    args_in: list[Any],
    send_to_devices_cb: Callable[[argparse.Namespace], Any],
) -> argparse.Namespace | None:

    """Send out klyqa broadcast to discover all devices. Tries to set
    device_unitids in args parse. The user can select them.

    Params:
        args (Argsparse): Parsed args object
        args_in (list): List of arguments parsed to the script call
        timeout_ms (int, optional): Timeout to send. Defaults to 5000.

    Raises:
        Exception: Network or file errors

    Returns:
        bool: True if succeeded.
    """

    discover_local_args: list[str] = [
        DeviceType.LIGHTING.value,
        "--request",
        "--allDevices",
        "--selectDevice",
        "--discover",
    ]

    orginal_args_parser: argparse.ArgumentParser = get_description_parser()
    discover_local_args_parser: argparse.ArgumentParser = (
        get_description_parser()
    )

    add_config_args(parser=orginal_args_parser)
    add_config_args(parser=discover_local_args_parser)
    add_command_args_bulb(parser=discover_local_args_parser)

    original_config_args_parsed, _ = orginal_args_parser.parse_known_args(
        args=args_in
    )

    discover_local_args_parsed = discover_local_args_parser.parse_args(
        discover_local_args, namespace=original_config_args_parsed
    )

    uids: set | list | str = await send_to_devices_cb(
        discover_local_args_parsed
    )
    if isinstance(uids, set) or isinstance(uids, list):
        args_in = ["--device_unitids", ",".join(list(uids))] + args_in
    elif isinstance(uids, str) and uids == "no_devices":
        return None
    else:
        LOGGER.error("Error during local discovery of the devices.")
        return None

    add_command_args_bulb(parser=orginal_args_parser)
    args = orginal_args_parser.parse_args(args=args_in, namespace=args)
    return args


async def create_device_message(
    args: argparse.Namespace,
    args_in: list[Any],
    send_to_devices_callable: Callable[[argparse.Namespace], Any],
    message_queue_tx_local: list[Any],
    message_queue_tx_command_cloud: list[Any],
    message_queue_tx_state_cloud: list[Any],
    scene_list: list[str],
) -> bool:
    """

    Process arguments for communicating with lights. Fill message queues for
    local and cloud communication. Discover devices to communicate with.

    Params:
        args: Parsed arguments to be processed.
        args_in: Original arguments as a list, if we want to reparse and add
            arguments.
        send_to_devices_callable: If we need to send something to the lamps,
            use this callable.
        message_queue_tx_local: Queue to be filled with messages for local
            communication.
        message_queue_tx_command_cloud: Queue for cloud command messages.
        message_queue_tx_state_cloud: Queue for cloud state messages.
        scene_list: If a scene is applied, add it to the scene list, so the
            klyqa-ctl send function can process it.

    """

    def local_and_cloud_command_msg(
        json_msg: Command,
    ) -> None:  # , check_func: Callable | None = None) -> None:
        """Add message to local and cloud queue. Give a timeout after the
        message was sent. Give also a check function for the values that
        are send to be in limits (device config).
        """
        # msg: tuple[str, int] = (json.dumps(json_msg), timeout)
        # if check_func:
        #     msg = msg + (check_func,)
        message_queue_tx_local.append(json_msg)
        message_queue_tx_command_cloud.append(json_msg.json())

    # needs rewrite
    ## TODO: Missing cloud discovery and interactive device selection. Send to
    ## devices if given as argument working.
    # if (args.local or args.tryLocalThanCloud) and (
    #     not args.device_name
    #     and not args.device_unitids
    #     and not args.allDevices
    #     and not args.discover
    # ):
    #     args_ret: argparse.Namespace | None = await self.discover_devices(
    #         args, args_in, send_to_devices_callable
    #     )

    #     if isinstance(args_ret, argparse.Namespace):
    #         args = args_ret

    commands_to_send: list[str] = [
        i for i in COMMANDS_TO_SEND if hasattr(args, i) and getattr(args, i)
    ]

    if commands_to_send:
        LOGGER.info(
            "Commands to send to devices: " + ", ".join(commands_to_send)
        )
    else:
        if not await commands_select(args, args_in, send_to_devices_callable):
            return False

    if args.ota is not None:
        local_and_cloud_command_msg(FwUpdateCommand(args.ota))

    if args.ping:
        local_and_cloud_command_msg(PingCommand())

    if args.request:
        local_and_cloud_command_msg(RequestCommand())

    # needs new command class
    # if args.external_source:
    #     mode, port, channel = args.external_source
    #     local_and_cloud_command_msg(
    #         # ExternalSourceCommand(protocol=, port=int(port),
    # channel=int(channel)).json()
    #         external_source_message(int(mode), port, channel)
    #         , 0
    #     )

    if args.enable_tb is not None:
        enable_tb(args, message_queue_tx_local)

    if args.passive:
        pass

    if args.power:
        message_queue_tx_local.append(
            PowerCommand(status=args.power[0])
            # Command(_json={"type": "request", "status": args.power[0]})
        )
        message_queue_tx_state_cloud.append({"status": args.power[0]})

    if args.color is not None:
        command_color(
            args, message_queue_tx_local, message_queue_tx_state_cloud
        )

    if args.percent_color is not None:
        command_color_percent(
            args, message_queue_tx_local, message_queue_tx_state_cloud
        )

    if args.temperature is not None:
        command_temperature(
            args, message_queue_tx_local, message_queue_tx_state_cloud
        )

    if args.brightness is not None:
        command_brightness(
            args, message_queue_tx_local, message_queue_tx_state_cloud
        )

    if args.factory_reset:
        local_and_cloud_command_msg(
            FactoryResetCommand()
            # Command(_json={"type": "factory_reset", "status": args.power[0]})
        )

    # needs new command classes
    if args.fade is not None and len(args.fade) == 2:
        #     local_and_cloud_command_msg(
        #         {"type": "request", "fade_out": args.fade[1],
        # "fade_in": args.fade[0]}, 500
        #     )
        local_and_cloud_command_msg(
            FadeCommand(fade_in=args.fade[0], fade_out=args.fade[1])
            # Command(
            #     _json={
            #         "type": "request",
            #         "fade_out": args.fade[1],
            #         "fade_in": args.fade[0],
            #     }
            # )
        )

    if args.reboot:
        # local_and_cloud_command_msg(Command(_json={"type": "reboot"}))
        local_and_cloud_command_msg(RebootCommand())

    routine_scene(args, scene_list)
    # return False

    if args.routine_list:
        # local_and_cloud_command_msg({"type": "routine", "action": "list"},
        # 500)
        local_and_cloud_command_msg(
            # Command(_json={"type": "routine", "action": "list"})
            RoutineListCommand()
        )

    if args.routine_put and args.routine_id is not None:
        routine_put(args, local_and_cloud_command_msg)

    if args.routine_delete and args.routine_id is not None:
        local_and_cloud_command_msg(
            RoutineDeleteCommand(id=args.routine_id)
            # {"type": "routine", "action": "delete", "id": args.routine_id},
            # 500
        )
    if args.routine_start and args.routine_id is not None:
        local_and_cloud_command_msg(
            RoutineStartCommand(id=args.routine_id)
            # {"type": "routine", "action": "start", "id": args.routine_id},
            # 500
        )

    return True


# Needs clean up
async def commands_select(
    args: argparse.Namespace,
    args_in: list[str],
    send_to_devices_callable: Callable,
) -> bool:
    """Interactive command select."""
    # print("Commands (arguments):")
    # print(sep_width * "-")

    # def get_temp_range(product_id: str) -> bool | tuple[int,int]:
    #     temperature_enum = []
    #     if not self.device_config:
    #         return False
    #     try:
    #         temperature_enum = [
    #             trait["value_schema"]["properties"]["colorTemperature"]["enum"]
    #             if "properties" in trait["value_schema"]
    #             else trait["value_schema"]["enum"]
    #             for trait in self.device_config["deviceTraits"]
    #             if trait["trait"] == "@core/traits/color-temperature"
    #         ]
    #         if len(temperature_enum[0]) < 2:
    #             raise Exception()
    #     except:
    #         return False
    #     return temperature_enum[0]

    # def get_inner_range(tup1: Any, tup2: Any) -> tuple[int, int]:
    #     return (
    #         tup1[0] if tup1[0] > tup2[0] else tup2[0],
    #         tup1[1] if tup1[1] < tup2[1] else tup2[1],
    #     )

    # temperature_enum: tuple[int, int] = tuple()
    # color: list[int] = [0, 255]
    # brightness: tuple[int, int] = (0,100)
    # u_id: str
    # for u_id in args.device_unitids[0].split(","):
    #     u_id = format_uid(u_id)
    #     # fix self devices
    #     if u_id not in self.devices or not self.devices[u_id].ident:

    #         async def send_ping() -> bool:
    #             discover_local_args2: list[str] = [
    #                 "--ping",
    #                 "--device_unitids",
    #                 u_id,
    #             ]

    #             orginal_args_parser: argparse.ArgumentParser = (
    #                 get_description_parser()
    #             )
    #             discover_local_args_parser2: argparse.ArgumentParser = (
    #                 get_description_parser()
    #             )

    #             add_config_args(parser=orginal_args_parser)
    #             add_config_args(parser=discover_local_args_parser2)
    #             add_command_args_bulb(parser=discover_local_args_parser2)

    #             (
    #                 original_config_args_parsed,
    #                 _,
    #             ) = orginal_args_parser.parse_known_args(args=args_in)

    #             discover_local_args_parsed2 = (
    #                 discover_local_args_parser2.parse_args(
    #                     discover_local_args2,
    #                     namespace=original_config_args_parsed,
    #                 )
    #             )

    #             ret = send_to_devices_callable(discover_local_args_parsed2)
    #             if isinstance(ret, bool) and ret:
    #                 return True
    #             else:
    #                 return False

    #         ret: bool = await send_ping()
    #         if isinstance(ret, bool) and ret:
    #             product_id: str = self.devices[u_id].ident.product_id
    #         else:
    #             LOGGER.error(f"Device {u_id} not found.")
    #             return False
    #     product_id = self.devices[u_id].ident.product_id
    #     if not temperature_enum:
    #         temperature_enum = get_temp_range(product_id)
    #     else:
    #         temperature_enum = get_inner_range(
    #             temperature_enum, get_temp_range(product_id)
    #         )
    # arguments_send_to_device = {}
    # if temperature_enum:
    #     arguments_send_to_device = {
    #         "temperature": " ["
    #         + str(temperature_enum[0])
    #         + "-"
    #         + str(temperature_enum[1])
    #         + "] (Kelvin, low: warm, high: cold)"
    #     }

    # arguments_send_to_device: dict[str, str] = {
    #     **arguments_send_to_device,
    #     **{
    #         "color": f" rgb [{color[0]}..{color[1]}] [{color[0]}..{color[1]}]
    # [{color[0]}..{color[1]}]",
    #         "brightness": " ["
    #         + str(brightness[0])
    #         + ".."
    #         + str(brightness[1])
    #         + "]",
    #         "routine_commands": " [cmd]",
    #         "routine_id": " [int]",
    #         "power": " [on/off]",
    #     },
    # }

    # count: int = 1
    # for c in commands_send_to_bulb:
    #     args_to_b: str = (
    #         arguments_send_to_device[c] if c in arguments_send_to_device
    # else ""
    #     )
    #     LOGGER.info(str(count) + ") " + c + args_to_b)
    #     count = count + 1

    # cmd_c_id: int = int(input("Choose command number [1-9]*: "))
    # if cmd_c_id > 0 and cmd_c_id < count:
    #     args_in.append("--" + commands_send_to_bulb[cmd_c_id - 1])
    # else:
    #     LOGGER.error("No such command id " + str(cmd_c_id) + " available.")
    #     sys.exit(1)

    # if commands_send_to_bulb[cmd_c_id - 1] in arguments_send_to_device:
    #     args_app: str = input(
    #         "Set arguments (multiple arguments space separated) for command
    # [Enter]: "
    #     )
    #     if args_app:
    #         args_in.extend(args_app.split(" "))

    # parser: argparse.ArgumentParser = get_description_parser()

    # add_config_args(parser=parser)
    # add_command_args_bulb(parser=parser)

    # args = parser.parse_args(args_in, namespace=args)
    # # args.func(args)
    return True


def command_color(
    args: argparse.Namespace,
    message_queue_tx_local: list,
    message_queue_tx_state_cloud: list,
) -> None:
    """Command for setting the color."""
    r: str
    g: str
    b: str
    r, g, b = args.color

    tt: int = int(args.transitionTime[0])
    # msg: tuple[str, int] | tuple [str, int, Callable] = color_message(
    #     r, g, b, 0 if args.brightness is not None else tt)
    msg: ColorCommand = ColorCommand(
        transition_time=tt,
        _force=args.force,
        color=RgbColor(int(r), int(g), int(b)),
    )

    # check_color = functools.partial(
    #     check_device_parameter, args, CheckDeviceParameter.COLOR, [int(r),
    # int(g), int(b)]
    # )
    # msg = msg + (check_color,)

    message_queue_tx_local.append(msg.msg_str())
    # col: Any = json.loads(msg[0])["color"]
    message_queue_tx_state_cloud.append(msg.color_json())


def command_color_percent(
    args: argparse.Namespace,
    message_queue_tx_local: list,
    message_queue_tx_state_cloud: list,
) -> None:
    """Command for color in percentage numbers."""
    r: Any
    g: Any
    b: Any
    w: Any
    c: Any
    r, g, b, w, c = args.percent_color
    tt: Any = args.transitionTime[0]
    msg: tuple[str, int] = percent_color_message(
        r, g, b, w, c, 0 if args.brightness is not None else tt
    )
    message_queue_tx_local.append(msg)
    p_color: Any = json.loads(msg[0])["p_color"]
    message_queue_tx_state_cloud.append({"p_color": p_color})


def command_brightness(
    args: argparse.Namespace,
    message_queue_tx_local: list,
    message_queue_tx_state_cloud: list,
) -> None:
    """Command for brightness."""
    brightness_str: str = args.brightness[0]

    tt: int = int(args.transitionTime[0])
    # msg: tuple[str, int] | tuple [str, int, Callable] = brightness_message(
    # brightness_str, tt)#
    msg: BrightnessCommand = BrightnessCommand(
        transition_time=tt, _force=args.force, brightness=int(brightness_str)
    )

    # check_brightness: functools.partial[bool] = functools.partial(
    #     check_device_parameter, args, CheckDeviceParameter.BRIGHTNESS,
    # int(brightness_str)
    # )
    # msg = msg + (check_brightness,)

    message_queue_tx_local.append(msg)
    # brightness: Any = json.loads(msg[0])["brightness"]
    # message_queue_tx_state_cloud.append({"brightness": brightness})
    message_queue_tx_state_cloud.append(msg.brightness_json())


def command_temperature(
    args: argparse.Namespace,
    message_queue_tx_local: list,
    message_queue_tx_state_cloud: list,
) -> None:
    """Command for temperature."""
    temperature: str = args.temperature[0]

    tt: Any = args.transitionTime[0]
    # msg: tuple[str, int] | tuple[str, int, Callable] = temperature_message(
    #     temperature, 0 if args.brightness is not None else tt)

    # check_temperature: functools.partial[bool] = functools.partial(
    #     check_device_parameter, args, CheckDeviceParameter.TEMPERATURE,
    # int(temperature)
    # )
    # msg = msg + (check_temperature,)

    # temperature = json.loads(msg[0])["temperature"]
    msg: TemperatureCommand = TemperatureCommand(
        transition_time=tt, _force=args.force, temperature=int(temperature)
    )

    message_queue_tx_local.append(msg)
    message_queue_tx_state_cloud.append(msg.temperature_json())


def routine_scene(args: argparse.Namespace, scene_list: list[str]) -> bool:
    """Command for select scene."""

    scene: str = ""
    if args.WW:
        scene = "Warm White"
    if args.daylight:
        scene = "Daylight"
    if args.CW:
        scene = "Cold White"
    if args.nightlight:
        scene = "Night Light"
    if args.relax:
        scene = "Relax"
    if args.TVtime:
        scene = "TV time"
    if args.comfort:
        scene = "Comfort"
    if args.focused:
        scene = "Focused"
    if args.fireplace:
        scene = "Fireplace"
    if args.club:
        scene = "Jazz Club"
    if args.romantic:
        scene = "Romantic"
    if args.gentle:
        scene = "Gentle"
    if args.summer:
        scene = "Summer"
    if args.jungle:
        scene = "Jungle"
    if args.ocean:
        scene = "Ocean"
    if args.fall:  # Autumn
        scene = "Fall"
    if args.sunset:
        scene = "Sunset"
    if args.party:
        scene = "Party"
    if args.spring:
        scene = "Spring"
    if args.forest:
        scene = "Forest"
    if args.deep_sea:
        scene = "Deep Sea"
    if args.tropical:
        scene = "Tropical"
    if args.magic:
        scene = "Magic Mood"
    if args.mystic:
        scene = "Mystic Mountain"
    if args.cotton:
        scene = "Cotton Candy"
    if args.ice:
        scene = "Ice Cream"

    if scene:
        scene_result: list[dict[str, Any]] = [
            x for x in SCENES if x["label"] == scene
        ]
        if not len(scene_result) or len(scene_result) > 1:
            LOGGER.error(
                f"Scene {scene} not found or more than one scene with the name"
                " found."
            )
            return False
        scene_obj: dict[str, Any] = scene_result[0]

        # check_brightness = functools.partial(check_device_parameter,
        # Check_device_parameter.scene, scene_obj)
        # msg = msg + (check_brightness,)
        # if not check_device_parameter(Check_device_parameter.scene,
        # scene_obj):
        #     return False

        commands: str = scene_obj["commands"]
        if len(commands.split(";")) > 2:
            commands += "l 0;"
        args.routine_id = 0
        args.routine_put = True
        args.routine_commands = commands
        args.routine_scene = str(scene_obj["id"])

        scene_list.append(scene)

    return True


def enable_tb(args: argparse.Namespace, message_queue_tx_local: list) -> None:
    """Enable thingsboard to device."""
    a: str = args.enable_tb[0]
    if a != "yes" and a != "no":
        print("ERROR --enable_tb needs to be yes or no")
        sys.exit(1)

    message_queue_tx_local.append(
        (json.dumps({"type": "backend", "link_enabled": a}), 1000)
    )


@dataclass
class PowerCommand(RequestCommand, CloudStateCommand):
    status: str = "on"


@dataclass
class RebootCommand(CommandTyped):
    def __post_init__(self) -> None:
        self.type = CommandType.REBOOT.value


@dataclass
class FactoryResetCommand(CommandTyped):
    def __post_init__(self) -> None:
        self.type = CommandType.FACTORY_RESET.value


@dataclass
class FadeCommand(RequestCommand):
    fade_in: int = 0
    fade_out: int = 0


@dataclass
class RoutineCommand(CommandTyped):
    action: str = "list"

    def __post_init__(self) -> None:
        self.type = CommandType.ROUTINE.value

    def json(self) -> TypeJson:
        return TypeJson(
            {
                k: v
                for k, v in self.__dict__.items()
                if not k.startswith("_") and v != "" and v is not None
            }
        )


@dataclass
class RoutineListCommand(RoutineCommand):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.action = "list"


@dataclass
class RoutineStartCommand(RoutineCommand, TransitionCommand):
    id: str = ""  # routine_id

    def __post_init__(self) -> None:
        super().__post_init__()
        self.action = "start"


@dataclass
class RoutineDeleteCommand(RoutineCommand, TransitionCommand):
    id: str = ""  # routine_id

    def __post_init__(self) -> None:
        super().__post_init__()
        self.action = "delete"


@dataclass
class RoutinePutCommand(
    RoutineCommand, CommandWithCheckValuesLight, TransitionCommand
):
    id: str = ""  # routine_id
    scene: str = ""  # scene_id
    commands: str = ""  # routine_commands

    def __post_init__(self) -> None:
        super().__post_init__()
        self.action = "put"

    def check_values(self, device: Device) -> bool:
        # check_scene: functools.partial[Any] = functools.partial(
        #     check_device_parameter,
        #     args.force,
        #     CheckDeviceParameter.SCENE,
        #     args.routine_scene,
        # )
        """Check device scene support."""
        # if force:
        #     return True
        if not device.ident:
            return False
        try:
            scene_result: list[dict[str, Any]] = [
                x for x in SCENES if x["id"] == int(self.scene)
            ]
            scene: dict[str, Any] = scene_result[0]

            # bulb has no colors, therefore only cwww scenes are allowed
            if ".rgb" not in device.ident.product_id and "cwww" not in scene:
                return forced_continue(
                    self._force,
                    f"Scene {scene['label']} not supported by device product"
                    + f"{device.acc_sets['productId']}. Coldwhite/Warmwhite"
                    " Scenes only.",
                )

        except Exception:
            return not missing_config(self._force, device.ident.product_id)
        return True


def routine_put(
    args: argparse.Namespace, local_and_cloud_command_msg: Callable
) -> None:
    """Put routine to device."""

    # msg = msg + (check_scene,) # fix check routine before putting
    local_and_cloud_command_msg(
        # RoutinePutCommand(
        #     _json={
        #         "type": "routine",
        #         "action": "put",
        #         "id": args.routine_id,
        #         "scene": args.routine_scene,
        #         "commands": args.routine_commands,
        #     }
        # ),
        RoutinePutCommand(
            id=args.routine_id,
            scene=args.routine_scene,
            commands=args.routine_commands,
        ),
        # 500,
        # check_scene,
    )


def forced_continue(force: bool, reason: str) -> bool:
    """Force argument."""
    if not force:
        LOGGER.error(reason)
        return False
    else:
        LOGGER.info(reason)
        LOGGER.info("Enforced send")
        return True


def missing_config(force: bool, product_id: str) -> bool:
    """Missing device config."""
    if not forced_continue(
        force,
        "Missing or faulty config values for device "
        + " product_id: "
        + product_id,
    ):
        return True
    return False


# Needing config profile versions implementation for checking trait ranges ###

# def check_color_range(force: bool, device: Light, values: list[int]) -> bool:
#     """Check device color range."""
#     if not device.color_range:
#         missing_config(force, device.device.ident.product_id)
#     else:
#         for value in values:
#             if int(value) < device.color_range.min or int(value) >
# device.color_range.max:
#                 return forced_continue(force,
#                     f"Color {value} out of range [{device.color_range.min}.."
#                     f"{device.color_range.max}]."
#                 )
#     return True

# def check_brightness_range(force: bool, device: Light, value: int) -> bool:
#     """Check device brightness range."""
#     if not device.brightness_range:
#         missing_config(force, device.device.ident.product_id)
#     else:
#         if int(value) < device.brightness_range.min or int(value) >
#         device.brightness_range.max:
#             return forced_continue(force,
#                 f"Brightness {value} out of range
# [{device.brightness_range.min}"
#                 f"..{device.brightness_range.max}]."
#             )
#     return True

# def check_temp_range(force: bool, device: Light, value: int) -> bool:
#     """Check device temperature range."""
#     if not device.temperature_range:
#         missing_config(force, device.device.ident.product_id)
#     else:
#         if int(value) < device.temperature_range.min or int(value) >
# device.temperature_range.max:
#             return forced_continue(force,
#                 f"Temperature {value} out of range
# [{device.temperature_range.min}.."
#                 f"{device.temperature_range.max}]."
#             )
#     return True


def check_scene_support(force: bool, device: Device, scene_id: str) -> bool:
    """Check device scene support."""
    if force:
        return True
    if not device.ident:
        return False
    try:
        scene_result: list[dict[str, Any]] = [
            x for x in SCENES if x["id"] == int(scene_id)
        ]
        scene: dict[str, Any] = scene_result[0]

        # bulb has no colors, therefore only cwww scenes are allowed
        if ".rgb" not in device.ident.product_id and "cwww" not in scene:
            return forced_continue(
                force,
                f"Scene {scene['label']} not supported by device product"
                + f"{device.acc_sets['productId']}. Coldwhite/Warmwhite Scenes"
                " only.",
            )

    except Exception:
        return not missing_config(force, device.ident.product_id)
    return True


CHECK_RANGE: dict[Any, Any] = {
    # CheckDeviceParameter.COLOR: check_color_range,
    # CheckDeviceParameter.BRIGHTNESS: check_brightness_range,
    # CheckDeviceParameter.TEMPERATURE: check_temp_range,
    CheckDeviceParameter.SCENE: check_scene_support,
}


def check_device_parameter(
    force: bool, parameter: CheckDeviceParameter, values: Any, device: Device
) -> bool:
    """Check device configs."""
    if not device.device_config and not forced_continue(
        force, "Missing configs for devices."
    ):
        return False

    if not CHECK_RANGE[parameter](force, device, values):
        return False
    return True
