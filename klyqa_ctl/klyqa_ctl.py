#!/usr/bin/env python3
"""Klyqa control client."""

###################################################################
#
# Interactive Klyqa Control commandline client
#
# Company: QConnex GmbH / Klyqa
# Author: Frederick Stallmeyer
#
# E-Mail: frederick.stallmeyer@gmx.de
#
# nice to haves:
#   -   list cloud connected devices in discovery.
#   -   offer for selected devices possible commands and arguments in interactive
#       mode based on their device profile
#   -   Implementation for the different device config profile versions and
#       check on send.
#
# BUGS:
#  - vc1 interactive command selection support.
#
###################################################################

from __future__ import annotations
from dataclasses import dataclass
import socket
import sys
import json
import datetime
import argparse
import select
import logging
import time
from typing import TypeVar, Any, Type

from .general.parameters import get_description_parser


NoneType: Type[None] = type(None)
import requests, uuid, json
import os.path
from threading import Thread
from collections import ChainMap
from threading import Event
from enum import Enum
import asyncio, aiofiles
import functools, traceback
from asyncio.exceptions import CancelledError, TimeoutError
from collections.abc import Callable


from .devices.device import *
from .devices.light import *
from .devices.vacuum import *
from .general.message import *
from .general.general import *
from .general.connections import *

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
except:
    from Crypto.Cipher import AES  # provided by pycryptodome

from typing import TypeVar


s: str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]

print(f"{s} start")


tcp_udp_port_lock: AsyncIOLock = AsyncIOLock.instance()


Device_TCP_return = Enum(
    "Device_TCP_return",
    "sent answered wrong_uid no_uid_device wrong_aes tcp_error unknown_error timeout nothing_done sent_error no_message_to_send device_lock_timeout err_local_iv missing_aes_key response_error",
)


ReturnTuple = TypeVar("ReturnTuple", tuple[int, str], tuple[int, dict])


AES_KEYs: dict[str, bytes] = {}

S = TypeVar("S", argparse.ArgumentParser, type(None))


class EventQueuePrinter:
    """Single event queue printer for job printing."""

    event: Event = Event()
    """event for the printer that new data is available"""
    not_finished: bool = True
    print_strings = []
    printer_t: Thread | None = None

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


