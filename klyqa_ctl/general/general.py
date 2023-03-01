"""General types, constants, functions"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import datetime
from enum import Enum
import json
import logging
import os
from pathlib import Path
import sys
from threading import Event, Thread
import traceback
from typing import Any, Awaitable, Callable, Final, TextIO, Type, TypeVar

import aiofiles
import slugify

TRACE: Final = 5


DEFAULT_SEND_TIMEOUT_MS: Final[int] = 30
DEFAULT_MAX_COM_PROC_TIMEOUT_SECS: Final[int] = 120  # 2mins

TypeJson = dict[str, Any]

""" string output separator width """
SEPARATION_WIDTH: int = 0

PROD_HOST: Final = "https://app-api.prod.qconnex.io"

PRODUCT_URLS: dict[str, str] = {
    """TODO: Should be permalinks for urls here."""
    "@klyqa.lighting.cw-ww.gu10": (
        "https://klyqa.de/produkte/gu10-white-strahler"
    ),
    "@klyqa.lighting.rgb-cw-ww.gu10": (
        "https://klyqa.de/produkte/gu10-color-strahler"
    ),
    "@klyqa.lighting.cw-ww.g95": (
        "https://www.klyqa.de/produkte/g95-vintage-lampe"
    ),
    "@klyqa.lighting.rgb-cw-ww.e14": (
        "https://klyqa.de/produkte/e14-color-lampe"
    ),
    "@klyqa.lighting.cw-ww.e14": (
        "https://klyqa.de/produkte/gu10-white-strahler"
    ),
    "@klyqa.lighting.rgb-cw-ww.e27": (
        "https://www.klyqa.de/produkte/e27-color-lampe"
    ),
    "@klyqa.lighting.cw-ww.e27": "https://klyqa.de/produkte/e27-white-lampe",
    "@klyqa.cleaning.vc1": "https://klyqa.de/Alle-Produkte/Smarter-Starter",
}

SEND_LOOP_MAX_SLEEP_TIME: Final[float] = 0.005
MAX_SOCKET_SEND_TIMEOUT_SECS: Final[int] = 1


class DeviceType(str, Enum):
    """Device types."""

    CLEANER = "cleaner"
    LIGHTING = "lighting"


AES_KEY_DEV: Final[str] = "00112233445566778899AABBCCDDEEFF"

AES_KEY_DEV_BYTES: Final[bytes] = bytes.fromhex(AES_KEY_DEV)

QCX_SYN: Final[bytes] = "QCX-SYN".encode("utf-8")
QCX_DSYN: Final[bytes] = "QCX-DSYN".encode("utf-8")
QCX_ACK: Final[bytes] = "QCX-ACK".encode("utf-8")

ACC_SETS_REQUEST_TIMEDELTA: Final = 60


class CommandType(str, Enum):
    """Send/request command types."""

    PING = "ping"
    REQUEST = "request"
    FACTORY_RESET = "factory_reset"
    ROUTINE = "routine"
    REBOOT = "reboot"
    FW_UPDATE = "fw_update"


@dataclass
class Command:
    """General command class.
    Used as default cloud command class as well.
    (Normal cloud commands in json are the same as local commands)

    Private or protected attributes shouldn't be printed into the json
    command message and are just for logical control usage."""

    _json: TypeJson = field(default_factory=lambda: {})

    def json(self) -> TypeJson:
        """Return json command."""

        return self._json

    def cloud(self) -> TypeJson:
        """Return json command for cloud."""

        return self.json()

    def msg_str(self) -> str:
        """Return json command as string."""

        return json.dumps(self.json())

    def __str__(self) -> str:
        return self.msg_str()


class CloudStateCommand(Command):
    """Cloud state command class."""

    def cloud(self) -> TypeJson:
        return {"payload": self.json()}


@dataclass
class CommandTyped(Command):
    """General command class."""

    type: str = CommandType.REQUEST.value

    def json(self) -> TypeJson:
        """Return json command."""
        # return TypeJson(
        #     {
        #         k: v
        #         for k, v in self.__dict__.items()
        #         if not k.startswith("_") and v != "" and v is not None
        #     }
        # )  # json.dumps(self.__dict__)
        return TypeJson({"type": self.type} | super().json())


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
        """printer thread routine, waits for data to print and/or a
        trigger event"""

        while self.not_finished:
            if not self.print_strings:
                self.event.wait()
            while self.print_strings and (l_str := self.print_strings.pop(0)):
                print(l_str, flush=True)

    def print(self, val: str) -> None:
        """add string to the printer"""

        self.print_strings.append(val)
        self.event.set()


@dataclass
class Range:
    """Range of values class."""

    _attr_min: int
    _attr_max: int

    def __post_init__(self) -> None:
        self.min = int(self.min)
        self.max = int(self.max)

    @property
    def min(self) -> int:
        """Minimum getter."""

        return self._attr_min

    @min.setter
    def min(self, val: int) -> None:
        self._attr_min = val

    @property
    def max(self) -> int:
        """Maximum getter."""

        return self._attr_max

    @max.setter
    def max(self, val: int) -> None:
        self._attr_max = val


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
        """Red color part getter."""

        return self._attr_r

    @r.setter
    def r(self, red: int) -> None:
        self._attr_r = red

    @property
    def g(self) -> int:
        """Green color part getter."""

        return self._attr_g

    @g.setter
    def g(self, green: int) -> None:
        self._attr_g = green

    @property
    def b(self) -> int:
        """Blue color part getter."""

        return self._attr_b

    @b.setter
    def b(self, blue: int) -> None:
        self._attr_b = blue


class AsyncIoLock(asyncio.Lock):
    """AsyncIo lock with remembering of the task within it was locked."""

    def __init__(self, name: str = "") -> None:
        super().__init__()
        self.name: str = name
        self.locked_in_task: asyncio.Task[Any] | None = None

    async def acquire_within_task(
        self, timeout: int = 30, **kwargs: Any
    ) -> bool:
        """Get asyncio lock and remember the task within it was locked."""

        try:
            task_log_trace(f"wait for lock... {self.name}")

            await asyncio.wait_for(self.acquire(), timeout)

            self.locked_in_task = asyncio.current_task()

            task_log_trace(f"got lock... {self.name}")
            return True
        except asyncio.TimeoutError:
            LOGGER.error(
                'Timeout for getting the lock for device "%s"', self.name
            )

        return False

    def release_within_task(self) -> None:
        """Release the lock from inside the task where the lock was locked."""

        if self.locked() and self.locked_in_task == asyncio.current_task():
            try:
                super().release()
                self.locked_in_task = None
                task_log_trace(f"got unlock... {self.name}")
            except Exception as exception:
                task_log_error(
                    "Error while trying to unlock the device! (Probably now"
                    " locked until restart)"
                )
                task_log_trace_ex()
                raise exception


def task_name() -> str:
    """Return asyncio task name."""

    name: str = ""
    try:
        task: asyncio.Task[Any] | None = asyncio.current_task()
        name = task.get_name() if task is not None else ""
    except RuntimeError:
        # if no current async loop running skip
        return ""
    return name


DeviceConfig = dict

ReturnTuple = TypeVar("ReturnTuple", tuple[int, str], tuple[int, dict])

NoneType: Type[None] = type(None)


async def async_json_cache(
    json_data: TypeJson | None, json_file: str
) -> tuple[dict | None, bool]:
    """
    If json data is given write it to cache json_file.
    Else try to read from json_file the cache.
    """

    return_json: dict | None = json_data
    cached: bool = False

    user_homedir: str = ""

    user_homedir = os.path.expanduser("~")
    if not user_homedir:
        user_homedir = os.path.dirname(sys.argv[0])

    klyqa_data_path: str = user_homedir + "/.klyqa"

    Path(klyqa_data_path).mkdir(parents=True, exist_ok=True)

    if json_data:
        # Save the json for offline cache in dirpath where the called script
        # resides ids: { sets }.

        return_json = json_data
        try:
            data: str = ""
            sets: str | datetime.datetime | datetime.date
            for key, sets in json_data.items():
                if isinstance(sets, (datetime.datetime, datetime.date)):
                    sets = sets.isoformat()
                data = data + '"' + key + '": ' + json.dumps(sets) + ", "
            data = "{" + data[:-2] + "}"
            async with aiofiles.open(
                klyqa_data_path + f"/{json_file}", mode="w"
            ) as f:
                await f.write(data)
        except IOError:
            LOGGER.warning(
                'Could not save cache for json file "%s".', json_file
            )
    else:
        # No json data, take cached json from disk if available.

        k_ctl_main_path_parts: list[str] = list(
            Path(__file__).absolute().parts[:-2]
        )
        dc_default_path: str = (
            str(Path(*k_ctl_main_path_parts).absolute()) + f"/{json_file}"
        )
        for cache_path in [klyqa_data_path + f"/{json_file}", dc_default_path]:

            task_log_trace(f"Try read cache file {cache_path}.")
            try:
                async with aiofiles.open(cache_path, mode="r") as f:
                    data = await f.read()
                    return_json = json.loads(data)
                    cached = True
                    task_log_trace(f"Read cache file {cache_path} succeeded.")
                    break
            except FileNotFoundError:
                LOGGER.warning(
                    'No cache from json file "%s" available.', cache_path
                )
            except json.decoder.JSONDecodeError:
                LOGGER.error(
                    'Could not read cache from json file "%s"!', cache_path
                )
            except Exception as exception:
                LOGGER.warning(
                    'Error during loading cache from json file "%s".',
                    cache_path,
                )
                raise exception
    return (return_json, cached)


def get_fields(obj: Any) -> Any | list[str]:
    """Get attributes from object."""

    if hasattr(obj, "__dict__"):
        return obj.__dict__.keys()
    else:
        return dir(obj)


def get_obj_attrs_as_string(obj: Any) -> str:
    """Get all attributes names from the object besides private ones."""

    fields: Any | list[str] = get_fields(obj)
    attrs: list[Any | str] = [
        a
        for a in fields
        if not a.startswith("__") and not callable(getattr(obj, a))
    ]
    return ", ".join(attrs)


def get_obj_attr_values_as_string(obj: Any) -> str:
    """Get all attribute values from the object besides private ones."""

    fields: Any | list[str] = get_fields(obj)
    attrs: list[Any | str] = [
        a
        for a in fields
        if not a.startswith("__") and not callable(getattr(obj, a))
    ]
    vals: list[str] = []
    for a in attrs:
        _str: str = str(getattr(obj, a))
        vals.append(_str if _str else '""')
    return ", ".join(vals)


def format_uid(text: str, **kwargs: Any) -> Any:
    """Format unit ids to on single format."""

    return slugify.slugify(text)


def aes_key_to_bytes(key: str) -> bytes:
    """Translate hexadecimal AES key into bytes array."""

    return bytes.fromhex(key)


class TraceLogger(logging.Logger):
    """Trace logger level class for the logging framework."""

    def __init__(self, name: str, level: int = logging.NOTSET) -> None:
        super().__init__(name, level)

        logging.addLevelName(TRACE, "TRACE")

    def trace(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Print message in trace logging level."""

        if self.isEnabledFor(TRACE):
            self._log(TRACE, msg, args, **kwargs)


