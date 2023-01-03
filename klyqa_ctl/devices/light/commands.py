"""Light commands"""
from __future__ import annotations
"""! @brief Contains all functions for light commands."""
import sys

import argparse
from enum import Enum
import functools
import json
from typing import Any, Callable

from klyqa_ctl.devices.device import format_uid
from klyqa_ctl.devices.light import BULB_SCENES, KlyqaBulb
from klyqa_ctl.general.general import LOGGER, DeviceType, sep_width
from klyqa_ctl.general.parameters import add_config_args, get_description_parser
from klyqa_ctl.klyqa_ctl import TypeJSON

# Global Constants
commands_send_to_bulb: list[str] = [
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


# Functions
def color_message(red: str, green: str, blue: str, transition: int, skipWait=False) -> tuple[str, str]:
    """Create message for color change."""
    waitTime: str = str(transition) if not skipWait else "0"
    return (
        json.dumps(
            {
                "type": "request",
                "color": {
                    "red": red,
                    "green": green,
                    "blue": blue,
                },
                "transitionTime": transition,
            }
        ),
        waitTime,
    )


def temperature_message(temperature: str, transition: str, skipWait: bool = False) -> tuple[str, str]:
    """Create message for temperature change in kelvin."""
    waitTime: str = transition if not skipWait else "0"
    return (
        json.dumps(
            {
                "type": "request",
                "temperature": temperature,
                "transitionTime": transition,
            }
        ),
        waitTime,
    )


def percent_color_message(
    red: str, green: str, blue: str, warm: str, cold: str, transition: str, skipWait: bool = False
) -> tuple[str, str]:
    """Create message for color change in percent."""
    waitTime: str = transition if not skipWait else "0"
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
                "transitionTime": transition,
            }
        ),
        waitTime,
    )


def brightness_message(brightness: str, transition: int) -> tuple[str, str]:
    """Create message for brightness set."""
    return (
        json.dumps(
            {
                "type": "request",
                "brightness": {
                    "percentage": brightness,
                },
                "transitionTime": transition,
            }
        ),
        str(transition),
    )


def external_source_message(protocol, port, channel) -> TypeJSON:
    """Create external source protocol message."""
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
        "--transitionTime", nargs=1, help="transition time in milliseconds", default=[0]
    )

    parser.add_argument("--color", nargs=3, help="set color command (r,g,b) 0-255")
    parser.add_argument(
        "--temperature",
        nargs=1,
        help="set temperature command (in kelvin, range depends on lamp profile) (lower: warm, higher: cold)",
    )
    parser.add_argument("--brightness", nargs=1, help="set brightness in percent 0-100")
    parser.add_argument(
        "--percent_color",
        nargs=5,
        metavar=("RED", "GREEN", "BLUE", "WARM", "COLD"),
        help="set colors and white tones in percent 0 - 100",
    )
    parser.add_argument("--ota", nargs=1, help="specify http URL for ota")
    parser.add_argument(
        "--ping", help="send ping", action="store_const", const=True, default=False
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
        help="trigger a factory reset on the device (Warning: device has to be onboarded again afterwards)",
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
        "--routine_id", help="specify routine id to act on (for put, start, delete)"
    )
    parser.add_argument("--routine_scene", help="specify routine scene label (for put)")
    parser.add_argument("--routine_commands", help="specify routine program (for put)")
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
    parser.add_argument("--mystic", help="Mystic Mountain", action="store_true")
    parser.add_argument("--cotton", help="Cotton Candy", action="store_true")
    parser.add_argument("--ice", help="Ice Cream", action="store_true")


async def discover_devices(
    args: argparse.Namespace,
    args_in: list[Any],
    send_to_devices_cb: Callable[[argparse.Namespace], Any]) -> argparse.Namespace | None:
        
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
        DeviceType.lighting.name,
        "--request",
        "--allDevices",
        "--selectDevice",
        "--discover",
    ]

    orginal_args_parser: argparse.ArgumentParser = get_description_parser()
    discover_local_args_parser: argparse.ArgumentParser = get_description_parser()

    add_config_args(parser=orginal_args_parser)
    add_config_args(parser=discover_local_args_parser)
    add_command_args_bulb(parser=discover_local_args_parser)

    original_config_args_parsed, _ = orginal_args_parser.parse_known_args(
        args=args_in
    )

    discover_local_args_parsed = discover_local_args_parser.parse_args(
        discover_local_args, namespace=original_config_args_parsed
    )

    uids: set | list | str = await send_to_devices_cb(discover_local_args_parsed)
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


