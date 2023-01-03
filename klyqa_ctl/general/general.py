"""General types, constants, functions"""
from __future__ import annotations
import asyncio, aiofiles
from threading import Event, Thread
from dataclasses import dataclass
from enum import Enum

from typing import Any
import datetime
import json
import logging
import os
import sys
from pathlib import Path

LOGGER: logging.Logger = logging.getLogger(__package__)
LOGGER.setLevel(level=logging.INFO)
formatter: logging.Formatter = logging.Formatter(
    "%(asctime)s %(levelname)-8s - %(message)s"
)

logging_hdl = logging.StreamHandler()
logging_hdl.setLevel(level=logging.INFO)
logging_hdl.setFormatter(formatter)

LOGGER.addHandler(logging_hdl)

# import coloredlogs
# # coloredlogs.install(reconfigure=True, level='INFO', logger=LOGGER,fmt='%(asctime)s,%(msecs)03d %(levelname)s %(message)s')
# formatter = coloredlogs.ColoredFormatter(fmt="%(asctime)s,%(msecs)03d %(levelname)s %(message)s")

# logging_hdl_clr = logging.StreamHandler() #stream=sys.stdout)
# logging_hdl_clr.setLevel(logging.INFO)
# logging_hdl_clr.setFormatter(formatter)
# LOGGER.addHandler(logging_hdl_clr)

DEFAULT_SEND_TIMEOUT_MS = 30
DEFAULT_MAX_COM_PROC_TIMEOUT_SECS = 600 # 600 secs = 10 min

TypeJSON = dict[str, Any]

""" string output separator width """
sep_width: int = 0


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
        
class EventQueuePrinter:
    """Single event queue printer for job printing."""

    event: Event = Event()  # event for the printer that new data is available
    not_finished: bool = True
    print_strings = []
    printer_t: Thread | None = None  # printer thread

    def __init__(self) -> None:
        """start printing helper thread routine"""
        self.printer_t = Thread(target=self.coroutine)
        self.printer_t.start()

    def stop(self) -> None:
        """stop printing helper thread"""
        self.not_finished = False
        self.event.set()
        if self.printer_t is not None:
            self.printer_t.join(timeout=5)

    def coroutine(self) -> None:
        """printer thread routine, waits for data to print and/or a trigger event"""
        while self.not_finished:
            if not self.print_strings:
                self.event.wait()
            while self.print_strings and (l_str := self.print_strings.pop(0)):
                print(l_str, flush=True)

    def print(self, str) -> None:
        """add string to the printer"""
        self.print_strings.append(str)
        self.event.set()
        
@dataclass
class Range:
    min: int
    max: int
    
    def __post_init__(self) -> None:
        self.min = int(self.min)
        self.max = int(self.max)

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

    ref: Any = None

    def __init__(self, ref: Any) -> None:
        self.ref = ref


Device_config = dict


async def async_json_cache(json_data, json_file) -> tuple[dict, bool]:
    """
    If json data is given write it to cache json_file.
    Else try to read from json_file the cache.
    """

    return_json: Device_config = json_data
    cached = False
    
    user_homedir: str = ""
    try: 
        user_homedir = os.path.expanduser('~')
    except:
        # use else the dirpath where the called python script lies. 
        user_homedir = os.path.dirname(sys.argv[0])
        
    klyqa_data_path: str = user_homedir + "/.klyqa"
    
    Path(klyqa_data_path).mkdir(parents=True, exist_ok=True)
    
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
                klyqa_data_path + f"/{json_file}", mode="w"
            ) as f:
                await f.write(s)
        except Exception as e:
            LOGGER.warning(f'Could not save cache for json file "{json_file}".')
    else:
        """no json data, take cached json from disk if available"""
        try:
            async with aiofiles.open(
                klyqa_data_path + f"/{json_file}", mode="r"
            ) as f:
                s = await f.read()
            return_json = json.loads(s)
            cached: bool = True
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


def task_name() -> str:
    """Return asyncio task name."""
    task: asyncio.Task[Any] | None = asyncio.current_task()
    task_name: str = task.get_name() if task is not None else ""
    return task_name
    
def logger_debug_task(log) -> None:
    logger_debug_task(f"{log}")