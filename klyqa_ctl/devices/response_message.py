"""Response message"""
from __future__ import annotations
import datetime
from typing import Any

class ResponseMessage:
    """Response message"""
    
    def __init__(self, **kwargs: Any) -> None:
        """__init__"""
        self.type: str = ""
        self.ts: datetime.datetime | None = None
        self.update(**kwargs)

    def update(self, **kwargs: Any) -> None:
        self.ts = datetime.datetime.now()
        # Walk through parsed kwargs dict and look if names in dict exists as attribute in class,
        # then apply the value in kwargs to the value in class.
        for attr in kwargs:
            if hasattr(self, attr):
                setattr(self, attr, kwargs[attr])