async def process_args_to_msg_lighting(
    args: argparse.Namespace,
    args_in: list[Any],
    send_to_devices_callable: Callable[[argparse.Namespace], Any],
    message_queue_tx_local: list[Any],
    message_queue_tx_command_cloud: list[Any],
    message_queue_tx_state_cloud: list[Any],
    scene_list: list[str],
) -> bool:
    """
    
    Process arguments for communicating with lights. Fill message queues for local
    and cloud communication. Discover devices to communicate with.
    
    Params:
        args: Parsed arguments to be processed.
        args_in: Original arguments as a list, if we want to reparse and add arguments.
        send_to_devices_callable: If we need to send something to the lamps,
            use this callable.
        message_queue_tx_local: Queue to be filled with messages for local
            communication.
        message_queue_tx_command_cloud: Queue for cloud command messages.
        message_queue_tx_state_cloud: Queue for cloud state messages.
        scene_list: If a scene is applied, add it to the scene list, so the
            klyqa-ctl send function can process it.

    """

    def local_and_cloud_command_msg(json_msg: TypeJSON, timeout: int, check_func: Callable | None = None) -> None:
        """ Add message to local and cloud queue. Give a timeout after the message
        was sent. Give also a check function for the values that are send to be in
        limits (device config).
        """
        msg: tuple[str, int] | tuple[str, int, Callable] = (json.dumps(json_msg), timeout)
        if check_func:
            msg = msg + (check_func,)
        message_queue_tx_local.append(msg)
        message_queue_tx_command_cloud.append(json_msg)

    # TODO: Missing cloud discovery and interactive device selection. Send to devices if given as argument working.
    if (args.local or args.tryLocalThanCloud) and (
        not args.device_name
        and not args.device_unitids
        and not args.allDevices
        and not args.discover
    ):
        args_ret: argparse.Namespace | None = await discover_devices(args, args_in, send_to_devices_callable)
        
        if isinstance(args_ret, argparse.Namespace):
            args = args_ret

    commands_to_send: list[str] = [
        i for i in commands_send_to_bulb if hasattr(args, i) and getattr(args, i)
    ]

    if commands_to_send:
        print("Commands to send to devices: " + ", ".join(commands_to_send))
    else:
        if not await commands_select(args, args_in, send_to_devices_callable):
            return False

    if args.ota is not None:
        local_and_cloud_command_msg({"type": "fw_update", "url": args.ota}, 10000)

    if args.ping:
        local_and_cloud_command_msg({"type": "ping"}, 10000)

    if args.request:
        local_and_cloud_command_msg({"type": "request"}, 10000)

    if args.external_source:
        mode, port, channel = args.external_source
        local_and_cloud_command_msg(
            external_source_message(int(mode), port, channel), 0
        )

    if args.enable_tb is not None:
        enable_tb(args, message_queue_tx_local)

    if args.passive:
        pass

    if args.power:
        message_queue_tx_local.append(
            (json.dumps({"type": "request", "status": args.power[0]}), 500)
        )
        message_queue_tx_state_cloud.append({"status": args.power[0]})

    if args.color is not None:
        command_color(args, message_queue_tx_local, message_queue_tx_state_cloud)
    
    if args.percent_color is not None:
        command_color_percent(args, message_queue_tx_local, message_queue_tx_state_cloud)

    if args.temperature is not None:
        command_temperature(args, message_queue_tx_local, message_queue_tx_state_cloud)

    if args.brightness is not None:
        command_brightness(args, message_queue_tx_local, message_queue_tx_state_cloud)

    if args.factory_reset:
        local_and_cloud_command_msg({"type": "factory_reset"}, 500)

    if args.fade is not None and len(args.fade) == 2:
        local_and_cloud_command_msg(
            {"type": "request", "fade_out": args.fade[1], "fade_in": args.fade[0]}, 500
        )

    if not routine_scene(args, scene_list):
        return False

    if args.routine_list:
        local_and_cloud_command_msg({"type": "routine", "action": "list"}, 500)

    if args.routine_put and args.routine_id is not None:
        routine_put(args, local_and_cloud_command_msg, Check_device_parameter)

    if args.routine_delete and args.routine_id is not None:
        local_and_cloud_command_msg(
            {"type": "routine", "action": "delete", "id": args.routine_id}, 500
        )
    if args.routine_start and args.routine_id is not None:
        local_and_cloud_command_msg(
            {"type": "routine", "action": "start", "id": args.routine_id}, 500
        )

    if args.reboot:
        local_and_cloud_command_msg({"type": "reboot"}, 500)
    
    return True


