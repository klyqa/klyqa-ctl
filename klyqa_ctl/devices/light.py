"""Lighting"""

from __future__ import annotations
import argparse
import functools
import json
import sys

from ..general.parameters import add_config_args, get_description_parser
from .device import *

from ..general.general import *

## Bulbs ##

BULB_SCENES: list[dict[str, Any]] = [
    {
        "id": 100,
        "colors": ["#FFECD8", "#FFAA5B"],
        "label": "Warm White",
        "commands": "5ch 0 0 0 0 65535 65535 500;p 1000;",
        "cwww": True,
    },
    {
        "id": 101,
        "colors": ["#FCF4DD", "#FED07A"],
        "label": "Daylight",
        "commands": "5ch 0 0 0 24903 40631 65535 500;p 1000;",
    },
    {
        "id": 102,
        "colors": ["#FFFFFF", "#B6DAFF"],
        "label": "Cold White",
        "commands": "5ch 0 0 0 65535 0 65535 500;p 1000;",
        "cwww": True,
    },
    {
        "id": 103,
        "colors": ["#E06004", "#55230D"],
        "label": "Night Light",
        "commands": "5ch 9830 3276 0 1310 0 65535 500;p 1000;",
        "cwww": True,
    },
    {
        "id": 106,
        "colors": ["#FDCB78", "#FCDA60"],
        "label": "Relax",
        "commands": "5ch 26214 26214 0 0 13107 65535 500;p 1000;",
    },
    {
        "id": 109,
        "colors": ["#090064", "#2E2A5A"],
        "label": "TV Time",
        "commands": "5ch 655 0 6553 1310 0 65535 500;p 1000;",
    },
    {
        "id": 107,
        "colors": ["#FFD1A2", "#FFEDDA"],
        "label": "Comfort",
        "commands": "5ch 47185 0 0 18349 0 65535 500;p 1000;",
    },
    {
        "id": 108,
        "colors": ["#EAFCFF", "#81DFF0"],
        "label": "Focused",
        "commands": "5ch 0 0 26214 5000 0 65535 500;p 1000;",
        "cwww": True,
    },
    {
        "id": 110,
        "colors": ["#CD3700", "#CD0000", "#CD6600"],
        "label": "Fireplace",
        "commands": "5ch 32767 0 0 0 1500 65535 500;p 500;5ch 55535 200 0 0 2000 65535 500;p 500;",
        # '5ch 32767 0 0 0 1500 65535 500;p 500;5ch 55535 200 0 0 2000 65535 500;p 500;5ch 32767 30000 0 0 1500 65535 500;p 500;5ch 25535 20000 0 0 2000 65535 500;p 500;5ch 62767 0 0 0 1500 65535 500;p 500;5ch 65535 200 0 0 2000 65535 500;p 500;5ch 32767 30000 0 0 1500 65535 500;p 500;5ch 25535 30000 0 0 2000 65535 500;p 500;',
    },
    {
        "id": 122,
        "colors": ["#12126C", "#B22222", "#D02090"],
        "label": "Jazz Club",
        "commands": "5ch 45746 8738 8738 0 0 65535 6100;p 5100;5ch 45232 12336 24672 0 0 65535 6100;p 5000;5ch 53436 8224 37008 0 0 65535 6100;p 5000;5ch 0 0 33896 0 0 65535 6000;p 5000;5ch 18504 15677 35728 0 0 65535 6100;p 5000;5ch 38036 0 52428 0 0 65535 6600;p 5000;5ch 45232 12336 24672 0 0 65535 6100;p 5000;",
    },
    {
        "id": 104,
        "colors": ["#B20C26", "#CC1933", "#EE6AA7"],
        "label": "Romantic",
        "commands": "5ch 58981 6553 16383 0 0 65535 1000;p 7400;5ch 45874 3276 9830 0 0 65535 4400;p 6600;5ch 52428 6553 13107 0 0 65535 8800;p 15200;5ch 41287 0 0 0 0 65535 4400;p 13200;",
    },
    {
        "id": 112,
        "colors": ["#FFDCE8", "#D2FFD2", "#CCFFFF"],
        "label": "Gentle",
        "commands": "5ch 51117 0 0 13107 0 65535 26000;p 56000;5ch 26214 26214 0 8519 0 65535 26000;p 56000;5ch 0 51117 0 13107 0 65535 26000;p 56000;5ch 0 26214 26214 8519 0 65535 26000;p 56000;5ch 0 0 51117 13107 0 65535 26000;p 56000;5ch 26214 0 26214 8519 0 65535 26000;p 56000;",
    },
    {
        "id": 113,
        "colors": ["#EEAD0E", "#FF7F24", "#CD0000"],
        "label": "Summer",
        "commands": "5ch 17039 25558 0 13762 0 65535 8000;p 14000;5ch 39321 7864 0 15728 0 65535 8000;p 14000;5ch 28180 17694 0 11140 0 65535 8000;p 14000;",
    },
    {
        "id": 114,
        "colors": ["#00BA0C", "#008400", "#0C4400"],
        "label": "Jungle",
        "commands": "5ch 0 47840 3276 0 0 65535 2600;p 2100;5ch 5898 10485 1310 0 0 65535 2300;p 4200;5ch 0 34078 0 0 0 65535 2100;p 2500;5ch 3276 17694 0 0 0 65535 4600;p 4000;5ch 9174 46529 0 0 0 65535 5500;p 6900;5ch 9830 43908 1966 0 0 65535 2700;p 4700;5ch 0 55704 0 0 0 65535 2000;p 3800;",
    },
    {
        "id": 105,
        "colors": ["#00008B", "#0000FF", "#1874ED"],
        "label": "Ocean",
        "commands": "5ch 1310 17694 36044 0 0 65535 2400;p 5400;5ch 655 15073 39321 0 0 65535 2100;p 5100;5ch 1310 36044 17039 0 0 65535 4200;p 5100;5ch 1966 22281 29490 0 0 65535 2800;p 5700;5ch 655 19005 34733 0 0 65535 2100;p 4900;5ch 655 26869 27524 0 0 65535 2600;p 3400;5ch 655 26869 27524 0 0 65535 2700;p 3600;5ch 1310 38010 15728 0 0 65535 4200;p 5000;",
    },
    # {
    #   "id": 111,
    #   "colors": ['#A31900', '#A52300', '#B71933', '#A5237F', '#B71900'],
    #   "label": 'Club',
    #   "commands":
    #     '5ch 41942 6553 0 1310 0 65535 600;p 800;5ch 42597 9174 0 1310 0 65535 8700;p 12000;5ch 47185 6553 13107 1310 0 65535 8700;p 12000;5ch 42597 9174 32767 1310 0 65535 300;p 400;5ch 47185 6553 0 1310 0 65535 300;p 1300;',
    # },
    {
        "id": 115,
        "colors": ["#EE4000", "#CD6600", "#FFA500"],
        "label": "Fall",
        "commands": "5ch 49151 1966 0 9830 0 65535 8400;p 8610;5ch 35388 13107 0 6553 0 65535 8400;p 8750;5ch 52428 0 0 10485 0 65535 8400;p 8740;5ch 39321 9174 0 12451 0 65535 500;p 840;",
    },
    {
        "id": 116,
        "colors": ["#FFF0F5", "#FF6EB4", "#FF4500"],
        "label": "Sunset",
        "commands": "5ch 39321 0 15073 2621 0 65535 5680;p 5880;5ch 51117 0 0 13107 0 65535 5680;p 5880;5ch 43253 11796 0 2621 0 65535 5680;p 5880;5ch 38010 0 15073 7208 0 65535 5680;p 5880;5ch 46529 0 0 3932 0 65535 5680;p 5880;5ch 41287 11140 0 7864 0 65535 5680;p 5880;",
    },
    {
        "id": 117,
        "colors": ["#FF0000", "#0000FF", "#00FF00"],
        "label": "Party",
        "commands": "5ch 55704 0 0 0 0 65535 132;p 272;5ch 55704 0 0 0 0 65535 132;p 272;5ch 0 55704 0 0 0 65535 132;p 272;5ch 0 55704 0 0 0 65535 132;p 272;5ch 0 0 55704 0 0 65535 132;p 272;5ch 0 0 55704 0 0 65535 132;p 272;5ch 28180 0 27524 0 0 65535 132;p 272;5ch 0 28180 27524 0 0 65535 132;p 272;",
    },
    {
        "id": 118,
        "colors": ["#F0FFF0", "#C1FFC1", "#FFE4E1"],
        "label": "Spring",
        "commands": "5ch 19660 15728 19660 0 0 65535 8000;p 11000;5ch 20315 26214 13107 0 0 65535 8000;p 11000;5ch 17039 19005 19005 0 0 65535 8000;p 11000;5ch 20315 14417 14417 0 0 65535 8000;p 11000;5ch 19005 18349 17694 0 0 65535 8000;p 11000;5ch 11796 30146 6553 0 0 65535 8000;p 11000;",
    },
    {
        "id": 119,
        "colors": ["#C1FFC1", "#C0FF3E", "#CAFF70"],
        "label": "Forest",
        "commands": "5ch 23592 22937 0 3932 0 65535 6000;p 8000;5ch 19005 23592 0 7864 0 65535 6200;p 10100;5ch 22281 21626 0 12451 0 65535 6000;p 10000;5ch 23592 22281 0 4587 0 65535 5800;p 10400;5ch 18349 27524 0 1966 0 65535 6200;p 7000;5ch 8519 25558 0 23592 0 65535 6200;p 9400;",
    },
    {
        "id": 120,
        "colors": ["#104E8B", "#00008B", "#4876FF"],
        "label": "Deep Sea",
        "commands": "5ch 3932 3276 59636 0 0 65535 4100;p 5100;5ch 3276 6553 53738 0 0 65535 4100;p 5000;5ch 0 0 43908 0 0 65535 4100;p 5000;5ch 655 1310 53083 0 0 65535 3600;p 5000;5ch 1310 0 53738 0 0 65535 4000;p 5000;",
    },
    {
        "id": 121,
        "colors": ["#90ee90", "#8DEEEE", "#008B45"],
        "label": "Tropical",
        "commands": "5ch 0 43253 0 0 36044 65535 3000;p 4000;5ch 0 0 0 0 65535 65535 2400;p 5400;5ch 0 38010 0 0 48495 65535 2600;p 3600;5ch 0 32767 0 0 0 65535 2000;p 3400;5ch 0 46529 0 0 26869 65535 3100;p 4100;5ch 0 43908 0 0 0 65535 4000;p 7000;5ch 0 49806 0 0 16383 65535 2000;p 5000;",
    },
    {
        "id": 123,
        "colors": ["#FF6AD0", "#8BFFC7", "#96A0FF"],
        "label": "Magic Mood",
        "commands": "5ch 65535 27242 53456 0 0 35535 2400;p 1180;5ch 30326 33924 65535 0 0 35535 2200;p 1110;5ch 65535 21331 21331 0 0 35535 2800;p 1200;5ch 35723 55535 31143 0 0 35535 2800;p 1200;5ch 38550 41120 65535 0 0 35535 2400;p 1040;5ch 65535 61423 29041 0 0 35535 2400;p 1000;",
    },
    {
        "id": 124,
        "colors": ["#FF0000", "#B953FF", "#DBFF96"],
        "label": "Mystic Mountain",
        "commands": "5ch 65535 0 0 0 0 35535 1400;p 980;5ch 65535 30326 52685 0 0 35535 1200;p 910;5ch 47543 21331 65535 0 0 35535 1800;p 1200;5ch 35723 65535 44461 0 0 35535 1800;p 1200;5ch 56283 65535 38550 0 0 35535 1400;p 1040;5ch 65535 29041 53456 0 0 35535 1400;p 1000;",
    },
    {
        "id": 125,
        "colors": ["#FB0000", "#FFF748", "#B97FFF"],
        "label": "Cotton Candy",
        "commands": "5ch 65535 0 52428 0 0 35535 1400;p 980;5ch 47545 32639 655350 0 0 35535 1200;p 910;5ch 65535 33410 33410 0 0 35535 1800;p 1200;5ch 65535 63479 18504 0 0 35535 1800;p 1200;5ch 65535 63222 16448 0 0 35535 1400;p 1040;5ch 64507 0 0 0 0 35535 1400;p 1000;",
    },
    {
        "id": 126,
        "colors": ["#8BFFE1", "#D8FA97", "#FF927F"],
        "label": "Ice Cream",
        "commands": "5ch 65535 0 0 0 0 35535 1400;p 980;5ch 65535 37522 32639 0 0 35535 1200;p 910;5ch 61166 54741 65535 0 0 35535 1800;p 1200;5ch 35723 65535 57825 0 0 35535 1800;p 1200;5ch 55512 64250 38807 0 0 35535 1400;p 1040;5ch 65535 56796 62709 0 0 35535 1400;p 1000;",
    },
]


