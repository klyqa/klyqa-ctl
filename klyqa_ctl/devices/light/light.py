"""! @brief Contains all functions, constants and classes regarding lighting."""
from __future__ import annotations
import traceback
from typing import Any
from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.light.response_status import ResponseStatus
from klyqa_ctl.general.general import LOGGER, Range, TypeJson

class Light(Device):
    """Light"""

    def __init__(self) -> None:
        super().__init__()
        self.response_classes["status"] = ResponseStatus
        self._attr_brightness_range: Range | None = None
        self._attr_temperature_range: Range | None = None
        self._attr_color_range: Range | None = None
        
    @property
    def brightness_range(self) -> Range | None:
        return self._attr_brightness_range
    
    @brightness_range.setter
    def brightness_range(self, brightness_range: Range | None ) -> None:
        self._attr_brightness_range = brightness_range
        
    @property
    def temperature_range(self) -> Range | None:
        return self._attr_temperature_range
    
    @temperature_range.setter
    def temperature_range(self, temperature_range: Range | None) -> None:
        self._attr_temperature_range = temperature_range
        
    @property
    def color_range(self) -> Range | None:
        return self._attr_color_range
    
    @color_range.setter
    def color_range(self, color_range: Range | None) -> None:
        self._attr_color_range = color_range
        
    def set_brightness_range(self, device_config: TypeJson) -> None:
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
        
    def set_temperature_range(self, device_config: TypeJson) -> None:
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
        
    def set_color_range(self, device_config: TypeJson) -> None:  
        color_enum: list[Any] = []
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
                    color_enum = [
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
        
    def read_device_config(self, device_config: TypeJson) -> None:
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
