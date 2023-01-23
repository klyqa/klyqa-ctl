"""Response identity message"""
from typing import Any

from klyqa_ctl.devices.response_message import ResponseMessage
from klyqa_ctl.general.unit_id import UnitId


# eventually dataclass
class ResponseIdentityMessage(ResponseMessage):
    """Device response identity message"""

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        self._attr_fw_version: str = ""
        self._attr_fw_build: str = ""
        self._attr_hw_version: str = ""
        self._attr_manufacturer_id: str = ""
        self._attr_product_id: str = ""
        self._attr_sdk_version: str = ""
        self._attr_unit_id: str = ""
        super().__init__(**kwargs)

    def update(self, **kwargs: Any) -> None:
        super().update(**kwargs)

    @property
    def unit_id(self) -> str:
        return self._attr_unit_id

    @unit_id.setter
    def unit_id(self, unit_id: str) -> None:
        self._attr_unit_id = str(UnitId(unit_id))

    @property
    def fw_version(self) -> str:
        return self._attr_fw_version

    @fw_version.setter
    def fw_version(self, fw_version: str) -> None:
        self._attr_fw_version = fw_version

    @property
    def fw_build(self) -> str:
        return self._attr_fw_build

    @fw_build.setter
    def fw_build(self, fw_build: str) -> None:
        self._attr_fw_build = fw_build

    @property
    def hw_version(self) -> str:
        return self._attr_hw_version

    @hw_version.setter
    def hw_version(self, hw_version: str) -> None:
        self._attr_hw_version = hw_version

    @property
    def manufacturer_id(self) -> str:
        return self._attr_manufacturer_id

    @manufacturer_id.setter
    def manufacturer_id(self, manufacturer_id: str) -> None:
        self._attr_manufacturer_id = manufacturer_id

    @property
    def product_id(self) -> str:
        return self._attr_product_id

    @product_id.setter
    def product_id(self, product_id: str) -> None:
        self._attr_product_id = product_id

    @property
    def sdk_version(self) -> str:
        return self._attr_sdk_version

    @sdk_version.setter
    def sdk_version(self, sdk_version: str) -> None:
        self._attr_sdk_version = sdk_version