async def commands_select(args: argparse.Namespace, args_in: list[str], send_to_devices_callable: Callable) -> bool:
    """Interactive command select."""
    print("Commands (arguments):")
    print(sep_width * "-")

    def get_temp_range(product_id) -> bool | tuple[int,int]:
        temperature_enum = []
        if not self.device_config:
            return False
        try:
            temperature_enum = [
                trait["value_schema"]["properties"]["colorTemperature"]["enum"]
                if "properties" in trait["value_schema"]
                else trait["value_schema"]["enum"]
                for trait in self.device_config["deviceTraits"]
                if trait["trait"] == "@core/traits/color-temperature"
            ]
            if len(temperature_enum[0]) < 2:
                raise Exception()
        except:
            return False
        return temperature_enum[0]

    def get_inner_range(tup1, tup2) -> tuple[int, int]:
        return (
            tup1[0] if tup1[0] > tup2[0] else tup2[0],
            tup1[1] if tup1[1] < tup2[1] else tup2[1],
        )

    temperature_enum: tuple[int, int] = tuple()
    color: list[int] = [0, 255]
    brightness: tuple[int, int] = (0,100)
    for u_id in args.device_unitids[0].split(","):
        u_id: str = format_uid(u_id)
        if u_id not in self.devices or not self.devices[u_id].ident: # fix self devices

            async def send_ping() -> bool:
                discover_local_args2: list[str] = [
                    "--ping",
                    "--device_unitids",
                    u_id,
                ]

                orginal_args_parser: argparse.ArgumentParser = (
                    get_description_parser()
                )
                discover_local_args_parser2: argparse.ArgumentParser = (
                    get_description_parser()
                )

                add_config_args(parser=orginal_args_parser)
                add_config_args(parser=discover_local_args_parser2)
                add_command_args_bulb(parser=discover_local_args_parser2)

                (
                    original_config_args_parsed,
                    _,
                ) = orginal_args_parser.parse_known_args(args=args_in)

                discover_local_args_parsed2 = (
                    discover_local_args_parser2.parse_args(
                        discover_local_args2,
                        namespace=original_config_args_parsed,
                    )
                )

                ret = send_to_devices_callable(discover_local_args_parsed2)
                if isinstance(ret, bool) and ret:
                    return True
                else:
                    return False

            ret: bool = await send_ping()
            if isinstance(ret, bool) and ret:
                product_id: str = self.devices[u_id].ident.product_id
            else:
                LOGGER.error(f"Device {u_id} not found.")
                return False
        product_id = self.devices[u_id].ident.product_id
        if not temperature_enum:
            temperature_enum = get_temp_range(product_id)
        else:
            temperature_enum = get_inner_range(
                temperature_enum, get_temp_range(product_id)
            )
    arguments_send_to_device = {}
    if temperature_enum:
        arguments_send_to_device = {
            "temperature": " ["
            + str(temperature_enum[0])
            + "-"
            + str(temperature_enum[1])
            + "] (Kelvin, low: warm, high: cold)"
        }

    arguments_send_to_device: dict[str, str] = {
        **arguments_send_to_device,
        **{
            "color": f" rgb [{color[0]}..{color[1]}] [{color[0]}..{color[1]}] [{color[0]}..{color[1]}]",
            "brightness": " ["
            + str(brightness[0])
            + ".."
            + str(brightness[1])
            + "]",
            "routine_commands": " [cmd]",
            "routine_id": " [int]",
            "power": " [on/off]",
        },
    }

    count = 1
    for c in commands_send_to_bulb:
        args_to_b: str = (
            arguments_send_to_device[c] if c in arguments_send_to_device else ""
        )
        print(str(count) + ") " + c + args_to_b)
        count: int = count + 1

    cmd_c_id: int = int(input("Choose command number [1-9]*: "))
    if cmd_c_id > 0 and cmd_c_id < count:
        args_in.append("--" + commands_send_to_bulb[cmd_c_id - 1])
    else:
        LOGGER.error("No such command id " + str(cmd_c_id) + " available.")
        sys.exit(1)

    if commands_send_to_bulb[cmd_c_id - 1] in arguments_send_to_device:
        args_app: str = input(
            "Set arguments (multiple arguments space separated) for command [Enter]: "
        )
        if args_app:
            args_in.extend(args_app.split(" "))

    parser: argparse.ArgumentParser = get_description_parser()

    add_config_args(parser=parser)
    add_command_args_bulb(parser=parser)

    args = parser.parse_args(args_in, namespace=args)
    # args.func(args)
    return True

