#!/usr/bin/env python3
"""Klyqa control client."""
from __future__ import annotations

###################################################################
#
# Interactive Klyqa Control commandline client
#
# Company: QConnex GmbH / Klyqa
# Author: Frederick Stallmeyer
#
# E-Mail: frederick.stallmeyer@gmx.de
#
# nice to haves/missing:
#   -   list cloud connected devices in discovery.
#   -   offer for selected devices possible commands and arguments in interactive
#       mode based on their device profile
#   -   Implementation for the different device config profile versions and
#       check on send.
#   -   start scene support in cloud mode
#
# current bugs:
#  - vc1 interactive command selection support.
#  - interactive light selection, command not applied
#
###################################################################

import getpass
import random
import socket
import sys
import json
import datetime
import argparse
import select
import logging
import time
from typing import TypeVar, Any, TypedDict
from xml.dom.pulldom import default_bufsize

import requests, uuid, json
from threading import Thread, Event
from collections import ChainMap
from enum import Enum
import asyncio, aiofiles
import functools, traceback
from asyncio.exceptions import CancelledError, TimeoutError
from collections.abc import Callable

from klyqa_ctl.devices.device import *
from klyqa_ctl.devices.light import *
from klyqa_ctl.devices.light.commands import add_command_args_bulb, process_args_to_msg_lighting
from klyqa_ctl.devices.vacuum import *
from klyqa_ctl.devices.vacuum import process_args_to_msg_cleaner
from klyqa_ctl.general.connections import *
from klyqa_ctl.general.general import *
from klyqa_ctl.general.message import *
from klyqa_ctl.general.parameters import get_description_parser

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
except:
    from Crypto.Cipher import AES  # provided by pycryptodome

from typing import TypeVar

tcp_udp_port_lock: AsyncIOLock = AsyncIOLock.instance()
NoneType: Type[None] = type(None)

Device_TCP_return = Enum(
    "Device_TCP_return",
    "sent answered wrong_uid no_uid_device wrong_aes tcp_error unknown_error timeout nothing_done sent_error no_message_to_send device_lock_timeout err_local_iv missing_aes_key response_error",
)


ReturnTuple = TypeVar("ReturnTuple", tuple[int, str], tuple[int, dict])


AES_KEYs: dict[str, bytes] = {}

S = TypeVar("S", argparse.ArgumentParser, type(None))


