"""General types, constants, functions"""
from __future__ import annotations
import asyncio, aiofiles
from enum import Enum

from typing import Any, Literal
import datetime
import json
import logging
import os
import sys

LOGGER: logging.Logger = logging.getLogger(__package__)
LOGGER.setLevel(level=logging.INFO)
formatter: logging.Formatter = logging.Formatter(
    "%(asctime)s %(levelname)-8s - %(message)s"
)

logging_hdl = logging.StreamHandler()
logging_hdl.setLevel(level=logging.INFO)
logging_hdl.setFormatter(formatter)

LOGGER.addHandler(logging_hdl)

DEFAULT_SEND_TIMEOUT_MS = 30
DEFAULT_COM_PROC_TIMEOUT_SECS = 600

TypeJSON = dict[str, Any]

""" string output separator width """
sep_width = 0


PRODUCT_URLS: dict[str, str] = {
    """TODO: Make permalinks for urls."""
    "@klyqa.lighting.cw-ww.gu10": "https://klyqa.de/produkte/gu10-white-strahler",
    "@klyqa.lighting.rgb-cw-ww.gu10": "https://klyqa.de/produkte/gu10-color-strahler",
    "@klyqa.lighting.cw-ww.g95": "https://www.klyqa.de/produkte/g95-vintage-lampe",
    "@klyqa.lighting.rgb-cw-ww.e14": "https://klyqa.de/produkte/e14-color-lampe",
    "@klyqa.lighting.cw-ww.e14": "https://klyqa.de/produkte/gu10-white-strahler",
    "@klyqa.lighting.rgb-cw-ww.e27": "https://www.klyqa.de/produkte/e27-color-lampe",
    "@klyqa.lighting.cw-ww.e27": "https://klyqa.de/produkte/e27-white-lampe",
    "@klyqa.cleaning.vc1": "https://klyqa.de/Alle-Produkte/Smarter-Starter",
}


SEND_LOOP_MAX_SLEEP_TIME = 0.05
KLYQA_CTL_VERSION="1.0.17"

DeviceType = Enum("DeviceType", "cleaner lighting")


class RGBColor:
    """RGBColor"""

    r: int
    g: int
    b: int

    def __str__(self) -> str:
        return "[" + ",".join([str(self.r), str(self.g), str(self.b)]) + "]"
        # return get_obj_values_as_string(self)

    def __init__(self, r: int, g: int, b: int) -> None:
        self.r = r
        self.g = g
        self.b = b


class AsyncIOLock:
    """AsyncIOLock"""

    task: asyncio.Task | None
    lock: asyncio.Lock
    _instance = None

    def __init__(self) -> None:
        """__init__"""
        self.lock = asyncio.Lock()
        self.task = None

    async def acquire(self) -> None:
        """acquire"""
        await self.lock.acquire()
        self.task = asyncio.current_task()

    def release(self) -> None:
        """release"""
        self.lock.release()

    def force_unlock(self) -> bool:
        """force_unlock"""
        try:
            if self.task:
                self.task.cancel()
            self.lock.release()
        except:
            return False
        return True

    @classmethod
    def instance(
        cls,
    ):
        """instance"""
        if cls._instance is None:
            LOGGER.debug("Creating new AsyncIOLock instance")
            cls._instance = cls.__new__(cls)
            # Put any initialization here.
            cls._instance.__init__()
        return cls._instance


class RefParse:
    """RefParse"""

    ref = None

    def __init__(self, ref) -> None:
        self.ref = ref


Device_config = dict


async def async_json_cache(json_data, json_file) -> tuple[Device_config, bool]:
    """
    If json data is given write it to cache json_file.
    Else try to read from json_file the cache.
    """

    return_json: Device_config = json_data
    cached = False
    if json_data:
        """
        save the json for offline cache in dirpath where called script resides
        ids: { sets }
        """
        return_json = json_data
        try:
            s = ""
            for id, sets in json_data.items():
                if isinstance(sets, (datetime.datetime, datetime.date)):
                    sets = sets.isoformat()
                s = s + '"' + id + '": ' + json.dumps(sets) + ", "
            s = "{" + s[:-2] + "}"
            async with aiofiles.open(
                os.path.dirname(sys.argv[0]) + f"/{json_file}", mode="w"
            ) as f:
                await f.write(s)
        except Exception as e:
            LOGGER.warning(f'Could not save cache for json file "{json_file}".')
    else:
        """no json data, take cached json from disk if available"""
        try:
            async with aiofiles.open(
                os.path.dirname(sys.argv[0]) + f"/{json_file}", mode="r"
            ) as f:
                s = await f.read()
            return_json = json.loads(s)
            cached = True
        except:
            LOGGER.warning(f'No cache from json file "{json_file}" available.')
    return (return_json, cached)


def get_fields(object):
    """get_fields"""
    if hasattr(object, "__dict__"):
        return object.__dict__.keys()
    else:
        return dir(object)


def get_obj_attrs_as_string(object) -> str:
    """get_obj_attrs_as_string"""
    fields = get_fields(object)
    attrs = [
        a for a in fields if not a.startswith("__") and not callable(getattr(object, a))
    ]
    return ", ".join(attrs)


def get_obj_attr_values_as_string(object) -> str:
    """get_obj_attr_values_as_string"""
    fields = get_fields(object)
    attrs = [
        a for a in fields if not a.startswith("__") and not callable(getattr(object, a))
    ]
    vals = []
    for a in attrs:
        _str: str = str(getattr(object, a))
        vals.append(_str if _str else '""')
    return ", ".join(vals)


AES_KEY_DEV: bytes = bytes(
    [
        0x00,
        0x11,
        0x22,
        0x33,
        0x44,
        0x55,
        0x66,
        0x77,
        0x88,
        0x99,
        0xAA,
        0xBB,
        0xCC,
        0xDD,
        0xEE,
        0xFF,
    ]
)