def command_color(args: argparse.Namespace, message_queue_tx_local, message_queue_tx_state_cloud) -> None:
    """Command for setting the color."""
    r: str; g: str; b: str;
    r, g, b = args.color

    tt: int = int(args.transitionTime[0])
    msg: tuple[str, str] | tuple [str, str, Callable] = color_message(r, g, b, tt, skipWait=args.brightness is not None)

    check_color = functools.partial(
        check_device_parameter, args, Check_device_parameter.color, [int(r), int(g), int(b)]
    )
    msg = msg + (check_color,)

    message_queue_tx_local.append(msg)
    col = json.loads(msg[0])["color"]
    message_queue_tx_state_cloud.append({"color": col})

def command_color_percent(args, message_queue_tx_local, message_queue_tx_state_cloud) -> None:
    """Command for color in percentage numbers."""
    r, g, b, w, c = args.percent_color
    tt = args.transitionTime[0]
    msg: tuple[str, str] = percent_color_message(
        r, g, b, w, c, tt, skipWait=args.brightness is not None
    )
    message_queue_tx_local.append(msg)
    p_color = json.loads(msg[0])["p_color"]
    message_queue_tx_state_cloud.append({"p_color": p_color})
        
def command_brightness(args, message_queue_tx_local, message_queue_tx_state_cloud) -> None:
    """Command for brightness."""
    brightness_str: str = args.brightness[0]

    tt: int = int(args.transitionTime[0])
    msg: tuple[str, str] | tuple [str, str, Callable] = brightness_message(brightness_str, tt)

    check_brightness: functools.partial[bool] = functools.partial(
        check_device_parameter, args, Check_device_parameter.brightness, int(brightness_str)
    )
    msg = msg + (check_brightness,)

    message_queue_tx_local.append(msg)
    brightness = json.loads(msg[0])["brightness"]
    message_queue_tx_state_cloud.append({"brightness": brightness})

def command_temperature(args, message_queue_tx_local, message_queue_tx_state_cloud) -> None:
    """Command for temperature."""
    temperature = args.temperature[0]

    tt = args.transitionTime[0]
    msg: tuple[str, str] | tuple[str, str, Callable] = temperature_message(
        temperature, tt, skipWait=args.brightness is not None
    )

    check_temperature = functools.partial(
        check_device_parameter, args, Check_device_parameter.temperature, int(temperature)
    )
    msg = msg + (check_temperature,)

    temperature: str = json.loads(msg[0])["temperature"]
    message_queue_tx_local.append(msg)
    message_queue_tx_state_cloud.append({"temperature": temperature})

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
        scene_result: list[dict[str, Any]] = [x for x in BULB_SCENES if x["label"] == scene]
        if not len(scene_result) or len(scene_result) > 1:
            LOGGER.error(
                f"Scene {scene} not found or more than one scene with the name found."
            )
            return False
        scene_obj: dict[str, Any] = scene_result[0]

        # check_brightness = functools.partial(check_device_parameter, Check_device_parameter.scene, scene_obj)
        # msg = msg + (check_brightness,)
        # if not check_device_parameter(Check_device_parameter.scene, scene_obj):
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