class KlyqaBulbResponseStatus(KlyqaDeviceResponse):
    """Klyqa_Bulb_Response_Status"""

    active_command: int | None = None
    active_scene: str | None = None
    fwversion: str | None = None
    mode: str | None = None
    open_slots: int | None = None
    sdkversion: str | None = None
    status: str | None = None
    temperature: int | None = None
    _brightness: int | None
    _color: RGBColor | None

    def __str__(self) -> str:
        """__str__"""
        return get_obj_attr_values_as_string(self)

    def __init__(self, **kwargs) -> None:
        """__init__"""
        self.active_command = None
        self.active_scene = None
        self.fwversion = None
        self.mode = None  # cmd, cct, rgb
        self.open_slots = None
        self.sdkversion = None
        self.status = None
        self.temperature = None
        self._brightness = None
        self._color = None
        super().__init__(**kwargs)
        LOGGER.debug(f"save status {self}")

    @property
    def brightness(self) -> int | None:
        return self._brightness

    @brightness.setter
    def brightness(self, brightness: dict[str, int]) -> None:
        self._brightness = int(brightness["percentage"])

    @property
    def color(self) -> RGBColor | None:
        return self._color

    @color.setter
    def color(self, color: dict[str, int]) -> None:
        self._color = (
            RGBColor(color["red"], color["green"], color["blue"]) if color else None
        )