class Klyqa_account:
    """

    Klyqa account
    * rest access token
    * devices
    * account settings

    """

    host: str
    access_token: str
    username: str
    password: str
    username_cached: bool

    devices: dict[str, KlyqaDevice]

    acc_settings: TypeJSON | None
    acc_settings_cached: bool

    __acc_settings_lock: asyncio.Lock
    _settings_loaded_ts: datetime.datetime | None

    __send_loop_sleep: asyncio.Task | None
    __tasks_done: list[tuple[asyncio.Task, datetime.datetime, datetime.datetime]]
    __tasks_undone: list[tuple[asyncio.Task, datetime.datetime]]
    __read_tcp_task: asyncio.Task | None
    message_queue: dict[str, list[Message]]
    message_queue_new: list[tuple]
    search_and_send_loop_task: asyncio.Task | None

    # Set of current accepted connections to an IP. One connection is most of the time
    # enough to send all messages for that device behind that connection (in the aes send message method).
    # If connection is currently finishing due to sent messages and no messages left for that device and a new
    # message appears in the queue, send a new broadcast and establish a new connection.
    #
    current_addr_connections: set[str] = set()

    def __init__(
        self, data_communicator: Data_communicator, username="", password="", host=""
    ) -> None:
        """Initialize the account with the login data, tcp, udp datacommunicator and tcp
        communication tasks."""
        self.username = username
        self.password = password
        self.devices = {}
        self.acc_settings = {}
        self.access_token: str = ""
        self.host = PROD_HOST if not host else host
        self.username_cached = False
        self.acc_settings_cached = False
        self.__acc_settings_lock = asyncio.Lock()
        self._settings_loaded_ts = None
        self.__send_loop_sleep = None
        self.__tasks_done = []
        self.__tasks_undone = []
        self.message_queue = {}
        self.message_queue_new: list[tuple] = []
        self.search_and_send_loop_task = None
        self.__read_tcp_task = None
        self.data_communicator: Data_communicator = data_communicator
        self.search_and_send_loop_task_end_now = False

    async def device_handle_local_tcp(
        self, device: KlyqaDevice | None, connection: LocalConnection
    ):
        """Handle the incoming tcp connection to the device."""
        return_state = -1
        response = ""

        try:
            # LOGGER.debug(f"TCP layer connected {connection.address['ip']}")

            r_device: RefParse = RefParse(device)
            msg_sent: Message | None = None
            r_msg: RefParse = RefParse(msg_sent)
            task: asyncio.Task[Any] | None = asyncio.current_task()

            if task is not None:
                LOGGER.debug(
                    f"{task.get_name()} - started tcp device {connection.address['ip']} "
                )
            try:
                return_state = await self.aes_handshake_and_send_msgs(
                    r_device, r_msg, connection
                )
                device = r_device.ref
                msg_sent = r_msg.ref
            except CancelledError as e:
                LOGGER.error(
                    f"Cancelled local send because send-timeout send_timeout hitted {connection.address['ip']}, "
                    + (device.u_id if device and device.u_id else "")
                    + "."
                )
            except Exception as e:
                LOGGER.debug(f"{traceback.format_exc()}")
            finally:
                LOGGER.debug(
                    f"finished tcp device {connection.address['ip']}, return_state: {return_state}"
                )

                if msg_sent and not msg_sent.callback is None and device is not None:
                    await msg_sent.callback(msg_sent, device.u_id)
                    if device is not None:
                        LOGGER.debug(
                            f"device {device.u_id} answered msg {msg_sent.msg_queue}"
                        )

                # if not device or (device and not device.u_id in self.message_queue or not self.message_queue[device.u_id]):
                #     try:
                # LOGGER.debug(f"no more messages to sent for device {device.u_id}, close tcp tunnel.")
                if connection.socket is not None:
                    connection.socket.shutdown(socket.SHUT_RDWR)
                    connection.socket.close()
                    connection.socket = None
                self.current_addr_connections.remove(str(connection.address["ip"]))
                LOGGER.debug(f"tcp closed for device.u_id.")
                # except Exception as e:
                #     pass

                unit_id: str = (
                    f" Unit-ID: {device.u_id}" if device and device.u_id else ""
                )

                if return_state == 0:
                    """no error"""

                    def dict_values_to_list(d: dict) -> list[str]:
                        r: list[str] = []
                        for i in d.values():
                            if isinstance(i, dict):
                                i = dict_values_to_list(i)
                            r.append(str(i))
                        return r

                    # if not args.selectDevice:
                    #     name = f' "{device.get_name()}"' if device.get_name() else ""
                    #     LOGGER.info(
                    #         f"device{name} response (local network): "
                    #         + str(json.dumps(response, sort_keys=True, indent=4))
                    #     )

                if device and device.u_id in self.devices:
                    device_b: KlyqaDevice = self.devices[device.u_id]
                    if device_b._use_thread == asyncio.current_task():
                        try:
                            if device_b._use_lock is not None:
                                device_b._use_lock.release()
                            device_b._use_thread = None
                        except:
                            pass

                elif return_state == 1:
                    LOGGER.error(
                        f"Unknown error during send (and handshake) with device {unit_id}."
                    )
                elif return_state == 2:
                    pass
                    # LOGGER.debug(f"Wrong device unit id.{unit_id}")
                elif return_state == 3:
                    LOGGER.debug(
                        f"End of tcp stream. ({connection.address['ip']}:{connection.address['port']})"
                    )

        except CancelledError as e:
            LOGGER.error(f"Device tcp task cancelled.")
        except Exception as e:
            LOGGER.debug(f"{e}")
            pass
        return return_state
        pass

    async def search_and_send_to_device(
        self, timeout_ms=DEFAULT_SEND_TIMEOUT_MS
    ) -> bool:
        """Send broadcast and make tasks for incoming tcp connections."""
        loop = asyncio.get_event_loop()

        try:
            if not self.data_communicator.tcp or not self.data_communicator.udp:
                await self.data_communicator.bind_ports()
            while not self.search_and_send_loop_task_end_now:  # self.tcp:
                if not self.data_communicator.tcp or not self.data_communicator.udp:
                    break
                # for debug cursor jump:
                a = False
                if a:
                    break

                # while self.message_queue_new:
                #     """add start timestamp to new messages"""
                #     send_msg, target_device_uid, args, callback, time_to_live_secs, started = self.message_queue_new.pop(0)
                #     if not send_msg:
                #         LOGGER.error(f"No message queue to send in message to {target_device_uid}!")
                #         await callback(None, target_device_uid)
                #         continue

                #     msg = Message(datetime.datetime.now(), send_msg, args,
                #     target_uid = target_device_uid, callback = callback, time_to_live_secs = time_to_live_secs)

                #     if not await msg.check_msg_ttl():
                #         continue

                #     LOGGER.debug(f"new message {msg.msg_counter} target {target_device_uid} {send_msg}")

                #     self.message_queue.setdefault(target_device_uid, []).append(msg)

                if self.message_queue:

                    read_broadcast_response = True
                    try:
                        LOGGER.debug("Broadcasting QCX-SYN Burst")
                        self.data_communicator.udp.sendto(
                            "QCX-SYN".encode("utf-8"), ("255.255.255.255", 2222)
                        )

                    except Exception as exception:
                        LOGGER.debug("Broadcasting QCX-SYN Burst Exception")
                        LOGGER.debug(f"{traceback.format_exc()}")
                        read_broadcast_response = False
                        if not await self.data_communicator.bind_ports():
                            LOGGER.error("Error binding ports udp 2222 and tcp 3333.")
                            return False

                    if not read_broadcast_response:
                        try:
                            LOGGER.debug(f"sleep task create (broadcasts)..")
                            self.__send_loop_sleep = loop.create_task(
                                asyncio.sleep(
                                    SEND_LOOP_MAX_SLEEP_TIME
                                    if (
                                        len(self.message_queue) > 0
                                        or len(self.message_queue_new) > 0
                                    )
                                    else 1000000000
                                )
                            )

                            LOGGER.debug(f"sleep task wait..")
                            done, pending = await asyncio.wait([self.__send_loop_sleep])

                            LOGGER.debug(f"sleep task done..")
                        except CancelledError as e:
                            LOGGER.debug(f"sleep cancelled1.")
                        except Exception as e:
                            LOGGER.debug(f"{e}")
                            pass
                        pass

                    while read_broadcast_response:

                        timeout_read: float = 1.9
                        LOGGER.debug("Read again tcp port..")

                        async def read_tcp_task() -> tuple[
                            list[Any], list[Any], list[Any]
                        ] | None:
                            try:
                                return await loop.run_in_executor(
                                    None,
                                    select.select,
                                    [self.data_communicator.tcp],
                                    [],
                                    [],
                                    timeout_read,
                                )
                            except CancelledError as e:
                                LOGGER.debug("cancelled tcp reading.")
                            except Exception as e:
                                LOGGER.error(f"{traceback.format_exc()}")
                                if not await self.data_communicator.bind_ports():
                                    LOGGER.error(
                                        "Error binding ports udp 2222 and tcp 3333."
                                    )

                        self.__read_tcp_task = asyncio.create_task(read_tcp_task())

                        LOGGER.debug("Started tcp reading..")
                        try:
                            await asyncio.wait_for(self.__read_tcp_task, timeout=1.0)
                        except Exception as e:
                            LOGGER.debug(
                                f"Socket-Timeout for incoming tcp connections."
                            )

                            if not await self.data_communicator.bind_ports():
                                LOGGER.error(
                                    "Error binding ports udp 2222 and tcp 3333."
                                )

                        result: tuple[list[Any], list[Any], list[Any]] | None = (
                            self.__read_tcp_task.result()
                            if self.__read_tcp_task
                            else None
                        )
                        if (
                            not result
                            or not isinstance(result, tuple)
                            or not len(result) == 3
                        ):
                            LOGGER.debug("no tcp read result. break")
                            break
                        readable: list[Any]
                        readable, _, _ = result if result else ([], [], [])

                        LOGGER.debug("Reading tcp port done..")

                        if not self.data_communicator.tcp in readable:
                            break
                        else:
                            device: KlyqaDevice = KlyqaDevice()
                            connection: LocalConnection = LocalConnection()
                            (
                                connection.socket,
                                addr,
                            ) = self.data_communicator.tcp.accept()
                            if not addr[0] in self.current_addr_connections:
                                self.current_addr_connections.add(addr[0])
                                connection.address["ip"] = addr[0]
                                connection.address["port"] = addr[1]

                                new_task = loop.create_task(
                                    self.device_handle_local_tcp(device, connection)
                                )

                                # for test:
                                await asyncio.wait([new_task], timeout=0.00000001)
                                # timeout task for the device tcp task
                                loop.create_task(
                                    asyncio.wait_for(
                                        new_task, timeout=(timeout_ms / 1000)
                                    )
                                )

                                LOGGER.debug(
                                    f"Address {connection.address['ip']} process task created."
                                )
                                self.__tasks_undone.append(
                                    (new_task, datetime.datetime.now())
                                )  # device.u_id
                            else:
                                LOGGER.debug(f"{addr[0]} already in connection.")

                    try:
                        to_del = []
                        """check message queue for ttls"""
                        for uid, msgs in self.message_queue.items():
                            for msg in msgs:
                                if not await msg.check_msg_ttl():
                                    msgs.remove(msg)
                                if not self.message_queue[uid]:
                                    # del self.message_queue[uid]
                                    to_del.append(uid)
                                    break
                        for uid in to_del:
                            del self.message_queue[uid]
                    except Exception as e:
                        LOGGER.debug(f"{traceback.format_exc()}")
                        pass

                try:
                    tasks_undone_new = []
                    for task, started in self.__tasks_undone:
                        if task.done():
                            self.__tasks_done.append(
                                (task, started, datetime.datetime.now())
                            )
                            e = task.exception()
                            if e:
                                LOGGER.debug(
                                    f"Exception error in {task.get_coro()}: {e}"
                                )
                        else:
                            if datetime.datetime.now() - started > datetime.timedelta(
                                milliseconds=int(timeout_ms * 1000)
                            ):
                                task.cancel()
                            tasks_undone_new.append((task, started))
                    self.__tasks_undone = tasks_undone_new

                except CancelledError as e:
                    LOGGER.debug(f"__tasks_undone check cancelled.")
                except Exception as e:
                    LOGGER.debug(f"{e}")
                    pass
                pass

                if not len(self.message_queue_new) and not len(self.message_queue):
                    try:
                        LOGGER.debug(f"sleep task create2 (searchandsendloop)..")
                        self.__send_loop_sleep = loop.create_task(
                            asyncio.sleep(
                                SEND_LOOP_MAX_SLEEP_TIME
                                if len(self.message_queue) > 0
                                else 1000000000
                            )
                        )
                        LOGGER.debug(f"sleep task wait..")
                        done, pending = await asyncio.wait([self.__send_loop_sleep])
                        LOGGER.debug(f"sleep task done..")
                    except CancelledError as e:
                        LOGGER.debug(f"sleep cancelled2.")
                    except Exception as e:
                        LOGGER.debug(f"{e}")
                        pass
                pass

        except CancelledError as e:
            LOGGER.debug(f"search and send to device loop cancelled.")
            self.message_queue = {}
            self.message_queue_now = {}
            for task, started in self.__tasks_undone:
                task.cancel()
        except Exception as e:
            LOGGER.debug("Exception on send and search loop. Stop loop.")
            LOGGER.debug(f"{traceback.format_exc()}")
            return False
        return True

    async def search_and_send_loop_task_stop(self):
        while (
            self.search_and_send_loop_task and not self.search_and_send_loop_task.done()
        ):
            LOGGER.debug("stop send and search loop.")
            if self.search_and_send_loop_task:
                self.search_and_send_loop_task_end_now = True
                self.search_and_send_loop_task.cancel()
            try:
                LOGGER.debug("wait for send and search loop to end.")
                await asyncio.wait_for(self.search_and_send_loop_task, timeout=0.1)
                LOGGER.debug("wait end for send and search loop.")
            except Exception as e:
                LOGGER.debug(f"{traceback.format_exc()}")
            LOGGER.debug("wait end for send and search loop.")
        pass

    def search_and_send_loop_task_alive(self) -> None:

        loop = asyncio.get_event_loop()

        if not self.search_and_send_loop_task or self.search_and_send_loop_task.done():
            LOGGER.debug("search and send loop task created.")
            self.search_and_send_loop_task = asyncio.create_task(
                self.search_and_send_to_device()
            )
        try:
            if self.__send_loop_sleep is not None:
                self.__send_loop_sleep.cancel()
        except:
            pass

    async def set_send_message(
        self,
        send_msg,
        target_device_uid,
        args,
        callback=None,
        time_to_live_secs: int = -1,
        started=datetime.datetime.now(),
    ) -> bool:

        loop = asyncio.get_event_loop()
        # self.message_queue_new.append((send_msg, target_device_uid, args, callback, time_to_live_secs, started))

        if not send_msg:
            LOGGER.error(f"No message queue to send in message to {target_device_uid}!")
            await callback(None, target_device_uid)
            return False

        msg: Message = Message(
            datetime.datetime.now(),
            send_msg,
            args,
            target_uid=target_device_uid,
            callback=callback,
            time_to_live_secs=time_to_live_secs,
        )

        if not await msg.check_msg_ttl():
            return False

        LOGGER.debug(
            f"new message {msg.msg_counter} target {target_device_uid} {send_msg}"
        )

        self.message_queue.setdefault(target_device_uid, []).append(msg)

        if self.__read_tcp_task:
            self.__read_tcp_task.cancel()
        self.search_and_send_loop_task_alive()
        return True

    async def load_username_cache(self) -> None:
        acc_settings_cache, cached = await async_json_cache(
            None, "last.acc_settings.cache.json"
        )

        self.username_cached = cached

        if cached:
            LOGGER.info(f"No username or no password given using cache.")
            if not acc_settings_cache or (
                self.username and list(acc_settings_cache.keys())[0] != self.username
            ):
                e = f"Account settings are from another account than {self.username}."
                LOGGER.error(e)
                raise ValueError(e)
            else:
                try:
                    self.username = list(acc_settings_cache.keys())[0]
                    self.password = acc_settings_cache[self.username]["password"]
                    e = f"Using cache account settings from account {self.username}."
                    LOGGER.info(e)
                except:
                    e = f"Could not load cached account settings."
                    LOGGER.error(e)
                    raise ValueError(e)
        else:
            e = f"Could not load cached account settings."
            LOGGER.error(e)
            raise ValueError(e)

    async def login(self, print_onboarded_devices=False) -> bool:
        """Login on klyqa account, get account settings, get onboarded device profiles,
        print all devices if parameter set."""
        global device_configs
        loop = asyncio.get_event_loop()

        acc_settings_cache = {}
        if not self.username or not self.password:
            try:
                async with aiofiles.open(
                    os.path.dirname(sys.argv[0]) + f"/last_username", mode="r"
                ) as f:
                    self.username = str(await f.readline()).strip()
            except:
                return False

        if self.username is not None and self.password is not None:
            login_response: requests.Response | None = None
            try:
                login_data = {"email": self.username, "password": self.password}

                login_response = await loop.run_in_executor(
                    None,
                    functools.partial(
                        requests.post,
                        self.host + "/auth/login",
                        json=login_data,
                        timeout=10,
                    ),
                )

                if not login_response or (
                    login_response.status_code != 200
                    and login_response.status_code != 201
                ):
                    LOGGER.error(
                        str(login_response.status_code)
                        + ", "
                        + str(login_response.text)
                    )
                    raise Exception(login_response.text)
                login_json = json.loads(login_response.text)
                self.access_token = login_json.get("accessToken")
                # self.acc_settings = await loop.run_in_executor(
                #     None, functools.partial(self.request, "settings", timeout=30)
                # )
                self.acc_settings = await self.request("settings", timeout=30)

            except Exception as e:
                LOGGER.error(
                    f"Error during login. Try reading account settings for account {self.username} from cache."
                )
                try:
                    acc_settings_cache, cached = await async_json_cache(
                        None, f"{self.username}.acc_settings.cache.json"
                    )
                except:
                    return False
                if not cached:
                    return False
                else:
                    self.acc_settings = acc_settings_cache

            if not self.acc_settings:
                return False

            try:
                acc_settings_cache = {
                    **self.acc_settings,
                    **{
                        "time_cached": datetime.datetime.now(),
                        "password": self.password,
                    },
                }

                """save current account settings in cache"""
                await async_json_cache(
                    acc_settings_cache, f"{self.username}.acc_settings.cache.json"
                )

                async with aiofiles.open(
                    os.path.dirname(sys.argv[0]) + f"/last_username", mode="w"
                ) as f:
                    await f.write(self.username)

            except Exception as e:
                pass

            try:
                klyqa_acc_string = (
                    "Klyqa account " + self.username + ". Onboarded devices:"
                )
                sep_width = len(klyqa_acc_string)

                if print_onboarded_devices:
                    print(sep_width * "-")
                    print(klyqa_acc_string)
                    print(sep_width * "-")

                queue_printer: EventQueuePrinter = EventQueuePrinter()

                def device_request_and_print(device_sets):
                    state_str = (
                        f'Name: "{device_sets["name"]}"'
                        + f'\tAES-KEY: {device_sets["aesKey"]}'
                        + f'\tUnit-ID: {device_sets["localDeviceId"]}'
                        + f'\tCloud-ID: {device_sets["cloudDeviceId"]}'
                        + f'\tType: {device_sets["productId"]}'
                    )
                    cloud_state = None

                    device: KlyqaDevice
                    if device_sets["productId"].find(".lighting") > -1:
                        device = KlyqaBulb()
                    elif device_sets["productId"].find(".cleaning") > -1:
                        device = KlyqaVC()
                    else:
                        return
                    device.u_id = format_uid(device_sets["localDeviceId"])
                    device.acc_sets = device_sets

                    self.devices[format_uid(device_sets["localDeviceId"])] = device

                    async def req():
                        try:
                            ret = await self.request(
                                f'device/{device_sets["cloudDeviceId"]}/state',
                                timeout=30,
                            )
                            return ret
                        except Exception as e:
                            return None

                    try:
                        cloud_state = asyncio.run(req())
                        if cloud_state:
                            if "connected" in cloud_state:
                                state_str = (
                                    state_str
                                    + f'\tCloud-Connected: {cloud_state["connected"]}'
                                )
                            device.cloud.connected = cloud_state["connected"]

                            device.save_device_message(
                                {**cloud_state, **{"type": "status"}}
                            )
                        else:
                            raise
                    except:
                        err = f'No answer for cloud device state request {device_sets["localDeviceId"]}'
                        # if args.cloud:
                        #     LOGGER.error(err)
                        # else:
                        LOGGER.info(err)

                    if print_onboarded_devices:
                        queue_printer.print(state_str)

                device_state_req_threads = []

                product_ids: set[str] = set()
                if self.acc_settings and "devices" in self.acc_settings:
                    for device_sets in self.acc_settings["devices"]:
                        # if not device_sets["productId"].startswith("@klyqa.lighting"):
                        #     continue
                        device_state_req_threads.append(
                            Thread(target=device_request_and_print, args=(device_sets,))
                        )
                        t = Thread(target=device_request_and_print, args=(device_sets,))
                        # t.start()
                        # t.join()

                        if isinstance(AES_KEYs, dict):
                            AES_KEYs[
                                format_uid(device_sets["localDeviceId"])
                            ] = bytes.fromhex(device_sets["aesKey"])
                        product_ids.add(device_sets["productId"])

                for t in device_state_req_threads:
                    t.start()
                for t in device_state_req_threads:
                    t.join()

                queue_printer.stop()

                def get_conf(id, device_configs):
                    async def req():
                        try:
                            ret = await self.request("config/product/" + id, timeout=30)
                            return ret
                        except:
                            return None

                    config = asyncio.run(req())
                    if config:
                        device_config: Device_config = config
                        device_configs[id] = device_config

                if self.acc_settings and product_ids:
                    threads: list[Thread] = [
                        Thread(target=get_conf, args=(i, device_configs))
                        for i in product_ids
                    ]
                    for t in threads:
                        LOGGER.debug(
                            "Try to request device config for "
                            + t._args[0]
                            + " from server."
                        )
                        t.start()
                    for t in threads:
                        t.join()

                device_configs, cached = await async_json_cache(
                    device_configs, "device.configs.json"
                )
                if cached:
                    LOGGER.info("No server reply for device configs. Using cache.")

            except Exception as e:
                LOGGER.error("Error during login to klyqa: " + str(e))
                return False
        return True

    def get_header_default(self) -> dict[str, str]:
        header: dict[str, str] = {
            "X-Request-Id": str(uuid.uuid4()),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "accept-encoding": "gzip, deflate, utf-8",
        }
        return header

    def get_header(self) -> dict[str, str]:
        return {
            **self.get_header_default(),
            **{"Authorization": "Bearer " + self.access_token},
        }

    async def request(self, url, **kwargs) -> TypeJSON | None:
        loop = asyncio.get_event_loop()
        answer: TypeJSON | None = None
        try:
            response = await loop.run_in_executor(
                None,
                functools.partial(
                    requests.get,
                    self.host + "/" + url,
                    headers=self.get_header()
                    if self.access_token
                    else self.get_header_default(),
                    **kwargs,
                ),
            )
            if response.status_code != 200:
                # TODO: make here a right
                raise Exception(response.text)
            answer = json.loads(response.text)
        except Exception as e:
            LOGGER.debug(f"{traceback.format_exc()}")
            answer = None
        return answer

    async def post(self, url, **kwargs) -> TypeJSON | None:
        loop = asyncio.get_event_loop()
        answer: TypeJSON | None = None
        try:
            response = await loop.run_in_executor(
                None,
                functools.partial(
                    requests.post,
                    self.host + "/" + url,
                    headers=self.get_header(),
                    **kwargs,
                ),
            )
            if response.status_code != 200:
                raise Exception(response.text)
            answer = json.loads(response.text)
        except Exception as e:
            LOGGER.debug(f"{traceback.format_exc()}")
            answer = None
        return answer

    def shutdown(self) -> None:
        """Logout again from klyqa account."""
        # for uid in self.devices:
        #     try:
        #         device = self.devices[uid]
        #         connection.connection.shutdown(socket.SHUT_RDWR)
        #         connection.connection.close()
        #         connection.connection = None
        #     except Exception as excp:
        #         pass
        if self.access_token:
            try:
                response = requests.post(
                    self.host + "/auth/logout", headers=self.get_header_default()
                )
                self.access_token = ""
            except Exception as excp:
                LOGGER.warning("Couldn't logout.")

    async def aes_handshake_and_send_msgs(
        self,
        r_device: RefParse,
        r_msg: RefParse,
        connection: LocalConnection,
        use_dev_aes=False,
        timeout_ms=11000,  # currently only used for pause timeout between sending messages if multiple for device in queue to send.
    ) -> Type[Device_TCP_return.__class__]:
        """
        FIX: return type! sometimes return value sometimes tuple...

        Finish AES handshake.
        Getting the identity of the device.
        Send the commands in message queue to the device with the device u_id or to any device.

        params:
            device: Device - (initial) device object with the tcp connection
            target_device_uid - If given device_uid only send commands when the device unit id equals the target_device_uid
            discover_mode - if True do the process to any device unit id.

        returns: tuple[int, dict] or tuple[int, str]
                dict: Json response of the device
                str: Error string message
                int: Error type
                    0 - success - no error
                    1 - on error
                    2 - not correct device uid
                    3 - tcp connection ended, shall retry
                    4 - error on reading response message from device, shall retry
                    5 - error getting lock for device, shall retry
                    6 - missing aes key
                    7 - value not valid for device config

        """

        global sep_width, LOGGER
        device: KlyqaDevice | None = r_device.ref
        if device is None or connection.socket is None:
            return Device_TCP_return.unknown_error
        task = asyncio.current_task()
        TASK_NAME: str = task.get_name() if task is not None else ""
        AES_KEY = ""

        data: bytes = b""
        last_send: datetime.datetime = datetime.datetime.now()
        connection.socket.settimeout(0.001)
        pause: datetime.timedelta = datetime.timedelta(milliseconds=0)
        elapsed: datetime.timedelta = datetime.datetime.now() - last_send

        loop = asyncio.get_event_loop()

        return_val = Device_TCP_return.nothing_done

        msg_sent: Message | None = None
        communication_finished: bool = False

        # LOGGER.debug(f"{TASK_NAME} - AES SEND: wait1 another 2 seconds ... ")
        # await asyncio.sleep(2)
        # LOGGER.debug(f"{TASK_NAME} - AES SEND: wait2 another 2 seconds ...")
        # await asyncio.sleep(2)
        # LOGGER.debug(f"{TASK_NAME} - AES SEND: wait3 another 2 seconds ...")
        # await asyncio.sleep(2)
        # LOGGER.debug(f"{TASK_NAME} - AES SEND: go process now ... ")

        async def __send_msg(msg: Message) -> Message | None:
            nonlocal last_send, pause, return_val, device

            LOGGER.debug(
                f"{TASK_NAME} - Sent msg '{msg.msg_queue}' to device '{device.u_id}'."
            )

            def rm_msg() -> None:
                try:
                    LOGGER.debug(f"{TASK_NAME} - rm_msg()")
                    self.message_queue[device.u_id].remove(msg)
                    msg.state = Message_state.sent

                    if (
                        device.u_id in self.message_queue
                        and not self.message_queue[device.u_id]
                    ):
                        del self.message_queue[device.u_id]
                except Exception as e:
                    LOGGER.debug(f"{TASK_NAME} - {traceback.format_exc()}")

            return_val = Device_TCP_return.sent

            if len(msg.msg_queue) and len(msg.msg_queue[-1]) == 2:
                text, ts = msg.msg_queue.pop()
                msg.msg_queue_sent.append(text)
            else:
                text, ts, check_func = msg.msg_queue.pop()
                msg.msg_queue_sent.append(text)
                if not check_func(
                    product_id=device.ident.product_id if device.ident else ""
                ):
                    rm_msg()
                    # return (7, "value not valid for device config")
                    return None

            pause = datetime.timedelta(milliseconds=timeout_ms)
            try:
                if await loop.run_in_executor(None, send_msg, text, device, connection):
                    rm_msg()
                    last_send = datetime.datetime.now()
                    return msg
            except Exception as excep:
                LOGGER.debug(f"{TASK_NAME} - {traceback.format_exc()}")
                # return (1, "error during send")
            return None

        while not communication_finished and (
            len(self.message_queue) > 0 or elapsed < pause
        ):
            try:
                data = await loop.run_in_executor(None, connection.socket.recv, 4096)
                if len(data) == 0:
                    LOGGER.debug(f"{TASK_NAME} - EOF")
                    # return (3, "TCP connection ended.")
                    return Device_TCP_return.tcp_error
            except socket.timeout:
                pass
            except Exception as excep:
                LOGGER.debug(f"{TASK_NAME} - {traceback.format_exc()}")
                # return (1, "unknown error")
                return Device_TCP_return.unknown_error

            elapsed = datetime.datetime.now() - last_send

            if connection.state == "CONNECTED":
                ## check how the answer come in and how they can be connected to the messages that has been sent.
                i = 0
                try:
                    send_next: bool = elapsed >= pause
                    # if len(message_queue_tx) > 0 and :
                    while (
                        send_next
                        and device.u_id in self.message_queue
                        and i < len(self.message_queue[device.u_id])
                    ):
                        msg = self.message_queue[device.u_id][i]
                        i: int = i + 1
                        if msg.state == Message_state.unsent:
                            msg_sent = await __send_msg(msg)
                            r_msg.ref = msg_sent
                            if not msg_sent:
                                return Device_TCP_return.sent_error
                            else:
                                break
                            # await recv(msg)
                except:
                    pass

            while not communication_finished and (len(data)):
                LOGGER.debug(
                    f"{TASK_NAME} - "
                    + "TCP server received "
                    + str(len(data))
                    + " bytes from "
                    + str(connection.address)
                )

                # Read out the data package as follows: package length (pkgLen), package type (pkgType) and package data (pkg)

                pkgLen: int = data[0] * 256 + data[1]
                pkgType: int = data[3]

                pkg: bytes = data[4 : 4 + pkgLen]
                if len(pkg) < pkgLen:
                    LOGGER.debug(
                        f"{TASK_NAME} - Incomplete packet, waiting for more..."
                    )
                    break

                data: bytes = data[4 + pkgLen :]

                if connection.state == "WAIT_IV" and pkgType == 0:

                    # Check identification package from device, lock the device object for changes,
                    # safe the idenfication to device object if it is a not known device,
                    # send the local initial vector for the encrypted communication to the device.

                    LOGGER.debug(f"{TASK_NAME} - Plain: {pkg}")
                    json_response: dict[str, Any] = json.loads(pkg)
                    try:
                        ident: KlyqaDeviceResponseIdent = KlyqaDeviceResponseIdent(
                            **json_response["ident"]
                        )
                        device.u_id = ident.unit_id
                    except Exception as e:
                        return Device_TCP_return.no_uid_device

                    is_new_device = False
                    if device.u_id != "no_uid" and device.u_id not in self.devices:
                        is_new_device = True
                        if self.acc_settings:
                            dev: list[dict] = [
                                device2
                                for device2 in self.acc_settings["devices"]
                                if format_uid(device2["localDeviceId"])
                                == format_uid(device.u_id)
                            ]
                            if dev:
                                device.acc_sets = dev[0]
                        if ident.product_id.find(".lighting") > -1:
                            self.devices[device.u_id] = KlyqaBulb()
                        elif ident.product_id.find(".cleaning") > -1:
                            self.devices[device.u_id] = KlyqaVC()

                    # device_b: KlyqaDevice
                    # device.ident.product_id.startswith("@klyqa.cleaning"):
                    #     device_b: KlyqaDevice = self.devices[device.u_id]

                    # cached client device (self.devices), incoming device object created on tcp connection acception
                    if not device.u_id in self.devices:
                        return -1
                    device_b: KlyqaDevice = self.devices[device.u_id]
                    if await device_b.use_lock():

                        # if not is_new_device:
                        #     try:
                        #         """There shouldn't be an open connection on the already known devices, but if there is close it."""
                        #         device_b.local.socket.shutdown(socket.SHUT_RDWR)
                        #         device_b.local.socket.close()
                        #         LOGGER.debug(f"{TASK_NAME} - tcp closed for device.u_id.")
                        #         """just ensure connection is closed, so that device knows it as well"""
                        #     except:
                        #         pass

                        device_b.local_addr = connection.address
                        if is_new_device:
                            device_b.ident = ident
                            device_b.u_id = ident.unit_id
                        device = device_b
                        r_device.ref = device_b
                    else:
                        err: str = f"{TASK_NAME} - Couldn't get use lock for device {device_b.get_name()} {connection.address})"
                        LOGGER.error(err)
                        return Device_TCP_return.device_lock_timeout

                    connection.received_packages.append(json_response)
                    device.save_device_message(json_response)

                    if (
                        not device.u_id in self.message_queue
                        or not self.message_queue[device.u_id]
                    ):
                        if device.u_id in self.message_queue:
                            del self.message_queue[device.u_id]
                        return Device_TCP_return.no_message_to_send

                    found = ""
                    settings_device = ""
                    if self.acc_settings and "devices" in self.acc_settings:
                        settings_device = [
                            device_sets
                            for device_sets in self.acc_settings["devices"]
                            if format_uid(device_sets["localDeviceId"])
                            == format_uid(device.u_id)
                        ]
                    if settings_device:
                        name = settings_device[0]["name"]
                        found = found + ' "' + name + '"'
                    else:
                        found = found + f" {json_response['ident']['unit_id']}"

                    LOGGER.info(f"{TASK_NAME} - Found device {found}")
                    if "all" in AES_KEYs:
                        AES_KEY = AES_KEYs["all"]
                    elif use_dev_aes or "dev" in AES_KEYs:
                        AES_KEY = AES_KEY_DEV
                    elif isinstance(AES_KEYs, dict) and device.u_id in AES_KEYs:
                        AES_KEY = AES_KEYs[device.u_id]
                    try:
                        if connection.socket is not None:
                            connection.socket.send(
                                bytes([0, 8, 0, 1]) + connection.localIv
                            )
                    except:
                        # return (1, "Couldn't send local IV.")
                        return Device_TCP_return.err_local_iv

                if connection.state == "WAIT_IV" and pkgType == 1:

                    # Receive the remote initial vector (iv) for aes encrypted communication.

                    connection.remoteIv = pkg
                    connection.received_packages.append(pkg)
                    if not AES_KEY:
                        LOGGER.error(
                            f"{TASK_NAME} - "
                            + "Missing AES key. Probably not in onboarded devices. Provide AES key with --aes [key]! "
                            + str(device.u_id)
                        )
                        # return (6, "missing aes key")
                        return Device_TCP_return.missing_aes_key
                    connection.sendingAES = AES.new(
                        AES_KEY,
                        AES.MODE_CBC,
                        iv=connection.localIv + connection.remoteIv,
                    )
                    connection.receivingAES = AES.new(
                        AES_KEY,
                        AES.MODE_CBC,
                        iv=connection.remoteIv + connection.localIv,
                    )

                    connection.state = "CONNECTED"

                elif connection.state == "CONNECTED" and pkgType == 2:

                    # Receive encrypted answer for sent message.

                    cipher: bytes = pkg

                    plain: bytes = connection.receivingAES.decrypt(cipher)
                    connection.received_packages.append(plain)
                    if msg_sent is not None:
                        msg_sent.answer = plain
                        json_response = None
                        try:
                            plain_utf8: str = plain.decode()
                            json_response = json.loads(plain_utf8)
                            device.save_device_message(json_response)
                            connection.sent_msg_answer = json_response
                            connection.aes_key_confirmed = True
                            LOGGER.debug(
                                f"{TASK_NAME} - device uid {device.u_id} aes_confirmed {connection.aes_key_confirmed}"
                            )
                        except:
                            LOGGER.error(
                                f"{TASK_NAME} - Could not load json message from device: "
                            )
                            LOGGER.error(f"{TASK_NAME} - {pkg}")
                            # return (4, "Could not load json message from device.")
                            return Device_TCP_return.response_error

                        msg_sent.answer_utf8 = plain_utf8
                        msg_sent.answer_json = json_response
                        msg_sent.state = Message_state.answered
                        return_val = Device_TCP_return.answered

                        device.recv_msg_unproc.append(msg_sent)
                        device.process_msgs()

                    LOGGER.debug(
                        f"{TASK_NAME} - Request's reply decrypted: " + str(plain)
                    )
                    # return (0, json_response)
                    communication_finished = True
                    break
                    return return_val
                else:
                    LOGGER.debug(
                        f"{TASK_NAME} - No answer to process. Waiting on answer of the device ... "
                    )
        return return_val

    async def request_account_settings_eco(self, scan_interval: int = 60) -> bool:
        if not await self.__acc_settings_lock.acquire():
            return False
        try:
            ret = False
            now = datetime.datetime.now()
            if not self._settings_loaded_ts or (
                now - self._settings_loaded_ts
                >= datetime.timedelta(seconds=scan_interval)
            ):
                """look that the settings are loaded only once in the scan interval"""
                ret = await self.request_account_settings()
        finally:
            self.__acc_settings_lock.release()
        return ret

    async def request_account_settings(self) -> None:
        try:
            self.acc_settings = await self.request("settings")

            """saving updated account settings to cache"""

            # acc_settings_cache = (
            #     {args.username[0]: self.acc_settings} if self.acc_settings else {}
            # )

            # self.acc_settings, cached = await async_json_cache(
            #     acc_settings_cache, "last.acc_settings.cache.json"
            # )

            # if cached:
            #     LOGGER.info(
            #         f"No server reply for account settings {args.username[0]}. Using cache."
            #     )
            #     if (
            #         not self.acc_settings
            #         or list(self.acc_settings.keys())[0] != args.username[0]
            #     ):
            #         LOGGER.error(
            #             f"Account settings are from another account than "
            #             + f"{args.username[0]}."
            #         )
            #         return False
        except:
            pass

        # self.acc_settings = self.acc_settings[list(self.acc_settings.keys())[0]]

    async def send_to_devices(
        self,
        args,
        args_in,
        udp: socket.socket | None = None,
        tcp: socket.socket | None = None,
        timeout_ms=5000,
        async_answer_callback: Callable[[Message, str], Any] | None = None,
    ):
        """Collect the messages for the devices to send to

        Args:
            args (Argsparse): Parsed args object
            args_in (list): List of arguments parsed to the script call
            timeout_ms (int, optional): Timeout to send. Defaults to 5000.

        Raises:
            Exception: Network or file errors

        Returns:
            bool: True if succeeded.
        """
        if not udp:
            udp = self.data_communicator.udp
        if not tcp:
            tcp = self.data_communicator.tcp
        try:
            global sep_width, device_configs

            loop = asyncio.get_event_loop()

            send_started: datetime.datetime = datetime.datetime.now()

            if args.dev:
                args.local = True
                args.tryLocalThanCloud = False
                args.cloud = False

            if args.debug:
                LOGGER.setLevel(level=logging.DEBUG)
                logging_hdl.setLevel(level=logging.DEBUG)

            if args.cloud or args.local:
                args.tryLocalThanCloud = False

            if args.aes is not None:
                AES_KEYs["all"] = bytes.fromhex(args.aes[0])

            target_device_uids = set()

            message_queue_tx_local = []
            message_queue_tx_state_cloud = []
            message_queue_tx_command_cloud = []

            # # TODO: Missing cloud discovery and interactive device selection. Send to devices if given as argument working.
            # if (args.local or args.tryLocalThanCloud) and (
            #     not args.device_name
            #     and not args.device_unitids
            #     and not args.allDevices
            #     and not args.discover
            # ):
            #     discover_local_args: list[str] = [
            #         "--request",
            #         "--allDevices",
            #         "--selectDevice",
            #         "--discover"
            #     ]

            #     orginal_args_parser: argparse.ArgumentParser = get_description_parser()
            #     discover_local_args_parser: argparse.ArgumentParser = get_description_parser()

            #     add_config_args(parser=orginal_args_parser)
            #     add_config_args(parser=discover_local_args_parser)
            #     add_command_args(parser=discover_local_args_parser)

            #     original_config_args_parsed, _ = orginal_args_parser.parse_known_args(
            #         args=args_in
            #     )

            #     discover_local_args_parsed = discover_local_args_parser.parse_args(
            #         discover_local_args, namespace=original_config_args_parsed
            #     )

            #     uids = await self.send_to_devices(
            #         discover_local_args_parsed,
            #         args_in,
            #         udp=udp,
            #         tcp=tcp,
            #         timeout_ms=3500,
            #     )
            #     if isinstance(uids, set) or isinstance(uids, list):
            #         # args_in.extend(["--device_unitids", ",".join(list(uids))])
            #         args_in = ["--device_unitids", ",".join(list(uids))] + args_in
            #     elif isinstance(uids, str) and uids == "no_devices":
            #         return False
            #     else:
            #         LOGGER.error("Error during local discovery of the devices.")
            #         return False

            #     add_command_args(parser=orginal_args_parser)
            #     args = orginal_args_parser.parse_args(args=args_in, namespace=args)

            if args.device_name is not None:
                if not self.acc_settings:
                    LOGGER.error(
                        'Missing account settings to resolve device name  "'
                        + args.device_name
                        + '"to unit id.'
                    )
                    return 1
                dev: list[str] = [
                    format_uid(device["localDeviceId"])
                    for device in self.acc_settings["devices"]
                    if device["name"] == args.device_name
                ]
                if not dev:
                    LOGGER.error(
                        'Device name "'
                        + args.device_name
                        + '" not found in account settings.'
                    )
                    return 1
                else:
                    target_device_uids: set[str] = set(format_uid(dev[0]))

            if args.device_unitids is not None:
                target_device_uids = set(
                    map(format_uid, set(args.device_unitids[0].split(",")))
                )
                print("Send to device: " + ", ".join(args.device_unitids[0].split(",")))

            if not args.selectDevice:
                product_ids: set[str] = {
                    device.ident.product_id
                    for uid, device in self.devices.items()
                    if device.ident and device.ident.product_id
                }

                for product_id in list(product_ids):
                    if product_id in device_configs:
                        continue
                    LOGGER.debug("Try to request device config from server.")
                    try:
                        config = await self.request(
                            "config/product/" + product_id,
                            timeout=30,
                        )
                        device_config: Device_config = config
                        device_configs[product_id] = device_config
                    except:
                        pass

            ### device specific commands ###

            async def send_to_devices_cb(args):
                """Send to devices callback for discover of devices option"""
                return await self.send_to_devices(
                    args,
                    args_in,
                    udp=udp,
                    tcp=tcp,
                    timeout_ms=3500,
                )

            scene: list[str] = []
            if args.type == DeviceType.lighting.name:
                await process_args_to_msg_lighting(
                    args,
                    args_in,
                    send_to_devices_cb,
                    message_queue_tx_local,
                    message_queue_tx_command_cloud,
                    message_queue_tx_state_cloud,
                    scene,
                )
            elif args.type == DeviceType.cleaner.name:
                await process_args_to_msg_cleaner(
                    args,
                    args_in,
                    send_to_devices_cb,
                    message_queue_tx_local,
                    message_queue_tx_command_cloud,
                    message_queue_tx_state_cloud,
                )
            else:
                LOGGER.error("Missing device type.")
                return False

            success = True
            if args.local or args.tryLocalThanCloud:
                if args.passive:
                    if udp:
                        LOGGER.debug("Waiting for UDP broadcast")
                        data, address = udp.recvfrom(4096)
                        LOGGER.debug(
                            "\n\n 2. UDP server received: ",
                            data.decode("utf-8"),
                            "from",
                            address,
                            "\n\n",
                        )

                        LOGGER.debug("3a. Sending UDP ack.\n")
                        udp.sendto("QCX-ACK".encode("utf-8"), address)
                        time.sleep(1)
                        LOGGER.debug("3b. Sending UDP ack.\n")
                        udp.sendto("QCX-ACK".encode("utf-8"), address)
                else:

                    message_queue_tx_local.reverse()
                    send_started_local: datetime.datetime = datetime.datetime.now()

                    if args.discover:

                        print(sep_width * "-")
                        print("Search local network for devices ...")
                        print(sep_width * "-")

                        discover_end_event: Event = asyncio.Event()
                        discover_timeout_secs: float = 2.5

                        async def discover_answer_end(
                            answer: TypeJSON, uid: str
                        ) -> None:
                            LOGGER.debug(f"discover ping end")
                            discover_end_event.set()

                        LOGGER.debug(f"discover ping start")
                        # send a message to uid "all" which is fake but will get the identification message
                        # from the devices in the aes_search and send msg function and we can send then a real
                        # request message to these discovered devices.
                        await self.set_send_message(
                            message_queue_tx_local,
                            "all",
                            args,
                            discover_answer_end,
                            discover_timeout_secs,
                        )

                        await discover_end_event.wait()
                        if self.devices:
                            target_device_uids = set(
                                u_id for u_id, v in self.devices.items()
                            )
                    # else:
                    msg_wait_tasks = {}

                    to_send_device_uids: set[str] = target_device_uids.copy()

                    async def sl(uid) -> None:
                        try:
                            await asyncio.sleep(timeout_ms / 1000)
                        except CancelledError as e:
                            LOGGER.debug(f"sleep uid {uid} cancelled.")
                        except Exception as e:
                            pass

                    for i in target_device_uids:
                        try:
                            msg_wait_tasks[i] = loop.create_task(sl(i))
                        except Exception as e:
                            pass

                    async def async_answer_callback_local(msg, uid) -> None:
                        if msg and msg.msg_queue_sent:
                            LOGGER.debug(f"{uid} msg callback.")
                        # else:
                        #     LOGGER.debug(f"{uid} {msg} msg callback.")
                        if uid in to_send_device_uids:
                            to_send_device_uids.remove(uid)
                        try:
                            msg_wait_tasks[uid].cancel()
                        except:
                            pass
                        if async_answer_callback:
                            await async_answer_callback(msg, uid)

                    for i in target_device_uids:
                        await self.set_send_message(
                            message_queue_tx_local.copy(),
                            i,
                            args,
                            callback=async_answer_callback_local,
                            time_to_live_secs=(timeout_ms / 1000),
                        )

                    for i in target_device_uids:
                        try:
                            LOGGER.debug(f"wait for send task {i}.")
                            await asyncio.wait([msg_wait_tasks[i]])
                            LOGGER.debug(f"wait for send task {i} end.")
                            # await asyncio.wait_for(msg_wait_tasks[i], timeout=(timeout_ms / 1000))
                        except CancelledError as e:
                            LOGGER.debug(f"sleep wait for uid {i} cancelled.")
                        except Exception as e:
                            pass

                    LOGGER.debug(f"wait for all target device uids done.")

                    if args.selectDevice:
                        print(sep_width * "-")
                        # devices_working = {k: v for k, v in self.devices.items() if v.local.aes_key_confirmed}
                        devices_working: dict[str, KlyqaDevice] = {
                            u_id: device
                            for u_id, device in self.devices.items()
                            if (
                                (
                                    args.type == DeviceType.lighting.name
                                    and isinstance(device, KlyqaBulb)
                                )
                                or (
                                    args.type == DeviceType.cleaner.name
                                    and isinstance(device, KlyqaVC)
                                )
                            )
                            and (
                                (
                                    device.status
                                    and device.status.ts
                                    and isinstance(device.status.ts, datetime.datetime)
                                    and device.status.ts > send_started_local
                                )
                                or (
                                    (args.cloud or args.tryLocalThanCloud)
                                    and device.cloud
                                    and device.cloud.connected
                                )
                            )
                        }
                        print(
                            "Found "
                            + str(len(devices_working))
                            + " "
                            + ("device" if len(devices_working) == 1 else "devices")
                            + " with working aes keys"
                            + (" (dev aes key)" if args.dev else "")
                            + "."
                        )
                        if len(devices_working) <= 0:
                            return "no_devices"
                        print(sep_width * "-")
                        count = 1
                        device_items: list[KlyqaDevice] = list(devices_working.values())

                        if device_items:
                            print(
                                "Status attributes: ("
                                + get_obj_attrs_as_string(KlyqaBulbResponseStatus)
                                + ") (local IP-Address)"
                            )
                            print("")

                        for device in device_items:
                            name: str = f"Unit ID: {device.u_id}"
                            if device.acc_sets and "name" in device.acc_sets:
                                name = device.acc_sets["name"]
                            address: str = (
                                f" (local {device.local_addr['ip']}:{device.local_addr['port']})"
                                if device.local_addr["ip"]
                                else ""
                            )
                            cloud = (
                                f" (cloud connected)" if device.cloud.connected else ""
                            )
                            status: str = (
                                f" ({device.status})"
                                if device.status
                                else " (no status)"
                            )
                            print(f"{count}) {name}{status}{address}{cloud}")
                            count = count + 1

                        if self.devices:
                            print("")
                            device_num_s: str = input(
                                "Choose bulb number(s) (comma seperated) a (all),[1-9]*{,[1-9]*}*: "
                            )
                            target_device_uids_lcl = set()
                            if device_num_s == "a":
                                return set(b.u_id for b in device_items)
                            else:
                                for bulb_num in device_num_s.split(","):
                                    bulb_num: int = int(bulb_num)
                                    if bulb_num > 0 and bulb_num < count:
                                        target_device_uids_lcl.add(
                                            device_items[bulb_num - 1].u_id
                                        )
                            return target_device_uids_lcl

                        """ no devices found. Exit script. """
                        sys.exit(0)

                if target_device_uids and len(to_send_device_uids) > 0:
                    """error"""
                    sent_locally_error: str = (
                        "The commands "
                        + "failed to send locally to the device(s): "
                        + ", ".join(to_send_device_uids)
                    )
                    if args.tryLocalThanCloud:
                        LOGGER.info(sent_locally_error)
                    else:
                        LOGGER.error(sent_locally_error)
                    success = False

            if args.cloud or args.tryLocalThanCloud:
                """cloud processing"""

                queue_printer: EventQueuePrinter = EventQueuePrinter()
                response_queue = []

                async def _cloud_post(
                    device: KlyqaDevice, json_message, target: str
                ) -> None:
                    cloud_device_id = device.acc_sets["cloudDeviceId"]
                    unit_id: str = format_uid(device.acc_sets["localDeviceId"])
                    LOGGER.info(
                        f"Post {target} to the device '{cloud_device_id}' (unit_id: {unit_id}) over the cloud."
                    )
                    resp = {
                        cloud_device_id: await self.post(
                            url=f"device/{cloud_device_id}/{target}",
                            json=json_message,
                        )
                    }
                    resp_print = ""
                    name: str = device.u_id
                    if device.acc_sets and "name" in device.acc_sets:
                        name = device.acc_sets["name"]
                    resp_print: str = f'Device "{name}" cloud response:'
                    resp_print = json.dumps(resp, sort_keys=True, indent=4)
                    device.cloud.received_packages.append(resp)
                    response_queue.append(resp_print)
                    queue_printer.print(resp_print)

                async def cloud_post(device: KlyqaDevice, json_message, target: str):
                    if not await device.use_lock():
                        LOGGER.error(
                            f"Couldn't get use lock for device {device.get_name()})"
                        )
                        return 1
                    try:
                        await _cloud_post(device, json_message, target)
                    except CancelledError:
                        LOGGER.error(
                            f"Cancelled cloud send "
                            + (device.u_id if device.u_id else "")
                            + "."
                        )
                    finally:
                        await device.use_unlock()

                started: datetime.datetime = datetime.datetime.now()
                # timeout_ms = 30000

                async def process_cloud_messages(target_uids) -> None:

                    threads = []
                    target_devices: list[KlyqaDevice] = [
                        b
                        for b in self.devices.values()
                        for t in target_uids
                        if b.u_id == t
                    ]

                    def create_post_threads(target, msg):
                        return [
                            (loop.create_task(cloud_post(b, msg, target)), b)
                            for b in target_devices
                        ]

                    state_payload_message = dict(
                        ChainMap(*message_queue_tx_state_cloud)
                    )
                    # state_payload_message = json.loads(*message_queue_tx_state_cloud) if message_queue_tx_state_cloud else ""

                    command_payload_message = dict(
                        ChainMap(*message_queue_tx_command_cloud)
                    )
                    # command_payload_message = json.loads(*message_queue_tx_command_cloud) if message_queue_tx_command_cloud else ""
                    if state_payload_message:
                        threads.extend(
                            create_post_threads(
                                "state", {"payload": state_payload_message}
                            )
                        )
                    if command_payload_message:
                        threads.extend(
                            create_post_threads("command", command_payload_message)
                        )

                    count = 0
                    timeout: float = timeout_ms / 1000
                    for t, device in threads:
                        count: int = count + 1
                        """wait at most timeout_ms wanted minus seconds elapsed since sending"""
                        try:
                            await asyncio.wait_for(
                                t,
                                timeout=timeout
                                - (datetime.datetime.now() - started).seconds,
                            )
                        except asyncio.TimeoutError:
                            LOGGER.error(f'Timeout for "{device.get_name()}"!')
                            t.cancel()
                        except:
                            pass

                await process_cloud_messages(
                    target_device_uids if args.cloud else to_send_device_uids
                )
                """if there are still target devices that the local send couldn't reach, try send the to_send_device_uids via cloud"""

                queue_printer.stop()

                if len(response_queue):
                    success = True

            if success and scene:
                scene_start_args: list[str] = ["--routine_id", "0", "--routine_start"]

                orginal_args_parser = get_description_parser()
                scene_start_args_parser: ArgumentParser = get_description_parser()

                add_config_args(parser=orginal_args_parser)
                add_config_args(parser=scene_start_args_parser)
                add_command_args(parser=scene_start_args_parser)

                original_config_args_parsed, _ = orginal_args_parser.parse_known_args(
                    args=args_in
                )

                scene_start_args_parsed = scene_start_args_parser.parse_args(
                    scene_start_args, namespace=original_config_args_parsed
                )

                ret = await self.send_to_devices(
                    scene_start_args_parsed,
                    args_in,
                    udp=udp,
                    tcp=tcp,
                    timeout_ms=timeout_ms
                    - (datetime.datetime.now() - send_started).total_seconds()
                    * 1000,  # 3000
                )

                if isinstance(ret, bool) and ret:
                    success = True
                else:
                    LOGGER.error(f"Couldn't start scene {scene[0]}.")
                    success = False

            return success
        except Exception as e:
            LOGGER.debug(traceback.format_exc())

    async def send_to_devices_wrapped(self, args_parsed, args_in, timeout_ms=5000):
        """set up broadcast port and tcp reply connection port"""

        if args_parsed.cloud or args_parsed.local:
            args_parsed.tryLocalThanCloud = False

        if args_parsed.debug:
            LOGGER.setLevel(level=logging.DEBUG)
            logging_hdl.setLevel(level=logging.DEBUG)

        if args_parsed.dev:
            AES_KEYs["dev"] = AES_KEY_DEV

        local_communication = args_parsed.local or args_parsed.tryLocalThanCloud
        # self.data_communicator.udp = None
        # self.data_communicator.tcp = None

        if local_communication:
            # await tcp_udp_port_lock.acquire()
            if not await self.data_communicator.bind_ports(
                # args_parsed.myip[0] if args_parsed.myip is not None else None
            ):
                return 1
            # try:
            #     self.data_communicator.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            #     self.data_communicator.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            #     self.data_communicator.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            #     if args_parsed.myip is not None:
            #         server_address = (args_parsed.myip[0], 2222)
            #     else:
            #         server_address = ("0.0.0.0", 2222)
            #     self.data_communicator.udp.bind(server_address)
            #     LOGGER.debug("Bound UDP port 2222")

            # except:
            #     LOGGER.error(
            #         "Error on opening and binding the udp port 2222 on host for initiating the device communication."
            #     )
            #     return 1

            # try:
            #     self.data_communicator.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #     self.data_communicator.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            #     server_address = ("0.0.0.0", 3333)
            #     self.data_communicator.tcp.bind(server_address)
            #     LOGGER.debug("Bound TCP port 3333")
            #     self.data_communicator.tcp.listen(1)

            # except:
            #     LOGGER.error(
            #         "Error on opening and binding the tcp port 3333 on host for initiating the device communication."
            #     )
            #     return 1

        exit_ret = 0

        async def async_answer_callback(msg, uid):
            print(f"{uid}: ")
            if msg:
                try:
                    LOGGER.info(f"Answer received from {uid}.")
                    print(
                        f"{json.dumps(json.loads(msg.answer), sort_keys=True, indent=4)}"
                    )
                except:
                    pass
            else:
                LOGGER.error(f"Error no message returned from {uid}.")

        if not await self.send_to_devices(
            args_parsed,
            args_in,
            udp=self.data_communicator.udp,
            tcp=self.data_communicator.tcp,
            timeout_ms=timeout_ms,
            async_answer_callback=async_answer_callback,
        ):
            exit_ret = 1

        # parser = get_description_parser()
        # args = ["--request"]
        # args.extend(["--local", "--debug", "--device_unitids", f"c4172283e5da92730bb5"])

        # add_config_args(parser=parser)
        # add_command_args(parser=parser)

        # args_parsed = parser.parse_args(args=args)

        # if not await self.send_to_devices(
        #     args_parsed, args, udp=self.data_communicator.udp, tcp=self.data_communicator.tcp, timeout_ms=timeout_ms, async_answer_callback=async_answer_callback
        # ):
        #     exit_ret = 1

        await self.search_and_send_loop_task_stop()

        LOGGER.debug("Closing ports")
        if local_communication:
            self.data_communicator.shutdown()
            # try:
            #     self.data_communicator.tcp.shutdown(socket.SHUT_RDWR)
            #     self.data_communicator.tcp.close()
            #     LOGGER.debug("Closed TCP port 3333")
            # except:
            #     pass

            # try:
            #     self.udp.close()
            #     LOGGER.debug("Closed UDP port 2222")
            # except:
            #     pass
            # tcp_udp_port_lock.release()

        return exit_ret