def routine_put(args: argparse.Namespace, local_and_cloud_command_msg: Callable, check_device_parameter) -> None:
    """Put routine to device."""
    check_scene: functools.partial[Any] = functools.partial(
        check_device_parameter, Check_device_parameter.scene, args.routine_scene
    )
    # msg = msg + (check_scene,) # fix check routine before putting
    local_and_cloud_command_msg(
        {
            "type": "routine",
            "action": "put",
            "id": args.routine_id,
            "scene": args.routine_scene,
            "commands": args.routine_commands,
        },
        500,
        check_scene
    )

def forced_continue(args: argparse.Namespace, reason: str) -> bool:
    """Force argument."""
    if not args.force:
        LOGGER.error(reason)
        return False
    else:
        LOGGER.info(reason)
        LOGGER.info("Enforced send")
        return True

Check_device_parameter = Enum(
    "Check_device_parameter", "color brightness temperature scene"
)

def missing_config(args: argparse.Namespace, product_id) -> bool:
    """Missing device config."""
    if not forced_continue(args, 
        "Missing or faulty config values for device " + " product_id: " + product_id
    ):
        return True
    return False

#### Needing config profile versions implementation for checking trait ranges ###

def check_color_range(args: argparse.Namespace, device: KlyqaBulb, values: list[int]) -> bool:
    """Check device color range."""
    if not device.color_range:
        missing_config(args, device.acc_sets["productId"])
    else:
        for value in values:
            if int(value) < device.color_range.min or int(value) > device.color_range.max:
                return forced_continue(args,
                    f"Color {value} out of range [{device.color_range.min}..{device.color_range.max}]."
                )
    return True

def check_brightness_range(args: argparse.Namespace, device: KlyqaBulb, value: int) -> bool:
    """Check device brightness range."""
    if not device.brightness_range:
        missing_config(args, device.acc_sets["productId"])
    else:
        if int(value) < device.brightness_range.min or int(value) > device.brightness_range.max:
            return forced_continue(args,
                f"Brightness {value} out of range [{device.brightness_range.min}..{device.brightness_range.max}]."
            )
    return True

def check_temp_range(args: argparse.Namespace, device: KlyqaBulb, value: int) -> bool:
    """Check device temperature range."""
    if not device.temperature_range:
        missing_config(args, device.acc_sets["productId"])
    else:
        if int(value) < device.temperature_range.min or int(value) > device.temperature_range.max:
            return forced_continue(args,
                f"Temperature {value} out of range [{device.temperature_range.min}..{device.temperature_range.max}]."
            )
    return True

def check_scene_support(args: argparse.Namespace, device, scene_id) -> bool:
    """Check device scene support."""
    try:
        scene_result: list[dict[str, Any]] = [x for x in BULB_SCENES if x["id"] == int(scene_id)]
        scene: dict[str, Any] = scene_result[0]

        # bulb has no colors, therefore only cwww scenes are allowed
        if not ".rgb" in device.acc_sets["productId"] and not "cwww" in scene:
            return forced_continue(args,
                f"Scene {scene['label']} not supported by device product" +
                f"{device.acc_sets['productId']}. Coldwhite/Warmwhite Scenes only."
            )

    except Exception as excp:
        return not missing_config(args, device.acc_sets["productId"])
    return True

check_range: dict[Any, Any] = {
    Check_device_parameter.color: check_color_range,
    Check_device_parameter.brightness: check_brightness_range,
    Check_device_parameter.temperature: check_temp_range,
    Check_device_parameter.scene: check_scene_support,
}

def check_device_parameter(args: argparse.Namespace, 
    parameter: Check_device_parameter, values, device
) -> bool:
    """Check device configs."""
    if not device.device_config and not forced_continue(args, "Missing configs for devices."):
        return False

    if not check_range[parameter](device, values):
        return False
    return True
