"""Response message"""
from __future__ import annotations

import datetime
from typing import Any


class ResponseMessage:
    """General response message class."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize response message with kwargs."""

        self._attr_type: str = ""
        self._attr_ts: datetime.datetime | None = None
        self.update(**kwargs)

    def update(self, **kwargs: Any) -> None:
        """Align class attribute values to the kwargs values."""

        self.ts = datetime.datetime.now()

        # Walk through parsed kwargs dict and look if names in dict exists as
        # attribute in class, then apply the value in kwargs to the value in
        # class.
        for attr, val in kwargs.items():
            if hasattr(self, attr):
                setattr(self, attr, val)

    @property
    def type(self) -> str:
        """Get response message type."""

        return self._attr_type

    @type.setter
    def type(self, rm_type: str) -> None:
        self._attr_type = rm_type

    @property
    def ts(self) -> datetime.datetime | None:
        """Get last updated datetime."""

        return self._attr_ts

    @ts.setter
    def ts(self, timestamp: datetime.datetime | None) -> None:

        self._attr_ts = timestamp
