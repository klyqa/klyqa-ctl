"""Vacuum cleaner response status"""
from __future__ import annotations
import datetime
from typing import Any
from klyqa_ctl.devices.device import DeviceResponse

from klyqa_ctl.general.general import LOGGER, get_obj_attr_values_as_string

class ResponseStatus(DeviceResponse):
    """Vacuum cleaner Response Status"""

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