logging.setLoggerClass(TraceLogger)
LOGGER: logging.Logger = logging.getLogger(__package__)


def set_logger(
    # pylint: disable-next=used-prior-global-declaration
    logger: logging.Logger = LOGGER,
    level: int = logging.INFO,
) -> None:
    """Set global logger object and initialize."""

    global LOGGER  # pylint: disable=global-statement
    LOGGER = logger
    LOGGER.setLevel(level=level)

    info_formatter: logging.Formatter = logging.Formatter("%(message)s")

    logging_hdl: logging.StreamHandler[TextIO] = logging.StreamHandler(
        stream=sys.stdout
    )
    logging_hdl.setLevel(level=level)
    logging_hdl.setFormatter(fmt=info_formatter)

    LOGGER.addHandler(logging_hdl)


LOGGER_DBG: TraceLogger = TraceLogger.manager.getLogger(
    "klyqa_ctl_trace"
)  # type: ignore[assignment]
LOGGER_DBG.disabled = True


def set_debug_logger(
    # pylint: disable-next=used-prior-global-declaration
    logger: TraceLogger = LOGGER_DBG,
    level: int = logging.DEBUG,
) -> None:
    """Stream logging handler to stderr pipe."""

    global LOGGER_DBG  # pylint: disable=global-statement
    LOGGER_DBG = logger
    trace_log_hdl: logging.StreamHandler[TextIO] = logging.StreamHandler(
        stream=sys.stderr
    )
    debug_formatter: logging.Formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s - %(message)s"
    )
    trace_log_hdl.setLevel(level)
    trace_log_hdl.setFormatter(debug_formatter)

    LOGGER_DBG.addHandler(trace_log_hdl)
    LOGGER_DBG.setLevel(level)
    LOGGER_DBG.disabled = False