class Klyqa_account:
    """

    Klyqa account
    * rest access token
    * devices
    * account settings
    * local communication
    * cloud communication

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
        self,
        data_communicator: Data_communicator,
        username: str = "",
        password: str = "",
        host: str = "",
        interactive_prompts: bool = False,
        offline: bool = False,
        device_configs: dict = {},
    ) -> None:
        """! Initialize the account with the login data, tcp, udp datacommunicator and tcp
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
        self.interactive_prompts = interactive_prompts
        self.offline = offline
        self.device_configs = device_configs

    def backend_connected(self) -> bool:
        return self.access_token != ""

    async def update_device_configs(self):
        product_ids: set[str] = {
            device.ident.product_id
            for uid, device in self.devices.items()
            if device.ident and device.ident.product_id
        }

        for product_id in list(product_ids):
            if self.device_configs and product_id in self.device_configs:
                continue
            LOGGER.debug("Try to request device config from server.")
            try:
                config = await self.request(
                    "config/product/" + product_id,
                    timeout=30,
                )
                device_config: Device_config | None = config
                if not isinstance(self.device_configs, dict):
                    self.device_configs = {}
                self.device_configs[product_id] = device_config
            except:
                pass

    async def device_handle_local_tcp(
        self, device: KlyqaDevice | None, connection: LocalConnection
    ) -> Type[Device_TCP_return]:
        """! Handle the incoming tcp connection to the device."""
        return_state: Type[Device_TCP_return] = Device_TCP_return.nothing_done
        
        task: asyncio.Task[Any] | None = asyncio.current_task()
        TASK_NAME: str = task.get_name() if task is not None else ""

        try:
            r_device: RefParse = RefParse(device)
  
            task: asyncio.Task[Any] | None = asyncio.current_task()

            if task is not None:
                LOGGER.debug(
                    f"{task.get_name()} - started tcp device {connection.address['ip']} "
                )
            try:
                return_state = await self.aes_handshake_and_send_msgs(
                    r_device, connection = connection
                )
                device = r_device.ref
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
                    f"{TASK_NAME} finished tcp device {connection.address['ip']}, return_state: {return_state}"
                )

                if connection.socket is not None:
                    connection.socket.shutdown(socket.SHUT_RDWR)
                    connection.socket.close()
                    connection.socket = None
                self.current_addr_connections.remove(str(connection.address["ip"]))
                if device:
                    LOGGER.debug(f"{TASK_NAME} tcp closed for {device.u_id}. Return state: {return_state}")

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

    async def search_and_send_to_device(
        self, proc_timeout_secs=DEFAULT_MAX_COM_PROC_TIMEOUT_SECS
    ) -> bool:
        """! Send broadcast and make tasks for incoming tcp connections.

        Params:
            proc_timeout_secs:   max timeout in seconds for a device communication handle process

        Returns:
            true:  on success
            false: on exception or error
        """
        loop = asyncio.get_event_loop()

        try:
            if not self.data_communicator.tcp or not self.data_communicator.udp:
                await self.data_communicator.bind_ports()
            while not self.search_and_send_loop_task_end_now:
                if not self.data_communicator.tcp or not self.data_communicator.udp:
                    break
                # for debug cursor jump:
                a = False
                if a:
                    break

                if self.message_queue:

                    read_broadcast_response = True
                    try:
                        LOGGER.debug("Broadcasting QCX-SYN Burst")
                        self.data_communicator.udp.sendto(
                            "QCX-SYN".encode("utf-8"), ("255.255.255.255", 2222)
                        )

                    except:
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
                                        new_task, timeout=proc_timeout_secs
                                    )
                                )

                                LOGGER.debug(
                                    f"Address {connection.address['ip']} process task created."
                                )
                                self.__tasks_undone.append(
                                    (new_task, datetime.datetime.now())
                                )
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
                                seconds=proc_timeout_secs
                            ):
                                task.cancel(
                                    msg=f"timeout of process of {proc_timeout_secs} seconds."
                                )
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
                task.cancel(msg=f"Search and send loop cancelled.")
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
                self.search_and_send_loop_task.cancel(
                    msg=f"Shutdown search and send loop."
                )
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
        send_msgs: list[tuple[Any]],
        target_device_uid: str,
        args: argparse.Namespace,
        callback: Callable | None = None,
        time_to_live_secs: float = -1.0,
        started: datetime.datetime = datetime.datetime.now(),
    ) -> bool:

        loop = asyncio.get_event_loop()
        # self.message_queue_new.append((send_msg, target_device_uid, args, callback, time_to_live_secs, started))

        if not send_msgs and callback is not None:
            LOGGER.error(f"No message queue to send in message to {target_device_uid}!")
            await callback(None, target_device_uid)
            return False
        
        # send_msg: tuple = send_msgs[0]
        # send_msg: tuple
        # send_msgs_cor: list[tuple] = []
        # timeout_secs: float = 0.0
        
        # for send_msg in send_msgs:
            
        #     text: str; ts_ms: int # timeout between local sending msgs
        #     check_func: Callable | None = None
        #     if len(send_msg) and len(send_msg) == 2:
        #         text, ts_ms = send_msg
        #     else:
        #         text, ts_ms, check_func = send_msg
        #     send_msgs_cor.append((text, check_func))
        #     if ts_ms > 0 and ts_ms > timeout_secs*1000:
        #         timeout_secs = ts_ms/1000

        msg: Message = Message(
            started = datetime.datetime.now(),
            msg_queue = send_msgs,
            args = args,
            target_uid = target_device_uid,
            callback = callback,
            # local_pause_after_answer_secs = timeout_secs,
            time_to_live_secs = time_to_live_secs,
        )

        if not await msg.check_msg_ttl():
            return False

        LOGGER.debug(
            f"new message {msg.msg_counter} target {target_device_uid} {send_msgs}"
        )

        self.message_queue.setdefault(target_device_uid, []).append(msg)

        if self.__read_tcp_task:
            # if still waiting for incoming connections, restart the process
            # with a new udp broadcast
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

    async def login_cache(self) -> bool:

        if not self.username:
            try:
                user_name_cache: dict
                cached: bool
                user_name_cache, cached = await async_json_cache(
                    None, f"last_username.json"
                )
                if cached:
                    self.username = user_name_cache["username"]
                    LOGGER.info("Using Klyqa account %s.", self.username)
                else:
                    LOGGER.error("Username missing, username cache empty.")

                    if self.interactive_prompts:
                        self.username = input(
                            " Please enter your Klyqa Account username (will be cached for the script invoke): "
                        )
                    else:
                        LOGGER.info("Missing Klyqa account username. No login.")
                        return False

                # async with aiofiles.open(
                #     os.path.dirname(sys.argv[0]) + f"/last_username", mode="r"
                # ) as f:
                #     self.username = str(await f.readline()).strip()
            except:
                return False
            
        try:
            acc_settings: dict
            cached: bool
            acc_settings, cached = await async_json_cache(
                None, f"{self.username}.acc_settings.cache.json"
            )
            if cached:
                self.acc_settings = acc_settings
                # self.username, self.password = (user_acc_cache["user"], user_acc_cache["password"])
                if not self.password:
                    self.password = self.acc_settings["password"]

            if not self.password:
                raise Exception()

            # async with aiofiles.open(
            #     os.path.dirname(sys.argv[0]) + f"/last_username", mode="r"
            # ) as f:
            #     self.username = str(await f.readline()).strip()
        except:
            if self.interactive_prompts:
                self.password = getpass.getpass(
                    prompt=" Please enter your Klyqa Account password (will be saved): ",
                    stream=None,
                )
            else:
                LOGGER.error("Missing Klyqa account password. Login failed.")
                return False

        return True

    async def login(self, print_onboarded_devices=False) -> bool:
        """! Login on klyqa account, get account settings, get onboarded device profiles,
        print all devices if parameter set.

        Params:
            print_onboarded_devices:   print onboarded devices from the klyqa account to the stdout

        Returns:
            true:  on success of the login
            false: on error
        """
        # global device_configs
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        if not await self.login_cache():
            return False

        acc_settings_cache: dict = {}

        if not self.offline and (
            self.username is not None and self.password is not None
        ):
            login_response: requests.Response | None = None
            try:
                login_data: dict[str, str] = {
                    "email": self.username,
                    "password": self.password,
                }

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
                login_json: dict = json.loads(login_response.text)
                self.access_token = str(login_json.get("accessToken"))
                # self.acc_settings = await loop.run_in_executor(
                #     None, functools.partial(self.request, "settings", timeout=30)
                # )
                acc_settings = await self.request("settings", timeout=30)
                if acc_settings:
                    self.acc_settings = acc_settings

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

                # await async_json_cache(
                #     {"user": self.username, "password": self.password}, f"last.user.account.json"
                # )
                # async with aiofiles.open(
                #     os.path.dirname(sys.argv[0]) + f"/last_username", mode="w"
                # ) as f:
                #     await f.write(self.username)

            except Exception as e:
                pass

        await async_json_cache({"username": self.username}, f"last_username.json")

        try:
            klyqa_acc_string: str = "Klyqa account " + self.username + ". Onboarded devices:"
            sep_width: int = len(klyqa_acc_string)

            if print_onboarded_devices:
                print(sep_width * "-")
                print(klyqa_acc_string)
                print(sep_width * "-")

            queue_printer: EventQueuePrinter = EventQueuePrinter()

            def device_request_and_print(device_sets) -> None:
                state_str: str = (
                    f'Name: "{device_sets["name"]}"'
                    + f'\tAES-KEY: {device_sets["aesKey"]}'
                    + f'\tUnit-ID: {device_sets["localDeviceId"]}'
                    + f'\tCloud-ID: {device_sets["cloudDeviceId"]}'
                    + f'\tType: {device_sets["productId"]}'
                )
                cloud_state: dict[str, Any] | None = None

                device: KlyqaDevice
                if ".lighting" in device_sets["productId"]:
                    device = KlyqaBulb()
                elif ".cleaning" in device_sets["productId"]:
                    device = KlyqaVC()
                else:
                    return
                device.u_id = format_uid(device_sets["localDeviceId"])
                device.acc_sets = device_sets

                self.devices[format_uid(device_sets["localDeviceId"])] = device

                async def req() -> dict[str, Any] | None:
                    try:
                        ret: dict[str, Any] | None = await self.request(
                            f'device/{device_sets["cloudDeviceId"]}/state',
                            timeout=30,
                        )
                        return ret
                    except Exception as e:
                        return None

                if self.backend_connected():
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
                        LOGGER.info(f'No answer for cloud device state request {device_sets["localDeviceId"]}')

                if print_onboarded_devices:
                    queue_printer.print(state_str)

            device_state_req_threads = []

            product_ids: set[str] = set()
            if self.acc_settings and "devices" in self.acc_settings:
                for device_sets in self.acc_settings["devices"]:
                    
                    
                    thread: Thread = Thread(target=device_request_and_print, args=(device_sets,))
                    device_state_req_threads.append(thread)

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

            if not self.backend_connected():
                if not self.device_configs:
                    device_configs_cache, cached = await async_json_cache(
                        None, "device.configs.json"
                    )
                    if (
                        cached and not self.device_configs
                    ):
                        # using again not device_configs check cause asyncio await scheduling
                        LOGGER.info("Using devices config cache.")
                        if device_configs_cache:
                            self.device_configs = device_configs_cache

            elif self.backend_connected():

                def get_conf(id, device_configs) -> None:
                    async def req() -> dict[str, Any] | None:
                        try:
                            ret: dict[str, Any] | None = await self.request("config/product/" + id, timeout=30)
                            return ret
                        except:
                            return None

                    config: dict[str, Any] | None = asyncio.run(req())
                    if config:
                        device_config: Device_config = config
                        device_configs[id] = device_config

                if self.acc_settings and product_ids:
                    threads: list[Thread] = [
                        Thread(target=get_conf, args=(i, self.device_configs))
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

                device_configs_cache: dict[Any, Any]
                cached: bool
                
                device_configs_cache, cached = await async_json_cache(
                    self.device_configs, "device.configs.json"
                )
                if cached:
                    self.device_configs: dict[Any, Any] = device_configs_cache
                    LOGGER.info("No server reply for device configs. Using cache.")

            for uid in self.devices:
                if (
                    "productId" in self.devices[uid].acc_sets
                    and self.devices[uid].acc_sets["productId"] in self.device_configs
                ):
                    self.devices[uid].read_device_config(device_config = self.device_configs[
                        self.devices[uid].acc_sets["productId"]
                    ])
        except Exception as e:
            LOGGER.error("Error during login to klyqa: " + str(e))
            LOGGER.debug(f"{traceback.format_exc()}")
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
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
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
                raise Exception(response.text)
            answer = json.loads(response.text)
        except Exception:
            LOGGER.debug(f"{traceback.format_exc()}")
            answer = None
        return answer

    async def post(self, url, **kwargs) -> TypeJSON | None:
        """Post requests."""
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        answer: TypeJSON | None = None
        try:
            response: requests.Response = await loop.run_in_executor(
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
        except:
            LOGGER.debug(f"{traceback.format_exc()}")
            answer = None
        return answer

    async def shutdown(self) -> None:
        """Logout again from klyqa account."""
        # loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
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
                requests.post(
                    self.host + "/auth/logout", headers=self.get_header_default()
                )
                self.access_token = ""
            except Exception:
                LOGGER.warning("Couldn't logout.")
                
        # asyncio.run_until_complete(self.search_and_send_loop_task_stop())
        # asyncio.run(self.search_and_send_loop_task_stop())
        await self.search_and_send_loop_task_stop()

    async def aes_wait_iv_pkg_one(self, connection, pkg, device) -> None:
        """Set aes key for the connection from the first package."""
        # Receive the remote initial vector (iv) for aes encrypted communication.

        connection.remoteIv = pkg
        connection.received_packages.append(pkg)
        if not connection.aes_key:
            LOGGER.debug(
                f"{task_name()} - "
                + "Missing AES key. Probably not in onboarded devices. Provide AES key with --aes [key]! "
                + str(device.u_id)
            )
            return Device_TCP_return.missing_aes_key
        connection.sendingAES = AES.new(
            connection.aes_key,
            AES.MODE_CBC,
            iv=connection.localIv + connection.remoteIv,
        )
        connection.receivingAES = AES.new(
            connection.aes_key,
            AES.MODE_CBC,
            iv=connection.remoteIv + connection.localIv,
        )

        connection.state = "CONNECTED"
        
    async def message_answer_package(self, connection, pkg, device, msg_sent) -> Device_TCP_return | int:
        """Message answer package"""
        
        return_val: Device_TCP_return | int = 0
        # Receive encrypted answer for sent message.

        cipher: bytes = pkg

        plain: bytes = connection.receivingAES.decrypt(cipher)
        connection.received_packages.append(plain)
        if msg_sent is not None and not msg_sent.state == Message_state.answered:
            msg_sent.answer = plain
            json_response = {}
            try:
                plain_utf8: str = plain.decode()
                json_response = json.loads(plain_utf8)
                device.save_device_message(json_response)
                connection.sent_msg_answer = json_response
                connection.aes_key_confirmed = True
                LOGGER.debug(
                    f"{task_name()} - device uid {device.u_id} aes_confirmed {connection.aes_key_confirmed}"
                )
            except:
                LOGGER.error(
                    f"{task_name()} - Could not load json message from device: "
                )
                LOGGER.error(f"{task_name()} - {pkg}")
                return Device_TCP_return.response_error

            msg_sent.answer_utf8 = plain_utf8
            msg_sent.answer_json = json_response
            msg_sent.state = Message_state.answered
            msg_sent.answered_datetime = datetime.datetime.now()
            return_val = Device_TCP_return.answered

            device.recv_msg_unproc.append(msg_sent)
            device.process_msgs()
                    
            if msg_sent and not msg_sent.callback is None and device is not None:
                await msg_sent.callback(msg_sent, device.u_id)
                LOGGER.debug(
                    f"device {device.u_id} answered msg {msg_sent.msg_queue}"
                )
            msg_sent = None

        LOGGER.debug(
            f"{task_name()} - Request's reply decrypted: " + str(plain)
        )
        return return_val

    async def aes_handshake_and_send_msgs(
        self,
        r_device: RefParse,
        # r_msg: RefParse,
        connection: LocalConnection,
        use_dev_aes: bool = False,
        timeout_ms: int = 11000,  # currently only used for pause timeout between sending messages if multiple for device in queue to send.
    ) -> Type[Device_TCP_return.__class__]:
        """
        FIX: return type! sometimes return value sometimes tuple...

        Finish AES handshake.
        Getting the identity of the device.
        Send the commands in message queue to the device with the device u_id or to any device.

        Params:
            device: Device - (initial) device object with the tcp connection
            target_device_uid - If given device_uid only send commands when the device unit id equals the target_device_uid
            discover_mode - if True do the process to any device unit id.

        Returns: tuple[int, dict] or tuple[int, str]
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
        task: asyncio.Task[Any] | None = asyncio.current_task()
        TASK_NAME: str = task.get_name() if task is not None else ""

        data: bytes = b""
        last_send: datetime.datetime = datetime.datetime.now()
        connection.socket.settimeout(0.001)
        pause: datetime.timedelta = datetime.timedelta(milliseconds=0)
        elapsed: datetime.timedelta = datetime.datetime.now() - last_send

        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        return_val: Type[Device_TCP_return.__class__] = Device_TCP_return.nothing_done

        msg_sent: Message | None = None
        communication_finished: bool = False        
        pause_after_send: int

        async def __send_msg() -> Message | None:
            nonlocal last_send, pause, return_val, device, msg_sent, pause_after_send
            
            def rm_msg(msg) -> None:
                if not device:
                    return
                try:
                    LOGGER.debug(f"{TASK_NAME} - rm_msg()")
                    self.message_queue[device.u_id].remove(msg)
                    msg.state = Message_state.sent

                    if (
                        device.u_id in self.message_queue
                        and not self.message_queue[device.u_id]
                    ):
                        del self.message_queue[device.u_id]
                except:
                    LOGGER.debug(f"{TASK_NAME} - {traceback.format_exc()}")

            return_val = Device_TCP_return.sent
            
            send_next: bool = elapsed >= pause
            sleep: float = (pause - elapsed).total_seconds()
            if sleep > 0:
                await asyncio.sleep(sleep)
        
            ## check how the answer come in and how they can be connected to the messages that has been sent.
                
            if (
                send_next and device
                and device.u_id in self.message_queue
                and len(self.message_queue[device.u_id]) > 0
            ):
                msg: Message = self.message_queue[device.u_id][0]
                
                LOGGER.debug(
                    f"{TASK_NAME} - Process msg to send '{msg.msg_queue}' to device '{device.u_id}'."
                )
                j: int = 0
                
                if msg.state == Message_state.unsent:
                    
                    while j < len(msg.msg_queue):
                            
                        text: str
                        if len(msg.msg_queue[j]) and len(msg.msg_queue[j]) == 2:
                            text, pause_after_send = msg.msg_queue[j]
                            msg.msg_queue_sent.append(text)
                        else:
                            text, pause_after_send, check_func = msg.msg_queue[j]
                            msg.msg_queue_sent.append(text)
                            if not check_func(device = device):
                                # some parameter check in the message failed, remove message from the queue
                                rm_msg(msg)
                                # stop processing further the message
                                break

                        pause = datetime.timedelta(milliseconds = pause_after_send)
                        try:
                            if await loop.run_in_executor(None, send_msg, text, device, connection):
                                msg_sent = msg 
                                last_send = datetime.datetime.now()
                                j = j + 1
                                # don't process the next message, but if
                                # still elements in the msg_queue send them as well
                                send_next = False
                                # break
                            else:
                                raise Exception(f"TCP socket connection broken (uid: {device.u_id})")
                        except:
                            LOGGER.debug(f"{TASK_NAME} - {traceback.format_exc()}")
                            break
       
                    if len(msg.msg_queue) == len(msg.msg_queue_sent):
                        msg.state = Message_state.sent
                        # all messages sent to devices, break now for reading response
                        rm_msg(msg)
                else:
                    rm_msg(msg)
                    
        connection.socket.settimeout(1)
        while (device.u_id == "no_uid" or type(device) == KlyqaDevice or 
               device.u_id in self.message_queue or msg_sent) and not communication_finished:
            try:
                data = await loop.run_in_executor(None, connection.socket.recv, 4096)
                if len(data) == 0:
                    LOGGER.debug(f"{TASK_NAME} - EOF")
                    return Device_TCP_return.tcp_error
            except socket.timeout:
                LOGGER.debug(f"{TASK_NAME} - aes_send_recv timeout")
                await asyncio.sleep(0.01)
            except:
                LOGGER.debug(f"{TASK_NAME} - {traceback.format_exc()}")
                return Device_TCP_return.unknown_error

            elapsed = datetime.datetime.now() - last_send
            
            if msg_sent and msg_sent.state == Message_state.answered:
                msg_sent = None

            if connection.state == "CONNECTED" and msg_sent is None:
                try:
                    await __send_msg()
                except:
                    LOGGER.debug(traceback.format_exc())
                    return Device_TCP_return.unknown_error

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
                    except:
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
                        if ".lighting" in ident.product_id:
                            self.devices[device.u_id] = KlyqaBulb()
                        elif ".cleaning" in ident.product_id:
                            self.devices[device.u_id] = KlyqaVC()

                    # cached client device (self.devices), incoming device object created on tcp connection acception
                    if not device.u_id in self.devices:
                        return Device_TCP_return.nothing_done
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

                    found: str = ""
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

                    if is_new_device:
                        LOGGER.info(
                            f"%sFound device {found}",
                            f"{TASK_NAME} - " if LOGGER.level == logging.DEBUG else "",
                        )
                    else:
                        LOGGER.debug(
                            f"%sFound device {found}",
                            f"{TASK_NAME} - " if LOGGER.level == logging.DEBUG else "",
                        )

                    if "all" in AES_KEYs:
                        connection.aes_key = AES_KEYs["all"]
                    elif use_dev_aes or "dev" in AES_KEYs:
                        connection.aes_key = AES_KEY_DEV
                    elif isinstance(AES_KEYs, dict) and device.u_id in AES_KEYs:
                        connection.aes_key = AES_KEYs[device.u_id]
                    try:
                        if connection.socket is not None:
                            # for prod do in executor for more asyncio schedule task executions
                            # await loop.run_in_executor(None, connection.socket.send, bytes([0, 8, 0, 1]) + connection.localIv)
                            if not connection.socket.send(
                                bytes([0, 8, 0, 1]) + connection.localIv
                            ):
                                return Device_TCP_return.err_local_iv
                    except:
                        return Device_TCP_return.err_local_iv

                if connection.state == "WAIT_IV" and pkgType == 1:
                    await self.aes_wait_iv_pkg_one(connection, pkg, device)

                elif connection.state == "CONNECTED" and pkgType == 2:
                    ret: Device_TCP_return | int = await self.message_answer_package(connection, pkg, device, msg_sent)
                    if type(ret) == Device_TCP_return: # != 0:
                        return_val = ret # type: ignore
                        if return_val == Device_TCP_return.answered:
                            communication_finished = True
                    break
                else:
                    LOGGER.debug(
                        f"{TASK_NAME} - No answer to process. Waiting on answer of the device ... "
                    )
        return return_val

    async def request_account_settings_eco(self, scan_interval: int = 60) -> bool:
        if not await self.__acc_settings_lock.acquire():
            return False
        ret: bool = True
        try:
            now: datetime.datetime = datetime.datetime.now()
            if not self._settings_loaded_ts or (
                now - self._settings_loaded_ts
                >= datetime.timedelta(seconds=scan_interval)
            ):
                """look that the settings are loaded only once in the scan interval"""
                await self.request_account_settings()
        finally:
            self.__acc_settings_lock.release()
        return ret

    async def request_account_settings(self) -> None:
        try:
            acc_settings: dict[str, Any] | None = await self.request("settings")
            if acc_settings:
                self.acc_settings = acc_settings
        except:
            pass
        
        
    async def discover_devices(self, args, message_queue_tx_local, target_device_uids) -> None:
        """Discover devices."""

        print(sep_width * "-")
        print("Search local network for devices ...")
        print(sep_width * "-")

        discover_end_event: asyncio.Event = asyncio.Event()
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


    def device_name_to_uid(self, args: argparse.Namespace, target_device_uids: set[str]) -> bool:
        """Set target device uid by device name argument."""
        
        if not self.acc_settings:
            LOGGER.error(
                'Missing account settings to resolve device name  "'
                + args.device_name
                + '"to unit id.'
            )
            return False
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
            return False
        else:
            target_device_uids.add(format_uid(dev[0]))
        return True
    
    
    async def select_device(self, args, send_started_local) -> str | set[str]:
        """Interactive select device."""
        
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
        count: int = 1
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
            cloud: str = (
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
            target_device_uids_lcl: set[str] = set()
            if device_num_s == "a":
                return set(b.u_id for b in device_items)
            else:
                for bulb_num in device_num_s.split(","):
                    bulb_num_nr: int = int(bulb_num)
                    if bulb_num_nr > 0 and bulb_num_nr < count:
                        target_device_uids_lcl.add(
                            device_items[bulb_num_nr - 1].u_id
                        )
            return target_device_uids_lcl

        """ no devices found. Exit script. """
        sys.exit(0)
    
    async def send_to_devices(
        self,
        args: argparse.Namespace,
        args_in: list[Any],
        udp: socket.socket | None = None,
        tcp: socket.socket | None = None,
        timeout_ms: int = 5000,
        async_answer_callback: Callable[[Message, str], Any] | None = None,
    ) -> str | bool | int | set:
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
            global sep_width  # , device_configs

            loop = asyncio.get_event_loop()

            send_started: datetime.datetime = datetime.datetime.now()

            add_command_args_ch: dict[str, Callable[..., Any]] = {
                DeviceType.lighting.name: add_command_args_bulb,
                DeviceType.cleaner.name: add_command_args_cleaner,
            }
            add_command_args: Callable[..., Any] = add_command_args_ch[args.type]

            if args.dev:
                args.local = True
                args.tryLocalThanCloud = False
                args.cloud = False

            if args.debug:
                LOGGER.setLevel(level=logging.DEBUG)
                logging_hdl.setLevel(level=logging.DEBUG)
                # coloredlogs.install(logging.DEBUG, logger=LOGGER, reconfigure=True)
                # logging_hdl_clr.setLevel(level=logging.DEBUG)

            if args.cloud or args.local:
                args.tryLocalThanCloud = False

            if args.aes is not None:
                AES_KEYs["all"] = bytes.fromhex(args.aes[0])

            target_device_uids: set[str] = set()

            message_queue_tx_local: list[Any] = []
            message_queue_tx_state_cloud: list[Any] = []
            message_queue_tx_command_cloud: list[Any] = []

            if args.device_name is not None:
                if not self.device_name_to_uid(args, target_device_uids):
                    return False

            if args.device_unitids is not None:
                target_device_uids = set(
                    map(format_uid, set(args.device_unitids[0].split(",")))
                )
                print("Send to device: " + ", ".join(args.device_unitids[0].split(",")))

            if not args.selectDevice and self.backend_connected():
                await self.update_device_configs()

            ### device specific commands ###

            async def send_to_devices_cb(args: argparse.Namespace) -> str | bool | int | set:
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

            success: bool = True
            to_send_device_uids: set[str] = set()
            
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

                    # message_queue_tx_local.reverse()
                    send_started_local: datetime.datetime = datetime.datetime.now()

                    if args.discover:
                        await self.discover_devices(args, message_queue_tx_local, target_device_uids)
                    # else:
                    msg_wait_tasks: dict[str, asyncio.Task] = {}

                    to_send_device_uids = target_device_uids.copy()

                    async def sl(uid) -> None:
                        """Sleep task for timeout."""
                        try:
                            await asyncio.sleep(timeout_ms / 1000)
                        except CancelledError as e:
                            LOGGER.debug(f"sleep uid {uid} cancelled.")
                        except Exception as e:
                            pass

                    for uid in target_device_uids:
                        try:
                            msg_wait_tasks[uid] = loop.create_task(sl(uid))
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

                    for uid in target_device_uids:
                        
                        await self.set_send_message(
                            send_msgs = message_queue_tx_local.copy(),
                            target_device_uid = uid,
                            args = args,
                            callback=async_answer_callback_local,
                            time_to_live_secs=(timeout_ms / 1000),
                        )

                    for uid in target_device_uids:
                        try:
                            LOGGER.debug(f"wait for send task {uid}.")
                            await asyncio.wait([msg_wait_tasks[uid]])
                            LOGGER.debug(f"wait for send task {uid} end.")
                            # await asyncio.wait_for(msg_wait_tasks[i], timeout=(timeout_ms / 1000))
                        except CancelledError as e:
                            LOGGER.debug(f"sleep wait for uid {uid} cancelled.")
                        except Exception as e:
                            pass

                    LOGGER.debug(f"wait for all target device uids done.")

                    if args.selectDevice:
                        return await self.select_device(args, send_started_local)

                if target_device_uids and len(to_send_device_uids) > 0:
                    """error"""
                    sent_locally_error: str = (
                        "The commands " + str([f'{k}={v}' for k, v in vars(args).items() if v])
                        + " failed to send locally to the device(s): "
                        + ", ".join(to_send_device_uids)
                    )
                    if args.tryLocalThanCloud:
                        LOGGER.info(sent_locally_error)
                    else:
                        LOGGER.error(sent_locally_error)
                    success = False

            if args.cloud or args.tryLocalThanCloud:
                success = await self.cloud_send(args, target_device_uids, to_send_device_uids, timeout_ms, message_queue_tx_state_cloud, message_queue_tx_command_cloud)

            if success and scene:
                scene_start_args: list[str] = [
                    args.type,
                    "--routine_id",
                    "0",
                    "--routine_start",
                ]

                orginal_args_parser: argparse.ArgumentParser = get_description_parser()
                scene_start_args_parser: argparse.ArgumentParser = get_description_parser()

                add_config_args(parser=orginal_args_parser)
                add_config_args(parser=scene_start_args_parser)
                add_command_args(parser=scene_start_args_parser)

                original_config_args_parsed, _ = orginal_args_parser.parse_known_args(
                    args=args_in
                )

                scene_start_args_parsed = scene_start_args_parser.parse_args(
                    scene_start_args, namespace=original_config_args_parsed
                )

                async def async_print_answer(msg: Message, uid: str) -> None:
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

                ret: str | bool | int | set = await self.send_to_devices(
                    scene_start_args_parsed,
                    args_in,
                    udp = udp,
                    tcp = tcp,
                    timeout_ms = timeout_ms
                    - int((datetime.datetime.now() - send_started).total_seconds())
                    * 1000,  # 3000
                    async_answer_callback=async_print_answer,
                )

                if isinstance(ret, bool) and ret:
                    success = True
                else:
                    LOGGER.error(f"Couldn't start scene {scene[0]}.")
                    success = False

            return success
        except Exception as e:
            LOGGER.debug(traceback.format_exc())
            return False
    
    async def cloud_send(self, args: argparse.Namespace, target_device_uids: set[str], to_send_device_uids: set[str], timeout_ms: int, message_queue_tx_state_cloud: list, message_queue_tx_command_cloud: list) -> bool:
        """Cloud message processing."""
        
        queue_printer: EventQueuePrinter = EventQueuePrinter()
        response_queue: list[Any] = []
        success: bool = False
        loop: asyncio.AbstractEventLoop= asyncio.get_event_loop()

        async def _cloud_post(
            device: KlyqaDevice, json_message, target: str
        ) -> None:
            cloud_device_id: str = device.acc_sets["cloudDeviceId"]
            unit_id: str = format_uid(device.acc_sets["localDeviceId"])
            LOGGER.info(
                f"Post {target} to the device '{cloud_device_id}' (unit_id: {unit_id}) over the cloud."
            )
            resp: dict[str, dict[str, Any] | None] = {
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

        async def cloud_post(device: KlyqaDevice, json_message, target: str) -> int:
            if not await device.use_lock():
                LOGGER.error(
                    f"Couldn't get use lock for device {device.get_name()})"
                )
                return 1
            try:
                await _cloud_post(device, json_message, target)
            except CancelledError as e:
                LOGGER.error(
                    f"Cancelled cloud send "
                    + (device.u_id if device.u_id else "")
                    + "."
                )
            finally:
                await device.use_unlock()
            return 0

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
        return success

    async def send_to_devices_wrapped(self, args_parsed, args_in, timeout_ms=5000) -> int:
        """Set up broadcast port and tcp reply connection port."""

        if args_parsed.cloud or args_parsed.local:
            args_parsed.tryLocalThanCloud = False

        if args_parsed.debug:
            LOGGER.setLevel(level=logging.DEBUG)
            logging_hdl.setLevel(level=logging.DEBUG)
            # coloredlogs.install(logging.DEBUG, logger=LOGGER, reconfigure=True)
            # logging_hdl_clr.setLevel(level=logging.DEBUG)

        if args_parsed.dev:
            AES_KEYs["dev"] = AES_KEY_DEV

        local_communication = args_parsed.local or args_parsed.tryLocalThanCloud

        if local_communication:
            if not await self.data_communicator.bind_ports():
                return 1

        exit_ret: int = 0

        async def async_answer_callback(msg, uid) -> None:
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
            args_in ,
            udp = self.data_communicator.udp,
            tcp = self.data_communicator.tcp,
            timeout_ms = timeout_ms,
            async_answer_callback = async_answer_callback,
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

        return exit_ret

async def tests(klyqa_acc: Klyqa_account) -> int:
        
    if not await klyqa_acc.data_communicator.bind_ports():
        return 1
    
    started: datetime.datetime = datetime.datetime.now()
    
    uids: list[str] = [
        "29daa5a4439969f57934",
        # "00ac629de9ad2f4409dc",
        # "04256291add6f1b414d1",
        # "cd992e921b3646b8c18a",
        # "1a8379e585321fdb8778"
        ]
    
    messages_answered: int = 0
    messages_sent: int = 0
    
    tasks: list[asyncio.Task] = []
    for u_id in uids:
        args_all: list[list[str]] = []
        # args_all.append(["--request"])
        args_all.append(["--color", str(random.randrange(0, 255)), str(random.randrange(0, 255)), str(random.randrange(0, 255))])
        # args_all.append(["--temperature", str(random.randrange(2000, 6500))])
        # args_all.append(["--brightness", str(random.randrange(0, 100))])
        # args_all.append(["--WW"])
        
        async def send_answer_cb(msg: Message, uid: str) -> None:
            nonlocal messages_answered
            if msg.answer_utf8:
                messages_answered = messages_answered + 1
                LOGGER.debug("Send_answer_cb %s", str(uid))
                LOGGER.info("Message answer %s: %s",msg.target_uid, 
                            json.dumps(json.loads(msg.answer_utf8), sort_keys=True, indent=4)
                            if msg else "empty msg")
            else:
                LOGGER.info("MSG-TTL: No answer from %s", uid)
        
        for args in args_all:

            parser: argparse.ArgumentParser = get_description_parser()
            
            args.extend(["--debug", "--local", "--device_unitids", f"{u_id}"])

            args.insert(0, DeviceType.lighting.name)
            add_config_args(parser=parser)
            add_command_args_bulb(parser=parser)

            args_parsed: argparse.Namespace = parser.parse_args(args=args)

            new_task: asyncio.Task[Any] = asyncio.create_task(
                klyqa_acc.send_to_devices(
                    args_parsed,
                    args,
                    async_answer_callback=send_answer_cb,
                    timeout_ms=4111 * 1000,
                )
            )
            messages_sent = messages_sent + 1
            # await asyncio.wait([new_task]) # single task debug
            # await asyncio.sleep(0.1)
            tasks.append(new_task)
        
    for task in tasks:
        try:
            await asyncio.wait([task], timeout=0.1)
        except asyncio.TimeoutError:
            pass
        
    for task in tasks:
        try:
            # await asyncio.wait([task])
            await task
        except asyncio.TimeoutError:
            pass
    
    LOGGER.info("End. Messages sent: %s, Messages answered: %s", messages_sent, messages_answered)
    time_run: datetime.timedelta = datetime.datetime.now() - started
    LOGGER.info("Time diff run: %s", time_run)
    return 0


async def main() -> None:
    """Main function."""
    
    klyqa_accs: dict[str, Klyqa_account] | None = None
    if not klyqa_accs:
        klyqa_accs = dict()

    parser: argparse.ArgumentParser = get_description_parser()

    add_config_args(parser=parser)

    args_in: list[str] = sys.argv[1:]

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

    if len(args_in) < 2 or config_args_parsed.help:
        parser.print_help()
        sys.exit(1)

    args_parsed = parser.parse_args(args=args_in)

    if args_parsed.version:
        print(KLYQA_CTL_VERSION)
        sys.exit(0)

    if not args_parsed:
        sys.exit(1)

    if args_parsed.debug:
        LOGGER.setLevel(level=logging.DEBUG)
        logging_hdl.setLevel(level=logging.DEBUG)
        # coloredlogs.install(logging.DEBUG, logger=LOGGER, reconfigure=True)
        # logging_hdl_clr.setLevel(level=logging.DEBUG)

    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS
    if args_parsed.timeout:
        timeout_ms = int(args_parsed.timeout[0]) * 1000

    server_ip: str = args_parsed.myip[0] if args_parsed.myip else "0.0.0.0"
    data_communicator: Data_communicator = Data_communicator(server_ip)

    print_onboarded_devices: bool = (
        not args_parsed.device_name
        and not args_parsed.device_unitids
        and not args_parsed.allDevices
    )

    klyqa_acc: Klyqa_account | None = None

    host: str = PROD_HOST
    if args_parsed.test:
        host = TEST_HOST

    if args_parsed.dev:
        if args_parsed.dev:
            LOGGER.info("development mode. Using default aes key.")
        klyqa_acc = Klyqa_account(
            data_communicator, offline = args_parsed.offline, interactive_prompts = True
        )
        # asyncio.run(klyqa_acc.login(print_onboarded_devices=False))
        await klyqa_acc.login(print_onboarded_devices=False)

    else:
        LOGGER.debug("login")
        if args_parsed.username is not None and args_parsed.username[0] in klyqa_accs:
            klyqa_acc = klyqa_accs[args_parsed.username[0]]
        else:
            klyqa_acc = Klyqa_account(
                data_communicator,
                args_parsed.username[0] if args_parsed.username else "",
                args_parsed.password[0] if args_parsed.password else "",
                host,
                offline=args_parsed.offline,
                interactive_prompts=True,
            )

        if not klyqa_acc.access_token:
            try:
                # if asyncio.run(
                #     klyqa_acc.login(print_onboarded_devices=print_onboarded_devices)
                # ):
                if await klyqa_acc.login(print_onboarded_devices=print_onboarded_devices):
                    LOGGER.debug("login finished")
                    klyqa_accs[klyqa_acc.username] = klyqa_acc
                else:
                    raise Exception()
            except:
                LOGGER.error("Error during login.")
                LOGGER.debug(f"{traceback.format_exc()}")
                sys.exit(1)
    exit_ret = 0

    if True:
        # loop.run_until_complete(tests(klyqa_acc))
        await tests(klyqa_acc)
    else:
        if (
            # loop.run_until_complete(
            #     klyqa_acc.send_to_devices_wrapped(
            #         args_parsed, args_in.copy(), timeout_ms=timeout_ms
            #     )
            # )
            await klyqa_acc.send_to_devices_wrapped(
                args_parsed, args_in.copy(), timeout_ms=timeout_ms)
            > 0
        ):
            exit_ret = 1

    # loop.run_until_complete(klyqa_acc.shutdown())
    await klyqa_acc.shutdown()

    LOGGER.debug("Closing ports")
    if klyqa_acc.data_communicator:
        klyqa_acc.data_communicator.shutdown()

    sys.exit(exit_ret)

if __name__ == "__main__":
    asyncio.run(main())
