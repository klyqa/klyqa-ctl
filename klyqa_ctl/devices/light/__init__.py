"""Lighting"""
from __future__ import annotations
"""! @brief Contains all functions, constants and classes regarding lighting."""

# Imports
from typing import Callable, List
import argparse
from dataclasses import dataclass
import functools
import json
import sys

from klyqa_ctl.general.parameters import add_config_args, get_description_parser
from klyqa_ctl.devices.device import *
from klyqa_ctl.general.general import *

# Global Constants
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


# Classes
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
        self.brightness_range: Range | None = None
        self.temperature_range: Range | None = None
        self.color_range: Range | None = None
        
    def set_brightness_range(self, device_config) -> None:
        brightness_enum: list[Any] = []
        try:
            if self.acc_sets["productId"].endswith(".rgb-cw-ww.e27"):
                brightness_enum = [
                    trait["value_schema"]["properties"]["brightness"]
                    for trait in device_config["deviceTraits"]
                    if trait["trait"] == "@core/traits/brightness"
                ]
                self.brightness_range = Range(
                    brightness_enum[0]["minimum"],
                    brightness_enum[0]["maximum"],
                )
            else:
                try:
                    brightness_enum = [
                        trait["value_schema"]["properties"]["brightness"]
                        for trait in device_config["deviceTraits"]
                        if trait["trait"] == "@core/traits/brightness"
                    ]
                    self.brightness_range = Range(
                        brightness_enum[0]["minimum"],
                        brightness_enum[0]["maximum"],
                    )
                except:
                    self.brightness_range = Range(0, 100)
        except Exception as e:
            LOGGER.error("Error during setting brightness range for klyqa bulb!")
            LOGGER.debug(f"{traceback.format_exc()}")
        
    def set_temperature_range(self, device_config) -> None:
        try:
            if self.acc_sets["productId"].endswith(".rgb-cw-ww.e27"):
                self.temperature_range = Range(*[
                    trait["value_schema"]["properties"]["colorTemperature"]["enum"]
                    for trait in device_config["deviceTraits"]
                    if trait["trait"] == "@core/traits/color-temperature"
                ][0])
            else:
                try:
                    LOGGER.debug("Not known product id try default trait search.")
                    self.temperature_range = Range(*[
                        trait["value_schema"]["properties"]["colorTemperature"]["enum"]
                        if "properties" in trait["value_schema"]
                        else trait["value_schema"]["enum"]
                        for trait in device_config["deviceTraits"]
                        if trait["trait"] == "@core/traits/color-temperature"
                    ][0])
                except:
                    LOGGER.debug("Bulb product id trait search failed using default temperature numbers.")
                    self.temperature_range = Range(2000, 6500)
        except Exception as e:
            LOGGER.error("Error during setting temperature range for klyqa bulb!")
            LOGGER.debug(f"{traceback.format_exc()}")
        
    def set_color_range(self, device_config) -> None:  
        color_enum = []
        try:
            if self.acc_sets["productId"].endswith(".rgb-cw-ww.e27"):
                color_enum = [
                    trait["value_schema"]["definitions"]["color_value"]
                    for trait in device_config["deviceTraits"]
                    if trait["trait"] == "@core/traits/color"
                ]
                self.color_range = Range(
                    color_enum[0]["minimum"],
                    color_enum[0]["maximum"],
                )
            else:
                try:
                    color_enum: list[Any] = [
                        trait["value_schema"]["definitions"]["color_value"]
                        for trait in device_config["deviceTraits"]
                        if trait["trait"] == "@core/traits/color"
                    ]
                    self.color_range = Range(
                        color_enum[0]["minimum"],
                        color_enum[0]["maximum"],
                    )
                except:
                    self.color_range = Range(0, 255)
        except Exception as e:
            LOGGER.error("Error during setting color range for klyqa bulb!")
            LOGGER.debug(f"{traceback.format_exc()}")
        
    def read_device_config(self, device_config) -> None:
        super().read_device_config(device_config)
        self.set_brightness_range(device_config)
        self.set_temperature_range(device_config)
        if ".rgb" in self.acc_sets["productId"]:
            self.set_color_range(device_config)

    def set_temperature(self, temp: int) -> bool:
        if not self.device_config:
            return False
        temperature_enum = []
        try:
            if self.ident:
                temperature_enum = [
                    trait["value_schema"]["properties"]["colorTemperature"]["enum"]
                    for trait in self.device_config["deviceTraits"]
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
        return True
