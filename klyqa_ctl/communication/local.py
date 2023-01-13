"""Local communication"""

from __future__ import annotations
import argparse
from asyncio import CancelledError, Task
import datetime
import json
import select
import socket
from typing import Any, Callable
from klyqa_ctl.account import Account
from klyqa_ctl.devices import device

from klyqa_ctl.devices.device import *
from klyqa_ctl.devices.light import KlyqaBulb
from klyqa_ctl.devices.vacuum import KlyqaVC
from klyqa_ctl.general.general import *
from klyqa_ctl.general.message import Message_state

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
    from Cryptodome.Random import get_random_bytes  # pycryptodome
except:
    from Crypto.Cipher import AES  # provided by pycryptodome
    from Crypto.Random import get_random_bytes  # pycryptodome

AES_KEYs: dict[str, bytes] = {}

Device_TCP_return = Enum(
    "Device_TCP_return",
    "no_error sent answered wrong_uid no_uid_device wrong_aes tcp_error unknown_error timeout nothing_done sent_error no_message_to_send device_lock_timeout err_local_iv missing_aes_key response_error send_error",
)

def send_msg(msg: str, device: KlyqaDevice, connection: LocalConnection) -> bool:
    info_str: str = (
        (f"{task_name()} - " if LOGGER.level == 10 else "")
        + 'Sending in local network to "'
        + device.get_name()
        + '": '
        + json.dumps(json.loads(msg), sort_keys=True, indent=4)
    )

    LOGGER.info(info_str)
    plain: bytes = msg.encode("utf-8")
    while len(plain) % 16:
        plain = plain + bytes([0x20])

    if connection.sendingAES is None:
        return False
    
    cipher: bytes = connection.sendingAES.encrypt(plain)

    while connection.socket:
        try:
            connection.socket.send(
                bytes([len(cipher) // 256, len(cipher) % 256, 0, 2]) + cipher
            )
            return True
        except socket.timeout:
            LOGGER.debug("Send timed out, retrying...")
            pass
    return False

class LocalConnection:
    """LocalConnection"""

    state: str = "WAIT_IV"
    localIv: bytes = get_random_bytes(8)
    remoteIv: bytes = b""

    address: dict[str, str | int] = {"ip": "", "port": -1}
    socket: socket.socket | None = None
    received_packages: list[Any] = []
    sent_msg_answer: dict[str, Any] = {}
    aes_key_confirmed: bool = False
    aes_key: bytes = b""

    def __init__(self) -> None:
        self.state = "WAIT_IV"
        self.localIv = get_random_bytes(8)

        self.sendingAES: Any = None
        self.receivingAES: Any = None
        self.address = {"ip": "", "port": -1}
        self.socket = None
        self.received_packages = []
        self.sent_msg_answer = {}
        self.aes_key_confirmed = False
        self.aes_key = b""
        self.started: datetime.datetime = datetime.datetime.now()
        

class LocalCommunication:
    """Data communicator for local connection"""

    # Set of current accepted connections to an IP. One connection is most of the time
    # enough to send all messages for that device behind that connection (in the aes send message method).
    # If connection is currently finishing due to sent messages and no messages left for that device and a new
    # message appears in the queue, send a new broadcast and establish a new connection.
    #
    current_addr_connections: set[str]
    
    def __init__(self, account: Account, server_ip: str = "0.0.0.0") -> None:
        self.devices: dict[str, KlyqaDevice] = account.devices
        self.tcp: socket.socket | None = None
        self.udp: socket.socket | None = None
        self.server_ip: str = server_ip
        self.message_queue: dict[str, list[Message]] = {}
        self.__send_loop_sleep: Task | None = None
        self.__tasks_done: list[tuple[Task, datetime.datetime, datetime.datetime]] = []
        self.__tasks_undone: list[tuple[Task, datetime.datetime]] = []
        self.search_and_send_loop_task: Task | None = None
        self.search_and_send_loop_task_end_now: bool = False
        self.__read_tcp_task: Task | None = None
        self.account: Account = account
        self.acc_settings: TypeJSON | None = account.settings
        self.current_addr_connections: set[str] = set()

    async def shutdown(self) -> None:

        await self.search_and_send_loop_task_stop()
        
        try:
            if self.tcp:
                self.tcp.shutdown(socket.SHUT_RDWR)
                self.tcp.close()
                LOGGER.debug("Closed TCP port 3333")
                self.tcp = None
        except:
            LOGGER.debug(f"{traceback.format_exc()}")

        try:
            if self.udp:
                self.udp.close()
                LOGGER.debug("Closed UDP port 2222")
                self.udp = None
        except:
            LOGGER.debug(f"{traceback.format_exc()}")

    async def bind_ports(self) -> bool:
        """bind ports."""
        await self.shutdown()
        server_address: tuple[str, int]
        try:

            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_address = (self.server_ip, 2222)
            self.udp.bind(server_address)
            LOGGER.debug("Bound UDP port 2222")

        except:
            LOGGER.error(
                "Error on opening and binding the udp port 2222 on host for initiating the device communication."
            )
            LOGGER.debug(f"{traceback.format_exc()}")
            return False

        try:
            self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_address = ("0.0.0.0", 3333)
            self.tcp.bind(server_address)
            LOGGER.debug("Bound TCP port 3333")
            self.tcp.listen(1)

        except:
            LOGGER.error(
                "Error on opening and binding the tcp port 3333 on host for initiating the device communication."
            )
            LOGGER.debug(f"{traceback.format_exc()}")
            return False
        return True
    
    
    async def aes_wait_iv_pkg_zero(
        self,
        connection: LocalConnection,
        pkg: bytes,
        device: KlyqaDevice,
        r_device: RefParse,
        use_dev_aes: bool) -> Device_TCP_return:
        # Check identification package from device, lock the device object for changes,
        # safe the idenfication to device object if it is a not known device,
        # send the local initial vector for the encrypted communication to the device.

        logger_debug_task(f"Plain: {pkg}")
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

            device_b.local_addr = connection.address
            if is_new_device:
                device_b.ident = ident
                device_b.u_id = ident.unit_id
            device = device_b
            r_device.ref = device_b
        else:
            err: str = f"{task_name()} - Couldn't get use lock for device {device_b.get_name()} {connection.address})"
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
        if self.account and self.account.settings and "devices" in self.account.settings:
            settings_device = [
                device_settings
                for device_settings in self.account.settings["devices"]
                if format_uid(device_settings["localDeviceId"])
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
                f"{task_name()} - " if LOGGER.level == logging.DEBUG else "",
            )
        else:
            logger_debug_task(f"Found device {found}")

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
    
        return Device_TCP_return.no_error

    async def aes_wait_iv_pkg_one(self, connection: LocalConnection,
        pkg: bytes, device: KlyqaDevice) -> Device_TCP_return:
        """Set aes key for the connection from the first package."""
        # Receive the remote initial vector (iv) for aes encrypted communication.

        connection.remoteIv = pkg
        connection.received_packages.append(pkg)
        if not connection.aes_key:
            logger_debug_task(
                "Missing AES key. Probably not in onboarded devices. Provide AES key with --aes [key]! "
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
    
        return Device_TCP_return.no_error
        
    async def message_answer_package(self, connection: LocalConnection,
        pkg: bytes, device: KlyqaDevice, msg_sent: Message | None) -> Device_TCP_return | int:
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
                logger_debug_task(f"device uid {device.u_id} aes_confirmed {connection.aes_key_confirmed}")
            except:
                logger_debug_task("Could not load json message from device: ")
                logger_debug_task(f"{pkg}")
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

        logger_debug_task(f" Request's reply decrypted: " + str(plain))
        return return_val


    async def device_handle_local_tcp(
        self, device: KlyqaDevice, connection: LocalConnection
    ) -> Device_TCP_return:
        """! Handle the incoming tcp connection to the device."""
        return_state: Device_TCP_return = Device_TCP_return.nothing_done
        
        task: asyncio.Task[Any] | None = asyncio.current_task()

        try:
            r_device: RefParse = RefParse(device)

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
                logger_debug_task(f"finished tcp device {connection.address['ip']}, return_state: {return_state}")

                if connection.socket is not None:
                    connection.socket.shutdown(socket.SHUT_RDWR)
                    connection.socket.close()
                    connection.socket = None
                self.current_addr_connections.remove(str(connection.address["ip"]))
                logger_debug_task(f"tcp closed for {device.u_id}. Return state: {return_state}")

                unit_id: str = (
                    f" Unit-ID: {device.u_id}" if device.u_id else ""
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

                if device.u_id in self.devices:
                    device_b: KlyqaDevice = self.devices[device.u_id]
                    if device_b._use_thread == asyncio.current_task():
                        try:
                            if device_b._use_lock is not None:
                                device_b._use_lock.release()
                            device_b._use_thread = None
                        except:
                            LOGGER.debug(f"{traceback.format_exc()}")

                elif return_state == 1:
                    LOGGER.error(
                        f"Unknown error during send (and handshake) with device {unit_id}."
                    )
                elif return_state == 2:
                    pass
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
            proc_timeout_secs: max timeout in seconds for a device communication handle process

        Returns:
            true:  on success
            false: on exception or error
        """
        loop = asyncio.get_event_loop()

        try:
            if not self.tcp or not self.udp:
                await self.bind_ports()
            while not self.search_and_send_loop_task_end_now:
                if not self.tcp or not self.udp:
                    break
                # for debug cursor jump:
                a = False
                if a:
                    break

                if self.message_queue:

                    read_broadcast_response = True
                    try:
                        LOGGER.debug("Broadcasting QCX-SYN Burst")
                        self.udp.sendto(
                            "QCX-SYN".encode("utf-8"), ("255.255.255.255", 2222)
                        )

                    except:
                        LOGGER.debug("Broadcasting QCX-SYN Burst Exception")
                        LOGGER.debug(f"{traceback.format_exc()}")
                        read_broadcast_response = False
                        if not await self.bind_ports():
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

                        timeout_read: float = 0.01
                        LOGGER.debug("Read again tcp port..")

                        async def read_tcp_task() -> tuple[
                            list[Any], list[Any], list[Any]
                        ] | None:
                            try:
                                return await loop.run_in_executor(
                                    None,
                                    select.select,
                                    [self.tcp],
                                    [],
                                    [],
                                    timeout_read,
                                )
                            except CancelledError as e:
                                LOGGER.debug("cancelled tcp reading.")
                            except Exception as e:
                                LOGGER.error(f"{traceback.format_exc()}")
                                if not await self.bind_ports():
                                    LOGGER.error(
                                        "Error binding ports udp 2222 and tcp 3333."
                                    )
                            return None

                        self.__read_tcp_task = asyncio.create_task(read_tcp_task())

                        LOGGER.debug("Started tcp reading..")
                        try:
                            await asyncio.wait_for(self.__read_tcp_task, timeout=1.0)
                        except Exception as e:
                            LOGGER.debug(
                                f"Socket-Timeout for incoming tcp connections."
                            )

                            if not await self.bind_ports():
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

                        if not self.tcp in readable:
                            break
                        else:
                            device: KlyqaDevice = KlyqaDevice()
                            connection: LocalConnection = LocalConnection()
                            (
                                connection.socket,
                                addr,
                            ) = self.tcp.accept()
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
                    except Exception:
                        LOGGER.debug(f"{traceback.format_exc()}")

                try:
                    tasks_undone_new = []
                    for task, started in self.__tasks_undone:
                        if task.done():
                            self.__tasks_done.append(
                                (task, started, datetime.datetime.now())
                            )
                            exception: Any = task.exception()
                            if exception:
                                LOGGER.debug(
                                    f"Exception error in {task.get_coro()}: {exception}"
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

                if not len(self.message_queue):
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
            for task, started in self.__tasks_undone:
                task.cancel(msg=f"Search and send loop cancelled.")
        except Exception as e:
            LOGGER.debug("Exception on send and search loop. Stop loop.")
            LOGGER.debug(f"{traceback.format_exc()}")
            return False
        return True

    async def search_and_send_loop_task_stop(self) -> None:
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

        if not self.search_and_send_loop_task or self.search_and_send_loop_task.done():
            LOGGER.debug("search and send loop task created.")
            self.search_and_send_loop_task = asyncio.create_task(
                self.search_and_send_to_device()
            )
        try:
            if self.__send_loop_sleep is not None:
                self.__send_loop_sleep.cancel()
        except:
            LOGGER.debug(f"{traceback.format_exc()}")

    async def set_send_message(
        self,
        send_msgs: list[tuple[Any]],
        target_device_uid: str,
        args: argparse.Namespace,
        callback: Callable | None = None,
        time_to_live_secs: float = -1.0
    ) -> bool:

        if not send_msgs and callback is not None:
            LOGGER.error(f"No message queue to send in message to {target_device_uid}!")
            await callback(None, target_device_uid)
            return False

        msg: Message = Message(
            started = datetime.datetime.now(),
            msg_queue = send_msgs,
            args = args,
            target_uid = target_device_uid,
            callback = callback,
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
   
   
    async def aes_handshake_and_send_msgs(
        self,
        r_device: RefParse,
        # r_msg: RefParse,
        connection: LocalConnection,
        use_dev_aes: bool = False,
    ) -> Device_TCP_return:
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
        device: KlyqaDevice = r_device.ref
        if device is None or connection.socket is None:
            return Device_TCP_return.unknown_error

        data: bytes = b""
        last_send: datetime.datetime = datetime.datetime.now()
        connection.socket.settimeout(0.001)
        pause: datetime.timedelta = datetime.timedelta(milliseconds=0)
        elapsed: datetime.timedelta = datetime.datetime.now() - last_send

        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        return_val: Device_TCP_return = Device_TCP_return.nothing_done

        msg_sent: Message | None = None
        communication_finished: bool = False        
        pause_after_send: int

        async def __send_msg() -> Message | None:
            nonlocal last_send, pause, return_val, device, msg_sent, pause_after_send
            
            def rm_msg(msg: Message) -> None:
                if not device:
                    return
                try:
                    logger_debug_task(f"rm_msg()")
                    self.message_queue[device.u_id].remove(msg)
                    msg.state = Message_state.sent

                    if (
                        device.u_id in self.message_queue
                        and not self.message_queue[device.u_id]
                    ):
                        del self.message_queue[device.u_id]
                except:
                    logger_debug_task(f"{traceback.format_exc()}")

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
                
                logger_debug_task(f"Process msg to send '{msg.msg_queue}' to device '{device.u_id}'.")
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

                        pause = datetime.timedelta(milliseconds = float(pause_after_send))
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
                            logger_debug_task(f"{traceback.format_exc()}")
                            break
       
                    if len(msg.msg_queue) == len(msg.msg_queue_sent):
                        msg.state = Message_state.sent
                        # all messages sent to devices, break now for reading response
                        rm_msg(msg)
                else:
                    rm_msg(msg)
            return None
        
        if msg_sent and msg_sent.state == Message_state.answered:
            msg_sent = None
                    
        while not communication_finished and (device.u_id == "no_uid" or type(device) == KlyqaDevice or 
               device.u_id in self.message_queue or msg_sent):
            try:
                data = await loop.run_in_executor(None, connection.socket.recv, 4096)
                if len(data) == 0:
                    logger_debug_task("EOF")
                    return Device_TCP_return.tcp_error
            except socket.timeout:
                LOGGER.debug(f"{traceback.format_exc()}")
            except:
                logger_debug_task(f"{traceback.format_exc()}")
                return Device_TCP_return.unknown_error

            elapsed = datetime.datetime.now() - last_send
            
            if msg_sent and msg_sent.state == Message_state.answered:
                msg_sent = None

            if connection.state == "CONNECTED" and msg_sent is None:
                try:
                    await __send_msg()
                except:
                    logger_debug_task(f"{traceback.format_exc()}")
                    return Device_TCP_return.send_error
                
            while not communication_finished and (len(data)):
                logger_debug_task(
                    f"TCP server received {str(len(data))} bytes from {str(connection.address)}"
                )

                # Read out the data package as follows: package length (pkgLen), package type (pkgType) and package data (pkg)
                
                pkgLen: int = data[0] * 256 + data[1]
                pkgType: int = data[3]

                pkg: bytes = data[4 : 4 + pkgLen]
                if len(pkg) < pkgLen:
                    logger_debug_task(f"Incomplete packet, waiting for more...")
                    break

                data = data[4 + pkgLen :]
                ret: Device_TCP_return | int 
                if connection.state == "WAIT_IV" and pkgType == 0:

                    ret = await self.aes_wait_iv_pkg_zero(connection, pkg, device, r_device, use_dev_aes)
                    device = r_device.ref
                    if ret != Device_TCP_return.no_error:
                        return ret

                if connection.state == "WAIT_IV" and pkgType == 1:
                    ret = await self.aes_wait_iv_pkg_one(connection, pkg, device)
                    if ret != Device_TCP_return.no_error:
                        return ret

                elif connection.state == "CONNECTED" and pkgType == 2:
                    ret = await self.message_answer_package(connection, pkg, device, msg_sent)
                    if type(ret) == Device_TCP_return:
                        return_val = ret # type: ignore
                        if return_val == Device_TCP_return.answered:
                            msg_sent = None
                            communication_finished = True
                    break
                else:
                    logger_debug_task("No answer to process. Waiting on answer of the device ... ")
        return return_val
    
        
    async def discover_devices(self, args: argparse.Namespace,
        message_queue_tx_local: list, target_device_uids: set) -> None:
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