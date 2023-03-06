"""Response status."""
from __future__ import annotations

from typing import Any

from klyqa_ctl.devices.device import ResponseMessage
from klyqa_ctl.general.general import (
    LOGGER,
    RgbColor,
    get_obj_attr_values_as_string,
    task_log_debug,
)


class ResponseStatus(ResponseMessage):
    """Response status of a bulb."""

    _attr_active_command: int | None = None
    _attr_active_scene: str | None = None
    _attr_fwversion: str | None = None
    _attr_mode: str | None = None
    _attr_open_slots: int | None = None
    _attr_sdkversion: str | None = None
    _attr_status: str | None = None
    _attr_temperature: int | None = None
    _attr_brightness: int | None
    _attr_color: RgbColor | None
    connected: bool = False

    def __str__(self) -> str:
        """__str__"""
        return get_obj_attr_values_as_string(self)

    def __init__(self, **kwargs: Any) -> None:
        """Initialization to an empty light response status message."""

        self._attr_active_command = None
        self._attr_active_scene = None
        self._attr_fwversion = None
        self._attr_mode = None  # cmd, cct, rgb
        self._attr_open_slots = None
        self._attr_sdkversion = None
        self._attr_status = None
        self._attr_temperature = None
        self._attr_brightness = None
        self._attr_open_slots = None
        self._attr_color = None
        self.connected = False
        super().__init__(**kwargs)
        task_log_debug(f"save status {self}")

    @property
    def active_command(self) -> int | None:
        return self._attr_active_command

    @active_command.setter
    def active_command(self, active_command: int | None) -> None:
        self._attr_active_command = active_command

    @property
    def active_scene(self) -> str | None:
        return self._attr_active_scene

    @active_scene.setter
    def active_scene(self, active_scene: str | None) -> None:
        self._attr_active_scene = active_scene

    @property
    def fwversion(self) -> str | None:
        return self._attr_fwversion

    @fwversion.setter
    def fwversion(self, fwversion: str | None) -> None:
        self._attr_fwversion = fwversion

    @property
    def mode(self) -> str | None:
        return self._attr_mode

    @mode.setter
    def mode(self, mode: str | None) -> None:
        self._attr_mode = mode

    @property
    def open_slots(self) -> int | None:
        return self._attr_open_slots

    @open_slots.setter
    def open_slots(self, open_slots: int | None) -> None:
        self._attr_open_slots = open_slots

    @property
    def sdkversion(self) -> str | None:
        return self._attr_sdkversion

    @sdkversion.setter
    def sdkversion(self, sdkversion: str | None) -> None:
        self._attr_sdkversion = sdkversion

    @property
    def status(self) -> str | None:
        return self._attr_status

    @status.setter
    def status(self, status: str | None) -> None:
        self._attr_status = status

    @property
    def temperature(self) -> int | None:
        return self._attr_temperature

    @temperature.setter
    def temperature(self, temperature: int | None) -> None:
        self._attr_temperature = temperature

    @property
    def brightness(self) -> int | None:
        return self._attr_brightness

    @brightness.setter
    def brightness(self, brightness: dict[str, int]) -> None:
        self._attr_brightness = int(brightness["percentage"])

    @property
    def color(self) -> RgbColor | None:
        return self._attr_color

    @color.setter
    def color(self, color: dict[str, int]) -> None:
        self._attr_color = (
            RgbColor(color["red"], color["green"], color["blue"])
            if color
            else None
        )
