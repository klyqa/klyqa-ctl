"""Response message"""
from __future__ import annotations

import datetime
from typing import Any


class ResponseMessage:
    """Response message"""

    def __init__(self, **kwargs: Any) -> None:
        """__init__"""
        self._attr_type: str = ""
        self._attr_ts: datetime.datetime | None = None
        self.update(**kwargs)

    def update(self, **kwargs: Any) -> None:
        self.ts = datetime.datetime.now()
        # Walk through parsed kwargs dict and look if names in dict exists as attribute in class,
        # then apply the value in kwargs to the value in class.
        for attr in kwargs:
            if hasattr(self, attr):
                setattr(self, attr, kwargs[attr])

    @property
    def type(self) -> str:
        return self._attr_type

    @type.setter
    def type(self, type: str) -> None:
        self._attr_type = type

    @property
    def ts(self) -> datetime.datetime | None:
        return self._attr_ts

    @ts.setter
    def ts(self, ts: datetime.datetime | None) -> None:
        self._attr_ts = ts
