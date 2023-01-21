"""General types, constants, functions"""
from __future__ import annotations
import asyncio, aiofiles
import traceback
from threading import Event, Thread
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TextIO, Type, TypeVar
import datetime
import json
import logging
import os
import sys
from pathlib import Path
import slugify

TRACE = 5

class TraceLogger(logging.Logger):
    def __init__(self, name: str, level: int =logging.NOTSET) -> None:
        super().__init__(name, level)

        logging.addLevelName(TRACE, "TRACE")

    def trace(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(TRACE):
            self._log(TRACE, msg, args, **kwargs)

logging.setLoggerClass(TraceLogger)

LOGGER: TraceLogger = TraceLogger.manager.getLogger(__package__) # type: ignore
LOGGER.setLevel(level=logging.INFO)
formatter: logging.Formatter = logging.Formatter(
    "%(asctime)s %(levelname)-8s - %(message)s"
)

logging_hdl: logging.StreamHandler[TextIO] = logging.StreamHandler()
logging_hdl.setLevel(level=logging.INFO)
logging_hdl.setFormatter(formatter)

LOGGER.addHandler(logging_hdl)

DEFAULT_SEND_TIMEOUT_MS: int = 30
DEFAULT_MAX_COM_PROC_TIMEOUT_SECS: int = 600 # 600 secs = 10 min

TypeJson = dict[str, Any]

""" string output separator width """
SEPARATION_WIDTH: int = 0

PRODUCT_URLS: dict[str, str] = {
    """TODO: Should be permalinks for urls here."""
    "@klyqa.lighting.cw-ww.gu10": "https://klyqa.de/produkte/gu10-white-strahler",
    "@klyqa.lighting.rgb-cw-ww.gu10": "https://klyqa.de/produkte/gu10-color-strahler",
    "@klyqa.lighting.cw-ww.g95": "https://www.klyqa.de/produkte/g95-vintage-lampe",
    "@klyqa.lighting.rgb-cw-ww.e14": "https://klyqa.de/produkte/e14-color-lampe",
    "@klyqa.lighting.cw-ww.e14": "https://klyqa.de/produkte/gu10-white-strahler",
    "@klyqa.lighting.rgb-cw-ww.e27": "https://www.klyqa.de/produkte/e27-color-lampe",
    "@klyqa.lighting.cw-ww.e27": "https://klyqa.de/produkte/e27-white-lampe",
    "@klyqa.cleaning.vc1": "https://klyqa.de/Alle-Produkte/Smarter-Starter",
}

SEND_LOOP_MAX_SLEEP_TIME: float = 0.05
KLYQA_CTL_VERSION: str = "1.0.17"

class DeviceType(str, Enum):
    CLEANER = "cleaner"
    LIGHTING = "lighting"

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

class CommandType(str, Enum):
    PING = "ping"
    REQUEST = "request"
    FACTORY_RESET = "factory_reset"
    ROUTINE = "routine"
    REBOOT = "reboot"
    FW_UPDATE = "fw_update"
    
@dataclass
class Command:
    """General command class."""
    _json: TypeJson = field(default_factory=lambda: {})

    def json(self) -> TypeJson:
        """Return json command."""
        return self._json
        
    def msg_str(self) -> str:
        """Return json command as string."""
        return json.dumps(self.json())

    def __str__(self) -> str:
        return self.msg_str()
    
@dataclass
class CommandTyped(Command):
    """General command class."""
    type: CommandType = CommandType.REQUEST

    def json(self) -> TypeJson:
        """Return json command."""
        return TypeJson({ "type": self.type })

class EventQueuePrinter:
    """Single event queue printer for job printing."""

    event: Event = Event()  # event for the printer that new data is available
    not_finished: bool = True
    print_strings: list[str] = []
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

    def print(self, str: str) -> None:
        """add string to the printer"""
        self.print_strings.append(str)
        self.event.set()
        
@dataclass
class Range:
    _attr_min: int
    _attr_max: int
    
    def __post_init__(self) -> None:
        self.min = int(self.min)
        self.max = int(self.max)

    @property
    def min(self) -> int:
        return self._attr_min

    @min.setter
    def min(self, min: int) -> None:
        self._attr_min = min

    @property
    def max(self) -> int:
        return self._attr_max

    @max.setter
    def max(self, max: int) -> None:
        self._attr_max = max

class RgbColor:
    """RGBColor"""

    _attr_r: int
    _attr_g: int
    _attr_b: int

    def __str__(self) -> str:
        return "[" + ",".join([str(self.r), str(self.g), str(self.b)]) + "]"
        # return get_obj_values_as_string(self)

    def __init__(self, r: int, g: int, b: int) -> None:
        self._attr_r = r
        self._attr_g = g
        self._attr_b = b

    @property
    def r(self) -> int:
        return self._attr_r

    @r.setter
    def r(self, r: int) -> None:
        self._attr_r = r

    @property
    def g(self) -> int:
        return self._attr_g

    @g.setter
    def g(self, g: int) -> None:
        self._attr_g = g

    @property
    def b(self) -> int:
        return self._attr_b

    @b.setter
    def b(self, b: int) -> None:
        self._attr_b = b

class AsyncIoLock(asyncio.Lock):
    
    def __init__(self, name: str = "") -> None:
        super().__init__()
        self.name: str = name
        self.locked_in_task: asyncio.Task[Any] | None = None
        
    async def acquire_within_task(self, timeout: int = 30, **kwargs: Any) -> bool:
        """Get asyncio lock."""
        
        try:
            LOGGER.debug(f"wait for lock... {self.name}")

            await asyncio.wait_for(self.acquire(), timeout)
            
            self.locked_in_task = asyncio.current_task()

            task_log(f"got lock... {self.name}")
            return True
        except asyncio.TimeoutError:
            LOGGER.error(f'Timeout for getting the lock for device "{self.name}"')
        except Exception:
            task_log_error(f"Error while trying to get device lock!")
            task_log_ex_trace()

        return False

    def release_within_task(self) -> None:
        if self.locked() and self.locked_in_task == asyncio.current_task():
            try:
                super().release()
                self.locked_in_task = None
                LOGGER.debug(f"got unlock... {self.name}")
            except Exception as e:
                task_log_error(f"Error while trying to unlock the device! (Probably now locked until restart)")
                task_log_ex_trace()
                raise e
                
# class AsyncIoLockTask:
#     """Async IO Lock"""

#     task: asyncio.Task | None
#     lock: asyncio.Lock
#     _instance = None

#     def __init__(self) -> None:
#         """__init__"""
#         self.lock = asyncio.Lock()
#         self.task = None

#     async def acquire(self) -> None:
#         """acquire"""
#         await self.lock.acquire()
#         self.task = asyncio.current_task()

#     def release(self) -> None:
#         """release"""
#         self.lock.release()

#     def force_unlock(self) -> bool:
#         """force_unlock"""
#         try:
#             if self.task:
#                 self.task.cancel()
#             self.lock.release()
#         except:
#             return False
#         return True

#     @classmethod
#     def instance(
#         cls: Any,
#     ) -> Any:
#         """instance"""
#         if cls._instance is None:
#             LOGGER.debug("Creating new AsyncIOLock instance")
#             cls._instance = cls.__new__(cls)
#             # Put any initialization here.
#             cls._instance.__init__()
#         return cls._instance

class ReferenceParse:
    """Reference parse for parameter in function calls."""

    _attr_ref: Any = None

    def __init__(self, ref: Any) -> None:
        self._attr_ref = ref

    @property
    def ref(self) -> Any:
        return self._attr_ref

    @ref.setter
    def ref(self, ref: Any) -> None:
        self._attr_ref = ref

Device_config = dict

ReturnTuple = TypeVar("ReturnTuple", tuple[int, str], tuple[int, dict])

NoneType: Type[None] = type(None)

async def async_json_cache(json_data: TypeJson | None, json_file: str) -> tuple[dict | None, bool]:
    """
    If json data is given write it to cache json_file.
    Else try to read from json_file the cache.
    """

    return_json: dict | None = json_data
    cached: bool = False
    
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
            s: str = ""
            sets: str | datetime.datetime | datetime.date
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
            cached = True
        except FileNotFoundError:
            LOGGER.warning(f'No cache from json file "{json_file}" available.')
        except json.decoder.JSONDecodeError:
            LOGGER.error(f'Could not read cache from json file "{json_file}"!')
        except:
            LOGGER.warning(f'Error during loading cache from json file "{json_file}".')
    return (return_json, cached)

def get_fields(object: Any) -> Any | list[str]:
    """get_fields"""
    if hasattr(object, "__dict__"):
        return object.__dict__.keys()
    else:
        return dir(object)

def get_obj_attrs_as_string(object: Any) -> str:
    """get_obj_attrs_as_string"""
    fields: Any | list[str] = get_fields(object)
    attrs: list[Any | str] = [
        a for a in fields if not a.startswith("__") and not callable(getattr(object, a))
    ]
    return ", ".join(attrs)

def get_obj_attr_values_as_string(object: Any) -> str:
    """get_obj_attr_values_as_string"""
    fields: Any | list[str] = get_fields(object)
    attrs: list[Any | str] = [
        a for a in fields if not a.startswith("__") and not callable(getattr(object, a))
    ]
    vals: list[str] = []
    for a in attrs:
        _str: str = str(getattr(object, a))
        vals.append(_str if _str else '""')
    return ", ".join(vals)

def task_name() -> str:
    """Return asyncio task name."""
    task_name: str = ""
    try:
        task: asyncio.Task[Any] | None = asyncio.current_task()
        task_name = task.get_name() if task is not None else ""
    except RuntimeError:
        # if no current async loop running skip
        return ""
    return task_name
    
def task_log(msg: str, output_func: Callable = LOGGER.debug, *args: Any, **kwargs: Any) -> None:
    """Output task name and logging string."""
    task_name_str: str = task_name()
    output_func(f"{task_name_str} - {msg}" if task_name_str else f"{msg}", *args, **kwargs)
    
def task_log_debug(msg: str, *args: Any, **kwargs: Any) -> None:
    """Output debug message with task name."""
    task_log(msg, LOGGER.debug, *args, **kwargs)
    
def task_log_error(msg: str, *args: Any, **kwargs: Any) -> None:
    """Output error message with task name."""
    task_log(msg, LOGGER.error, *args, **kwargs)
    
def task_log_ex_trace() -> None:
    """Log exception trace within task."""
    task_log(traceback.format_exc(), LOGGER.trace)
    
def format_uid(text: str, **kwargs: Any) -> Any:
    return slugify.slugify(text)