def main():
    # global klyqa_accs

    klyqa_accs: dict[str, Klyqa_account] = None
    if not klyqa_accs:
        klyqa_accs = dict()

    loop = asyncio.get_event_loop()

    parser = get_description_parser()

    add_config_args(parser=parser)

    # add_command_args(parser=parser)
    args_in: list[str] = sys.argv[1:]

    # add_config_args(parser=orginal_args_parser)
    # add_config_args(parser=discover_local_args_parser2)
    # add_command_args(parser=discover_local_args_parser2)

    (
        config_args_parsed,
        _,
    ) = parser.parse_known_args(args=args_in)

    if config_args_parsed.type == DeviceType.cleaner.name:
        add_command_args_cleaner(parser=parser)
    elif config_args_parsed.type == DeviceType.lighting.name:
        add_command_args_bulb(parser=parser)
    else:
        LOGGER.error("Unknown command type.")
        sys.exit(1)

    # discover_local_args_parsed2 = (
    #     discover_local_args_parser2.parse_args(
    #         [],
    #         namespace=original_config_args_parsed,
    #     )
    # )

    if len(args_in) < 2:
        parser.print_help()
        sys.exit(1)

    args_parsed = parser.parse_args(args=args_in)

    if not args_parsed:
        sys.exit(1)

    if args_parsed.debug:
        LOGGER.setLevel(level=logging.DEBUG)
        logging_hdl.setLevel(level=logging.DEBUG)

    timeout_ms = DEFAULT_SEND_TIMEOUT_MS
    if args_parsed.timeout:
        timeout_ms = int(args_parsed.timeout[0])

    server_ip = args_parsed.myip[0] if args_parsed.myip else "0.0.0.0"
    data_communicator: Data_communicator = Data_communicator(server_ip)

    # loop.run_until_complete(data_communicator.bind_ports())

    print_onboarded_devices: bool = (
        not args_parsed.device_name
        and not args_parsed.device_unitids
        and not args_parsed.allDevices
    )

    klyqa_acc: Klyqa_account | None = None

    if args_parsed.dev or args_parsed.aes:
        if args_parsed.dev:
            LOGGER.info("development mode. Using default aes key.")
        elif args_parsed.aes:
            LOGGER.info("aes key passed.")
        klyqa_acc = Klyqa_account(data_communicator)

    elif args_parsed.username is not None and args_parsed.username[0] in klyqa_accs:

        klyqa_acc = klyqa_accs[args_parsed.username[0]]
        if not klyqa_acc.access_token:
            asyncio.run(
                klyqa_acc.login(print_onboarded_devices=print_onboarded_devices)
            )
            LOGGER.debug("login finished")

    else:
        try:
            LOGGER.debug("login")
            host = PROD_HOST
            if args_parsed.test:
                host = TEST_HOST
            klyqa_acc = Klyqa_account(
                data_communicator,
                args_parsed.username[0] if args_parsed.username else "",
                args_parsed.password[0] if args_parsed.password else "",
                host,
            )

            asyncio.run(
                klyqa_acc.login(print_onboarded_devices=print_onboarded_devices)
            )
            klyqa_accs[args_parsed.username[0]] = klyqa_acc
        except:
            LOGGER.error("Error during login.")
            sys.exit(1)

        LOGGER.debug("login finished")
    exit_ret = 0

    if (
        loop.run_until_complete(
            klyqa_acc.send_to_devices_wrapped(
                args_parsed, args_in.copy(), timeout_ms=timeout_ms
            )
        )
        > 0
    ):
        exit_ret = 1

    klyqa_acc.shutdown()

    sys.exit(exit_ret)


if __name__ == "__main__":
    main()
