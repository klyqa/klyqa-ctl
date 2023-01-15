"""Response identity message"""
from typing import Any
from klyqa_ctl.devices.response_message import ResponseMessage
from klyqa_ctl.general.general import format_uid


# eventually dataclass
class ResponseIdentityMessage(ResponseMessage):
    """Device response identity message"""

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        self.fw_version: str = ""
        self.fw_build: str = ""
        self.hw_version: str = ""
        self.manufacturer_id: str = ""
        self.product_id: str = ""
        self.sdk_version: str = ""
        self._attr_unit_id: str = ""
        super().__init__(**kwargs)

    def update(self, **kwargs: Any) -> None:
        super().update(**kwargs)

    @property
    def unit_id(self) -> str:
        return self._attr_unit_id

    @unit_id.setter
    def unit_id(self, unit_id: str) -> None:
        self._attr_unit_id = format_uid(unit_id)