def task_log(
    msg: str, output_func: Callable = LOGGER.info, *args: Any, **kwargs: Any
) -> None:
    """Output task name and logging string."""

    task_name_str: str = (
        task_name() if LOGGER_DBG.getEffectiveLevel() <= logging.DEBUG else ""
    )
    output_func(
        f"{task_name_str} - {msg}" if task_name_str else f"{msg}",
        *args,
        **kwargs,
    )


def task_log_debug(msg: str, *args: Any, **kwargs: Any) -> None:
    """Output debug message with task name."""

    task_log(msg, LOGGER_DBG.debug, *args, **kwargs)


def task_log_trace(msg: str, *args: Any, **kwargs: Any) -> None:
    """Output debug message with task name."""

    task_log(msg, LOGGER_DBG.trace, *args, **kwargs)


def task_log_error(msg: str, *args: Any, **kwargs: Any) -> None:
    """Output error message with task name."""

    task_log(msg, LOGGER_DBG.trace, *args, **kwargs)


def task_log_trace_ex() -> None:
    """Log exception trace within task."""

    task_log_trace(traceback.format_exc())


def get_asyncio_loop() -> asyncio.AbstractEventLoop:
    """Get asyncio loop."""

    loop: asyncio.AbstractEventLoop
    # Within a coroutine, simply use `asyncio.get_running_loop()`, since the
    # coroutine wouldn't be ableto execute in the first place without a
    # running event loop present.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # depending on context, you might debug or warning log that a running
        # event loop wasn't found
        loop = asyncio.get_event_loop()

    return loop


class ShutDownHandler:
    """Shut down handler."""

    def __init__(self) -> None:
        self._shutdown_handler: list[Callable[[], Awaitable[None]]] = []

    async def shutdown(self) -> None:
        """Call all shuts down handler."""

        for awaitable in self._shutdown_handler:
            await awaitable()


@dataclass
class Address:
    """Class for IP address with port."""

    ip: str = ""
    port: int = -1


def enum_index(key: str, enum: Type[Enum]) -> Any:
    """Search string key name in enumeration and return the value."""

    return [i.value for i in enum if i.name == key][0]