class KlyqaBulb(KlyqaDevice):
    """KlyqaBulb"""

    # status: KlyqaBulbResponseStatus = None

    def __init__(self) -> None:
        super().__init__()
        # self.status = KlyqaBulbResponseStatus()
        self.response_classes["status"] = KlyqaBulbResponseStatus

    def setTemp(self, temp: int):
        temperature_enum = []
        try:
            if self.ident:
                temperature_enum = [
                    trait["value_schema"]["properties"]["colorTemperature"]["enum"]
                    for trait in device_configs[self.ident.product_id]["deviceTraits"]
                    if trait["trait"] == "@core/traits/color-temperature"
                ]
                if len(temperature_enum) < 2:
                    raise Exception()
        except:
            LOGGER.error("No temperature change on the bulb available")
            return False
        if temp < temperature_enum[0] or temp > temperature_enum[1]:
            LOGGER.error(
                "Temperature for bulb out of range ["
                + temperature_enum[0]
                + ", "
                + temperature_enum[1]
                + "]."
            )
            return False


def color_message(red, green, blue, transition, skipWait=False) -> tuple[str, int]:
    waitTime = transition if not skipWait else 0
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


def temperature_message(temperature, transition, skipWait=False) -> tuple[str, int]:
    waitTime = transition if not skipWait else 0
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
    red, green, blue, warm, cold, transition, skipWait
) -> tuple[str, int]:
    waitTime = transition if not skipWait else 0
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


