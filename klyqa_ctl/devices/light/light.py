""" Contains all functions, constants and classes regarding
lighting."""
from __future__ import annotations

from typing import Any

from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.light.response_status import ResponseStatus
from klyqa_ctl.general.general import (
    LOGGER,
    Range,
    TypeJson,
    task_log_debug,
    task_log_trace,
    task_log_trace_ex,
)


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
    def brightness_range(self, brightness_range: Range | None) -> None:
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
        """Set the device brightness range limits for minimum and maximum."""

        brightness_enum: list[Any] = []
        try:
            if self.ident and self.product_id.endswith(".rgb-cw-ww.e27"):
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
                    for trait in device_config["deviceTraits"]:
                        if trait["trait"] != "@core/traits/brightness":
                            continue
                        if trait["value_schema"]["type"] == "integer":
                            self.brightness_range = Range(
                                trait["value_schema"]["minimum"],
                                trait["value_schema"]["maximum"],
                            )
                            break
                except Exception:
                    self.brightness_range = Range(0, 100)
                    task_log_trace(
                        "Can't read brightness range%s. Falling back to"
                        " default Range.",
                        f" for product id {self.product_id}"
                        if self.ident
                        else "",
                    )
        except Exception:
            LOGGER.error(
                "Error during setting brightness range for klyqa bulb!"
            )
            task_log_trace_ex()

    def set_temperature_range(self, device_config: TypeJson) -> None:
        """Set the device temperature range limits for minimum and maximum."""

        try:
            if self.ident and self.product_id.endswith(".rgb-cw-ww.e27"):
                self.temperature_range = Range(
                    *[
                        trait["value_schema"]["properties"][
                            "colorTemperature"
                        ]["enum"]
                        for trait in device_config["deviceTraits"]
                        if trait["trait"] == "@core/traits/color-temperature"
                    ][0]
                )
            else:
                try:
                    task_log_debug(
                        "Not known product id try default trait search."
                    )
                    self.temperature_range = Range(
                        *[
                            trait["value_schema"]["properties"][
                                "colorTemperature"
                            ]["enum"]
                            if "properties" in trait["value_schema"]
                            else trait["value_schema"]["enum"]
                            for trait in device_config["deviceTraits"]
                            if trait["trait"]
                            == "@core/traits/color-temperature"
                        ][0]
                    )
                    task_log_debug("Temperature range setted.")
                except KeyError:
                    task_log_debug(
                        "Bulb product id trait search failed using default"
                        " temperature numbers."
                    )
                    self.temperature_range = Range(2000, 6500)
                    task_log_trace(
                        "Can't read temperature range%s. Falling back to"
                        " default Range.",
                        f" for product id {self.product_id}"
                        if self.ident
                        else "",
                    )
        except KeyError:
            LOGGER.error(
                "Error during setting temperature range for klyqa bulb!"
            )
            task_log_trace_ex()

    def set_color_range(self, device_config: TypeJson) -> None:
        """Set the device color range limits for minimum and maximum."""

        color_enum: list[Any] = []
        try:
            if self.ident and self.product_id.endswith(".rgb-cw-ww.e27"):
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
                except KeyError:
                    self.color_range = Range(0, 255)
                    task_log_trace(
                        "Can't read color range%s. Falling back to "
                        + "default Range.",
                        f" for product id {self.product_id}"
                        if self.ident
                        else "",
                    )
        except KeyError:
            LOGGER.error("Error during setting color range for klyqa bulb!")
            task_log_trace_ex()

    def read_device_config(self, device_config: TypeJson) -> None:
        """Read and set the device config from json configuration."""

        super().read_device_config(device_config)
        self.set_brightness_range(device_config)
        self.set_temperature_range(device_config)
        if self.ident and ".rgb" in self.product_id:
            self.set_color_range(device_config)

    def set_temperature(self, temp: int) -> bool:
        """Set the device temperature if the temperature is within the
        limits."""

        if not self.device_config:
            return False
        temperature_enum: list[Any] = []
        try:
            if self.ident:
                temperature_enum = [
                    trait["value_schema"]["properties"]["colorTemperature"][
                        "enum"
                    ]
                    for trait in self.device_config["deviceTraits"]
                    if trait["trait"] == "@core/traits/color-temperature"
                ]
                if len(temperature_enum) < 2:
                    raise KeyError()
        except KeyError:
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