def brightness_message(brightness, transition) -> tuple[str, int]:
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
        transition,
    )

def external_source_message(protocol, port, channel):
    if (protocol == 0):
        protocol_str = "EXT_OFF"
    elif (protocol == 1):
        protocol_str = "EXT_UDP"
    elif (protocol == 2):
        protocol_str = "EXT_E131"
    elif (protocol == 3):
        protocol_str = "EXT_TPM2"
    else:
        protocol_str = "EXT_OFF"
    return json.dumps(
            {
                "type": "request",
                "external": {
                    "mode": protocol_str,
                    "port": int(port),
                    "channel": int(channel)
                }
            }
        )


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
        help="set temperature command (kelvin range depends on lamp profile) (lower: warm, higher: cold)",
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


async def process_args_to_msg_lighting(
    args,
    args_in,
    send_to_devices_cb,
    message_queue_tx_local,
    message_queue_tx_command_cloud,
    message_queue_tx_state_cloud,
    scene_list: list[str],
) -> bool:
    """process_args_to_msg_lighting"""

    def local_and_cloud_command_msg(json_msg, timeout) -> None:
        message_queue_tx_local.append((json.dumps(json_msg), timeout))
        message_queue_tx_command_cloud.append(json_msg)

    # TODO: Missing cloud discovery and interactive device selection. Send to devices if given as argument working.
    if (args.local or args.tryLocalThanCloud) and (
        not args.device_name
        and not args.device_unitids
        and not args.allDevices
        and not args.discover
    ):
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

        uids = await send_to_devices_cb(discover_local_args_parsed)
        if isinstance(uids, set) or isinstance(uids, list):
            # args_in.extend(["--device_unitids", ",".join(list(uids))])
            args_in = ["--device_unitids", ",".join(list(uids))] + args_in
        elif isinstance(uids, str) and uids == "no_devices":
            return False
        else:
            LOGGER.error("Error during local discovery of the devices.")
            return False

        add_command_args_bulb(parser=orginal_args_parser)
        args = orginal_args_parser.parse_args(args=args_in, namespace=args)

    commands_to_send: list[str] = [
        i for i in commands_send_to_bulb if hasattr(args, i) and getattr(args, i)
    ]

    if commands_to_send:
        print("Commands to send to devices: " + ", ".join(commands_to_send))
    else:
        print("Commands (arguments):")
        print(sep_width * "-")

        def get_temp_range(product_id):
            temperature_enum = []
            try:
                temperature_enum = [
                    trait["value_schema"]["properties"]["colorTemperature"]["enum"]
                    if "properties" in trait["value_schema"]
                    else trait["value_schema"]["enum"]
                    for trait in device_configs[product_id]["deviceTraits"]
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

        temperature_enum = []
        color: list[int] = [0, 255]
        brightness: list[int] = [0, 100]
        for u_id in args.device_unitids[0].split(","):
            u_id: str = format_uid(u_id)
            if u_id not in self.devices or not self.devices[u_id].ident:

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

                    ret = send_to_devices_cb(discover_local_args_parsed2)
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
                temperature_enum: tuple[int, int] = get_inner_range(
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

    if args.ota is not None:
        local_and_cloud_command_msg({"type": "fw_update", "url": args.ota}, 10000)

    if args.ping:
        local_and_cloud_command_msg({"type": "ping"}, 10000)

    if args.request:
        local_and_cloud_command_msg({"type": "request"}, 10000)
        
    if args.external_source:
        mode, port, channel = args.external_source
        local_and_cloud_command_msg(external_source_message(int(mode), port, channel), 0)

    if args.enable_tb is not None:
        a = args.enable_tb[0]
        if a != "yes" and a != "no":
            print("ERROR --enable_tb needs to be yes or no")
            sys.exit(1)

        message_queue_tx_local.append(
            (json.dumps({"type": "backend", "link_enabled": a}), 1000)
        )

    if args.passive:
        pass

    if args.power:
        message_queue_tx_local.append(
            (json.dumps({"type": "request", "status": args.power[0]}), 500)
        )
        message_queue_tx_state_cloud.append({"status": args.power[0]})

    def forced_continue(reason: str) -> bool:
        if not args.force:
            LOGGER.error(reason)
            return False
        else:
            LOGGER.info(reason)
            LOGGER.info("Enforced send")
            return True

    """range"""
    Check_device_parameter = Enum(
        "Check_device_parameter", "color brightness temperature scene"
    )

    def missing_config(product_id) -> bool:
        if not forced_continue(
            "Missing or faulty config values for device " + " product_id: " + product_id
        ):
            return True
        return False

    #### Needing config profile versions implementation for checking trait ranges ###

    def check_color_range(product_id, values) -> bool:
        color_enum = []
        try:
            # # different device trait schematics. for now go typical range
            # color_enum = [
            #     trait["value_schema"]["definitions"]["color_value"]
            #     for trait in device_configs[product_id]["deviceTraits"]
            #     if trait["trait"] == "@core/traits/color"
            # ]
            # color_range = (
            #     color_enum[0]["minimum"],
            #     color_enum[0]["maximum"],
            # )
            color_range = (
                0,
                255,
            )
            for value in values:
                if int(value) < color_range[0] or int(value) > color_range[1]:
                    return forced_continue(
                        f"Color {value} out of range [{color_range[0]}..{color_range[1]}]."
                    )

        except:
            return not missing_config(product_id)
        return True

    def check_brightness_range(product_id, value) -> bool:
        brightness_enum = []
        try:
            # different device trait schematics. for now go typical range
            # brightness_enum = [
            #     trait["value_schema"]["properties"]["brightness"]
            #     for trait in device_configs[product_id]["deviceTraits"]
            #     if trait["trait"] == "@core/traits/brightness"
            # ]
            # brightness_range = (
            #     brightness_enum[0]["minimum"],
            #     brightness_enum[0]["maximum"],
            # )
            brightness_range = (
                0,
                100,
            )

            if int(value) < brightness_range[0] or int(value) > brightness_range[1]:
                return forced_continue(
                    f"Brightness {value} out of range [{brightness_range[0]}..{brightness_range[1]}]."
                )

        except:
            return not missing_config(product_id)
        return True

    def check_temp_range(product_id, value) -> bool:
        temperature_range: list[int] = []
        try:
            # # different device trait schematics. for now go typical range
            # temperature_range = [
            #     trait["value_schema"]["properties"]["colorTemperature"]["enum"]
            #     if "properties" in trait["value_schema"]
            #     else trait["value_schema"]["enum"]
            #     for trait in device_configs[product_id]["deviceTraits"]
            #     if trait["trait"] == "@core/traits/color-temperature"
            # ][0]
            temperature_range = [2000, 6500]
            if int(value) < temperature_range[0] or int(value) > temperature_range[1]:
                return forced_continue(
                    f"Temperature {value} out of range [{temperature_range[0]}..{temperature_range[1]}]."
                )
        except Exception as excp:
            return not missing_config(product_id)
        return True

    def check_scene_support(product_id, scene) -> bool:
        color_enum = []
        try:
            # color_enum = [
            #     trait
            #     for trait in device_configs[product_id]["deviceTraits"]
            #     if trait["trait"] == "@core/traits/color"
            # ]
            # color_support = len(color_enum) > 0

            # if not color_support and not "cwww" in scene:
            #     return forced_continue(
            #         f"Scene {scene['label']} not supported by device product {product_id}."
            #     )
            return True

        except:
            return not missing_config(product_id)
        return True

    check_range = {
        Check_device_parameter.color: check_color_range,
        Check_device_parameter.brightness: check_brightness_range,
        Check_device_parameter.temperature: check_temp_range,
        Check_device_parameter.scene: check_scene_support,
    }

    def check_device_parameter(
        parameter: Check_device_parameter, values, product_id
    ) -> bool:
        # if not device_configs and not forced_continue("Missing configs for devices."):
        #     return False

        # for u_id in target_device_uids:
        #     # dev = [
        #     #     device["productId"]
        #     #     for device in self.acc_settings["devices"]
        #     #     if format_uid(device["localDeviceId"]) == format_uid(u_id)
        #     # ]
        #     # product_id = dev[0]
        #     product_id = self.devices[u_id].ident.product_id

        if not check_range[parameter](product_id, values):
            return False
        return True

    if args.color is not None:
        r, g, b = args.color
        # if not check_device_parameter(Check_device_parameter.color, [r, g, b]):
        #     return False

        tt = args.transitionTime[0]
        msg = color_message(r, g, b, int(tt), skipWait=args.brightness is not None)

        check_color = functools.partial(
            check_device_parameter, Check_device_parameter.color, [r, g, b]
        )
        msg = msg + (check_color,)

        message_queue_tx_local.append(msg)
        col = json.loads(msg[0])["color"]
        message_queue_tx_state_cloud.append({"color": col})

    if args.temperature is not None:
        temperature = args.temperature[0]
        # if not check_device_parameter(Check_device_parameter.temperature, temperature):
        #     return False

        tt = args.transitionTime[0]
        msg = temperature_message(
            temperature, int(tt), skipWait=args.brightness is not None
        )

        check_temperature = functools.partial(
            check_device_parameter, Check_device_parameter.temperature, temperature
        )
        msg = msg + (check_temperature,)

        temperature = json.loads(msg[0])["temperature"]
        message_queue_tx_local.append(msg)
        message_queue_tx_state_cloud.append({"temperature": temperature})

    if args.brightness is not None:
        brightness = args.brightness[0]
        # if not check_device_parameter(Check_device_parameter.brightness, brightness):
        #     return False

        tt = args.transitionTime[0]
        msg: tuple[str, int] = brightness_message(brightness, int(tt))

        check_brightness = functools.partial(
            check_device_parameter, Check_device_parameter.brightness, brightness
        )
        msg = msg + (check_brightness,)

        message_queue_tx_local.append(msg)
        brightness = json.loads(msg[0])["brightness"]
        message_queue_tx_state_cloud.append({"brightness": brightness})

    if args.percent_color is not None:
        if not device_configs and not forced_continue("Missing configs for devices."):
            return False
        r, g, b, w, c = args.percent_color
        tt = args.transitionTime[0]
        msg = percent_color_message(
            r, g, b, w, c, int(tt), skipWait=args.brightness is not None
        )
        message_queue_tx_local.append(msg)
        p_color = json.loads(msg[0])["p_color"]
        message_queue_tx_state_cloud.append({"p_color": p_color})

    if args.factory_reset:
        local_and_cloud_command_msg({"type": "factory_reset"}, 500)

    if args.fade is not None and len(args.fade) == 2:
        local_and_cloud_command_msg(
            {"type": "request", "fade_out": args.fade[1], "fade_in": args.fade[0]}, 500
        )

    scene = ""
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

    # if (
    #     args.WW
    #     or args.daylight
    #     or args.CW
    #     or args.nightlight
    #     or args.relax
    #     or args.TVtime
    #     or args.comfort
    #     or args.focused
    #     or args.fireplace
    #     or args.club
    #     or args.romantic
    #     or args.gentle
    #     or args.summer
    #     or args.jungle
    #     or args.ocean
    #     or args.fall  # Autumn
    #     or args.sunset
    #     or args.party
    #     or args.spring
    #     or args.forest
    #     or args.deep_sea
    #     or args.tropical
    #     or args.magic
    #     or args.mystic
    #     or args.cotton
    #     or args.ice
    #     # or args.monjito
    # ):
    if scene:
        scene_result = [x for x in BULB_SCENES if x["label"] == scene]
        if not len(scene_result) or len(scene_result) > 1:
            LOGGER.error(
                f"Scene {scene} not found or more than one scene with the name found."
            )
            return False
        scene_obj = scene_result[0]

        # check_brightness = functools.partial(check_device_parameter, Check_device_parameter.scene, scene_obj)
        # msg = msg + (check_brightness,)
        # if not check_device_parameter(Check_device_parameter.scene, scene_obj):
        #     return False
        commands = scene_obj["commands"]
        if len(commands.split(";")) > 2:
            commands += "l 0;"
        args.routine_id = 0
        args.routine_put = True
        args.routine_commands = commands
        args.routine_scene = str(scene_obj["id"])

    if args.routine_list:
        local_and_cloud_command_msg({"type": "routine", "action": "list"}, 500)

    if args.routine_put and args.routine_id is not None:
        local_and_cloud_command_msg(
            {
                "type": "routine",
                "action": "put",
                "id": args.routine_id,
                "scene": args.routine_scene,
                "commands": args.routine_commands,
            },
            500,
        )

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

    if scene:
        scene_list.append(scene)


# async def discover_lightings(args, args_in, send_to_devices_cb):
