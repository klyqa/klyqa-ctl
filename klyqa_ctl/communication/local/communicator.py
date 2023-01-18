"""Local device communication"""

from __future__ import annotations
import argparse
from asyncio import AbstractEventLoop, CancelledError, Task
import asyncio
import datetime
from enum import Enum, auto
import json
import logging
import select
import socket
import traceback
from typing import Any, Callable
from klyqa_ctl.account import Account
from klyqa_ctl.communication.local.connection import AesConnectionState, DeviceTcpReturn, TcpConnection
from klyqa_ctl.communication.local.data_package import DataPackage, PackageType
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.light.light import Light
from klyqa_ctl.devices.response_identity_message import ResponseIdentityMessage
from klyqa_ctl.devices.vacuum import VacuumCleaner
from klyqa_ctl.general.general import AES_KEY_DEV, DEFAULT_MAX_COM_PROC_TIMEOUT_SECS, SEPARATION_WIDTH, SEND_LOOP_MAX_SLEEP_TIME, ReferenceParse, TypeJson, format_uid, task_log, task_name, LOGGER
from klyqa_ctl.general.message import Message, MessageState
from klyqa_ctl.general.unit_id import UnitId

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
except:
    from Crypto.Cipher import AES  # provided by pycryptodome

class LocalCommunicator:
    """Data communicator for local device connection"""

    # Set of current accepted connections to an IP. One connection is most of the time
    # enough to send all messages for that device behind that connection (in the aes send message method).
    # If connection is currently finishing due to sent messages and no messages left for that device and a new
    # message appears in the queue, send a new broadcast and establish a new connection.
    #
    _attr_current_addr_connections: set[str]
    
    def __init__(self, controller_data: ControllerData, account: Account | None, server_ip: str = "0.0.0.0") -> None:
        self._attr_controller_data: ControllerData = controller_data
        self._attr_account: Account | None = account
        self._attr_devices: dict[str, Device] = account.devices if account else {}
        self._attr_tcp: socket.socket | None = None
        self._attr_udp: socket.socket | None = None
        self._attr_server_ip: str = server_ip
        self._attr_message_queue: dict[str, list[Message]] = {}
        self.__attr_send_loop_sleep: Task | None = None
        self.__attr_tasks_done: list[tuple[Task, datetime.datetime, datetime.datetime]] = []
        self.__attr_tasks_undone: list[tuple[Task, datetime.datetime]] = []
        self._attr_search_and_send_loop_task: Task | None = None
        self._attr_search_and_send_loop_task_end_now: bool = False
        self.__attr_read_tcp_task: Task | None = None
        self._attr_acc_settings: TypeJson | None = account.settings if account else None
        self._attr_current_addr_connections = set()
        
    @property
    def controller_data(self) -> ControllerData:
        return self._attr_controller_data

    @controller_data.setter
    def controller_data(self, controller_data: ControllerData) -> None:
        self._attr_controller_data = controller_data
        
    @property
    def account(self) -> Account | None:
        return self._attr_account

    @account.setter
    def account(self, account: Account) -> None:
        self._attr_account = account
        
    @property
    def devices(self) -> dict[str, Device]:
        return self._attr_devices

    @devices.setter
    def devices(self, devices: dict[str, Device]) -> None:
        self._attr_devices = devices
        
    @property
    def tcp(self) -> socket.socket | None:
        return self._attr_tcp

    @tcp.setter
    def tcp(self, tcp:  socket.socket | None) -> None:
        self._attr_tcp = tcp
        
    @property
    def udp(self) -> socket.socket | None:
        return self._attr_udp

    @udp.setter
    def udp(self, udp: socket.socket | None) -> None:
        self._attr_udp = udp
        
    @property
    def server_ip(self) -> str:
        return self._attr_server_ip

    @server_ip.setter
    def server_ip(self, server_ip: str) -> None:
        self._attr_server_ip = server_ip
        
    @property
    def message_queue(self) -> dict[str, list[Message]]:
        return self._attr_message_queue

    @message_queue.setter
    def message_queue(self, message_queue: dict[str, list[Message]]) -> None:
        self._attr_message_queue = message_queue
        
    @property
    def __send_loop_sleep(self) -> Task | None:
        return self.__attr_send_loop_sleep
    
    @__send_loop_sleep.setter
    def __send_loop_sleep(self, send_loop_sleep: Task | None) -> None:
        self.__attr_send_loop_sleep = send_loop_sleep
        
    @property
    def __tasks_done(self) ->list[tuple[Task, datetime.datetime, datetime.datetime]]:
        return self.__attr_tasks_done

    @__tasks_done.setter
    def __tasks_done(self, tasks_done: list[tuple[Task, datetime.datetime, datetime.datetime]]) -> None:
        self.__attr_tasks_done = tasks_done
        
    @property
    def __tasks_undone(self) -> list[tuple[Task, datetime.datetime]]:
        return self.__attr_tasks_undone

    @__tasks_undone.setter
    def __tasks_undone(self, tasks_undone: list[tuple[Task, datetime.datetime]]) -> None:
        self.__attr_tasks_undone = tasks_undone
        
    @property
    def search_and_send_loop_task(self) -> Task | None:
        return self._attr_search_and_send_loop_task

    @search_and_send_loop_task.setter
    def search_and_send_loop_task(self, search_and_send_loop_task: Task | None) -> None:
        self._attr_search_and_send_loop_task = search_and_send_loop_task
        
    @property
    def search_and_send_loop_task_end_now(self) -> bool:
        return self._attr_search_and_send_loop_task_end_now

    @search_and_send_loop_task_end_now.setter
    def search_and_send_loop_task_end_now(self, search_and_send_loop_task_end_now: bool) -> None:
        self._attr_search_and_send_loop_task_end_now = search_and_send_loop_task_end_now
        
    @property
    def __read_tcp_task(self) -> Task | None:
        return self.__attr_read_tcp_task

    @__read_tcp_task.setter
    def __read_tcp_task(self, read_tcp_task: Task | None) -> None:
        self.__attr_read_tcp_task = read_tcp_task
        
    @property
    def acc_settings(self) -> dict[str, Any] | None:
        return self._attr_acc_settings

    @acc_settings.setter
    def acc_settings(self, acc_settings: TypeJson | None) -> None:
        self._attr_acc_settings = acc_settings
        
    @property
    def current_addr_connections(self) -> set[str]:
        return self._attr_current_addr_connections

    @current_addr_connections.setter
    def current_addr_connections(self, current_addr_connections: set[str]) -> None:
        self._attr_current_addr_connections = current_addr_connections
    
    async def shutdown(self) -> None:

        await self.search_and_send_loop_task_stop()
        
        if self.tcp:
            try:
                LOGGER.debug("Closing TCP port 3333")
                self.tcp.shutdown(socket.SHUT_RDWR)
                self.tcp.close()
                self.tcp = None
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error("Error on closing local tcp port 3333.")
                LOGGER.debug(f"{traceback.format_exc()}")

        if self.udp:
            try:
                LOGGER.debug("Closing UDP port 2222")
                self.udp.close()
                self.udp = None
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error("Error on closing local udp port 2222.")
                LOGGER.debug(f"{traceback.format_exc()}")

    async def bind_ports(self) -> bool:
        """bind ports."""
        # await self.shutdown()
        server_address: tuple[str, int]
        
        if not self.udp: # or self.udp._closed or self.udp.__getstate__()() == -1:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_address = (self.server_ip, 2222)
            try:
                self.udp.bind(server_address)
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error(
                    "Error on opening and binding the udp port 2222 on host for initiating the local device communication."
                )
                LOGGER.debug(f"{traceback.format_exc()}")
                return False
            LOGGER.debug("Bound UDP port 2222")

        if not self.tcp: # or self.tcp.closed() or self.tcp.fileno() == -1:
            self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_address = ("0.0.0.0", 3333)
            try:
                self.tcp.bind(server_address)
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error(
                    "Error on opening and binding the tcp port 3333 on host for initiating the local device communication."
                )
                LOGGER.debug(f"{traceback.format_exc()}")
                return False
            LOGGER.debug("Bound TCP port 3333")
            self.tcp.listen(1)
        return True
    
    async def process_device_identity_package(
        self,
        connection: TcpConnection,
        data: bytes,
        device_ref: ReferenceParse,
        use_dev_aes: bool,
        aes_key: bytes | None = None) -> DeviceTcpReturn:
        """Process the device identity package."""
        # Check identification package from device, lock the device object for changes,
        # safe the idenfication to device object if it is a not known device,
        # send the local initial vector for the encrypted communication to the device.
        
        device: Device = device_ref.ref

        task_log(f"Plain: {data}")
        json_response: dict[str, Any] = json.loads(data)
        try:
            identity: ResponseIdentityMessage = ResponseIdentityMessage(
                **json_response["ident"]
            )
            device.u_id = identity.unit_id
        except:
            return DeviceTcpReturn.NO_UNIT_ID

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
            if ".lighting" in identity.product_id:
                self.devices[device.u_id] = Light()
            elif ".cleaning" in identity.product_id:
                self.devices[device.u_id] = VacuumCleaner()

        # cached client device (self.devices), incoming device object created on tcp connection acception
        if not device.u_id in self.devices:
            return DeviceTcpReturn.NOTHING_DONE
        device_b: Device = self.devices[device.u_id]
        
        if await device_b.use_lock():

            device_b.local_addr = connection.address
            if is_new_device:
                device_b.ident = identity
                device_b.u_id = identity.unit_id
            device = device_b
            device_ref.ref = device_b
        else:
            err: str = f"{task_name()} - Couldn't get use lock for device {device_b.get_name()} {connection.address})"
            LOGGER.error(err)
            return DeviceTcpReturn.DEVICE_LOCK_TIMEOUT

        connection.received_packages.append(json_response)
        device.save_device_message(json_response)

        if (
            not device.u_id in self.message_queue
            or not self.message_queue[device.u_id]
        ):
            if device.u_id in self.message_queue:
                del self.message_queue[device.u_id]
            return DeviceTcpReturn.NO_MESSAGE_TO_SEND

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
            name: str = settings_device[0]["name"]
            found = found + ' "' + name + '"'
        elif device.ident:
            found = found + f" {device.ident.unit_id}"

        if is_new_device:
            LOGGER.info(
                f"%sFound device {found}",
                f"{task_name()} - " if LOGGER.level == logging.DEBUG else "",
            )
        else:
            task_log(f"Found device {found}")

        if aes_key is not None:
            connection.aes_key = aes_key
        elif "all" in self.controller_data.aes_keys:
            connection.aes_key = self.controller_data.aes_keys["all"]
        elif use_dev_aes or "dev" in self.controller_data.aes_keys:
            connection.aes_key = AES_KEY_DEV
        elif isinstance(self.controller_data.aes_keys, dict) and device.u_id in self.controller_data.aes_keys:
            connection.aes_key = self.controller_data.aes_keys[device.u_id]
        try:
            if connection.socket is not None:
                # for prod do in executor or task for more asyncio schedule task executions
                # await loop.run_in_executor(None, connection.socket.send, bytes([0, 8, 0, 1]) + connection.localIv)
                if not connection.socket.send(
                    bytes([0, 8, 0, 1]) + connection.localIv
                ):
                    return DeviceTcpReturn.ERROR_LOCAL_IV
        except:
            return DeviceTcpReturn.ERROR_LOCAL_IV
    
        return DeviceTcpReturn.NO_ERROR

    async def process_aes_initial_vector_package(self, connection: TcpConnection,
        data: bytes, device: Device) -> DeviceTcpReturn:
        """Create the AES encryption and decryption objects."""

        connection.remoteIv = data
        connection.received_packages.append(data)
        if not connection.aes_key:
            task_log(
                "Missing AES key. Probably not in onboarded devices. Provide AES key with --aes [key]! "
                + str(device.u_id)
            )
            return DeviceTcpReturn.MISSING_AES_KEY
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

        connection.state = AesConnectionState.CONNECTED
    
        return DeviceTcpReturn.NO_ERROR
        
    async def process_message_answer_package(self, connection: TcpConnection,
        answer: bytes, device: Device, msg_sent: Message | None) -> DeviceTcpReturn:
        """Process the encrypted device answer."""
        
        return_val: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

        cipher: bytes = answer

        plain: bytes = connection.receivingAES.decrypt(cipher)
        connection.received_packages.append(plain)
        if msg_sent is not None and not msg_sent.state == MessageState.ANSWERED:
            msg_sent.answer = plain
            json_response: TypeJson = {}
            try:
                plain_utf8: str = plain.decode()
                json_response = json.loads(plain_utf8)
                device.save_device_message(json_response)
                connection.sent_msg_answer = json_response
                connection.aes_key_confirmed = True
                task_log(f"device uid {device.u_id} aes_confirmed {connection.aes_key_confirmed}")
            except:
                task_log("Could not load json message from device: ")
                task_log(f"{answer}")
                return DeviceTcpReturn.RESPONSE_ERROR

            msg_sent.answer_utf8 = plain_utf8
            msg_sent.answer_json = json_response
            msg_sent.state = MessageState.ANSWERED
            msg_sent.answered_datetime = datetime.datetime.now()
            return_val = DeviceTcpReturn.ANSWERED

            device.recv_msg_unproc.append(msg_sent)
            device.process_msgs()
                    
            if msg_sent and not msg_sent.callback is None and device is not None:
                await msg_sent.callback(msg_sent, device.u_id)
                LOGGER.debug(
                    f"device {device.u_id} answered msg {msg_sent.msg_queue}"
                )

        task_log(f" Request's reply decrypted: " + str(plain))
        return return_val
    
    def remove_msg_from_queue(self, msg: Message, device: Device | None) -> None:
        if not device:
            return
        try:
            task_log(f"rm_msg()")
            self.message_queue[device.u_id].remove(msg)
            msg.state = MessageState.SENT

            if (
                device.u_id in self.message_queue
                and not self.message_queue[device.u_id]
            ):
                del self.message_queue[device.u_id]
        except:
            task_log(f"{traceback.format_exc()}")
   
    async def aes_handshake_and_send_msgs(
        self,
        device_ref: ReferenceParse,
        connection: TcpConnection,
        use_dev_aes: bool = False,
    ) -> DeviceTcpReturn:
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
        device: Device = device_ref.ref
        if device is None or connection.socket is None:
            return DeviceTcpReturn.UNKNOWN_ERROR

        data: bytes = b""
        last_send: datetime.datetime = datetime.datetime.now()
        connection.socket.settimeout(0.001)
        pause: datetime.timedelta = datetime.timedelta(milliseconds=0)
        elapsed: datetime.timedelta = datetime.datetime.now() - last_send

        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        return_val: DeviceTcpReturn = DeviceTcpReturn.NOTHING_DONE

        msg_sent: Message | None = None
        communication_finished: bool = False        
        pause_after_send: int

        async def __send_msg() -> Message | None:
            nonlocal last_send, pause, return_val, device, msg_sent, pause_after_send
            
            send_next: bool = elapsed >= pause
            sleep: float = (pause - elapsed).total_seconds()
            if sleep > 0:
                await asyncio.sleep(sleep)
        
            if (
                send_next and device
                and device.u_id in self.message_queue
                and len(self.message_queue[device.u_id]) > 0
            ):
                msg: Message = self.message_queue[device.u_id][0]
                
                task_log(f"Process msg to send '{msg.msg_queue}' to device '{device.u_id}'.")
                j: int = 0
                
                if msg.state == MessageState.UNSENT:
                    
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
                                self.remove_msg_from_queue(msg, device)
                                # stop processing further the message
                                break

                        pause = datetime.timedelta(milliseconds = float(pause_after_send))
                        try:
                            if await loop.run_in_executor(None, encrypt_and_send_msg, text, device,
                                                          connection):
                                
                                return_val = DeviceTcpReturn.SENT
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
                            task_log(f"{traceback.format_exc()}")
                            break
       
                    if len(msg.msg_queue) == len(msg.msg_queue_sent):
                        msg.state = MessageState.SENT
                        # all messages , break now for reading response
                        self.remove_msg_from_queue(msg, device)
                else:
                    self.remove_msg_from_queue(msg, device)
            return None
        
        if msg_sent and msg_sent.state == MessageState.ANSWERED:
            msg_sent = None
                    
        while not communication_finished and (device.u_id == "no_uid" or type(device) == Device or 
               device.u_id in self.message_queue or msg_sent):
            
            data_ref: ReferenceParse = ReferenceParse(data)
            read_data_ret: DeviceTcpReturn = await connection.read_local_tcp_socket(data_ref)
            if read_data_ret != DeviceTcpReturn.NO_ERROR:
                return read_data_ret
            data = data_ref.ref

            elapsed = datetime.datetime.now() - last_send
            
            if msg_sent and msg_sent.state == MessageState.ANSWERED:
                msg_sent = None

            if connection.state == AesConnectionState.CONNECTED and msg_sent is None:
                try:
                    await __send_msg()
                except:
                    task_log(f"{traceback.format_exc()}")
                    return DeviceTcpReturn.SEND_ERROR
                
            while not communication_finished and (len(data)):
                task_log(
                    f"TCP server received {str(len(data))} bytes from {str(connection.address)}"
                )
                
                return_val = await self.aes_handshake_and_read_tcp_socket(connection, data_ref,
                    msg_sent, device_ref, use_dev_aes)
                data = data_ref.ref
                device = device_ref.ref
                if return_val == DeviceTcpReturn.ANSWERED:
                    msg_sent = None
                    communication_finished = True
                elif return_val != DeviceTcpReturn.NO_ERROR:
                    return return_val
            
        return return_val
    
    async def aes_handshake_and_read_tcp_socket(self, connection: TcpConnection, data_ref: ReferenceParse,
        msg_sent: Message | None, device_ref: ReferenceParse, use_dev_aes: bool) -> DeviceTcpReturn:
    
        return_val: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR
        package: DataPackage = DataPackage(data_ref.ref)
        
        if not package.read_raw_data():
            return DeviceTcpReturn.RESPONSE_ERROR
        
        data_ref.ref = data_ref.ref[4 + package.length :]

        if connection.state == AesConnectionState.WAIT_IV and package.type == PackageType.IDENTITY:

            return_val = await self.process_device_identity_package(connection, package.data,
                device_ref, use_dev_aes)
            if return_val != DeviceTcpReturn.NO_ERROR:
                return return_val

        if connection.state == AesConnectionState.WAIT_IV and package.type == PackageType.AES_INITIAL_VECTOR:
            return_val = await self.process_aes_initial_vector_package(connection,
                package.data, device_ref.ref)
            if return_val != DeviceTcpReturn.NO_ERROR:
                return return_val

        elif connection.state == AesConnectionState.CONNECTED and package.type == PackageType.DATA:
            return_val = await self.process_message_answer_package(connection, package.data, device_ref.ref, msg_sent)
        else:
            task_log("No answer to process. Waiting on answer of the device ... ")
        return return_val

    async def device_handle_local_tcp(
        self, device: Device, connection: TcpConnection
    ) -> DeviceTcpReturn:
        """! Handle the incoming tcp connection to the device."""
        return_state: DeviceTcpReturn = DeviceTcpReturn.NOTHING_DONE
        
        task: asyncio.Task[Any] | None = asyncio.current_task()

        try:
            r_device: ReferenceParse = ReferenceParse(device)

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
                task_log(f"finished tcp device {connection.address['ip']}, return_state: {return_state}")

                if connection.socket is not None:
                    connection.socket.shutdown(socket.SHUT_RDWR)
                    connection.socket.close() 
                    connection.socket = None
                self.current_addr_connections.remove(str(connection.address["ip"]))
                task_log(f"tcp closed for {device.u_id}. Return state: {return_state}")

                unit_id: str = (
                    f" Unit-ID: {device.u_id}" if device.u_id else ""
                )

                # if return_state == DeviceTcpReturn.NO_ERROR:
                #     """no error"""

                #     def dict_values_to_list(d: dict) -> list[str]:
                #         r: list[str] = []
                #         for i in d.values():
                #             if isinstance(i, dict):
                #                 i = dict_values_to_list(i)
                #             r.append(str(i))
                #         return r

                if device.u_id in self.devices:
                    device_b: Device = self.devices[device.u_id]
                    if device_b._use_thread == asyncio.current_task():
                        try:
                            if device_b._use_lock is not None:
                                device_b._use_lock.release()
                            device_b._use_thread = None
                        except:
                            LOGGER.debug(f"{traceback.format_exc()}")

                elif return_state == DeviceTcpReturn.UNKNOWN_ERROR:
                    LOGGER.error(
                        f"Unknown error during send (and handshake) with device {unit_id}."
                    )
                # elif return_state == DeviceTcpReturn.NO_ERROR:
                #     pass
                # elif return_state == DeviceTcpReturn.NO_ERROR:
                #     LOGGER.debug(
                #         f"End of tcp stream. ({connection.address['ip']}:{connection.address['port']})"
                #     )

        except CancelledError as e:
            LOGGER.error(f"Device tcp task cancelled.")
        except Exception as e:
            LOGGER.debug(f"{e}")
            pass
        return return_state

    async def search_and_send_to_device(
        self, proc_timeout_secs: int = DEFAULT_MAX_COM_PROC_TIMEOUT_SECS
    ) -> bool:
        """! Send broadcast and make tasks for incoming tcp connections.

        Params:
            proc_timeout_secs: max timeout in seconds for a device communication handle process

        Returns:
            true:  on success
            false: on exception or error
        """
        loop: AbstractEventLoop = asyncio.get_event_loop()

        try:
            # if not self.tcp or not self.udp:
            while not self.search_and_send_loop_task_end_now:
                if not await self.bind_ports():
                # if (not self.tcp or not self.udp) and not await self.bind_ports():
                    break
                # for debug cursor jump:
                a: bool = False
                if a:
                    break

                if self.message_queue:

                    read_broadcast_response: bool = True
                    try:
                        LOGGER.debug("Broadcasting QCX-SYN Burst")
                        if self.udp:
                            await loop.run_in_executor(
                                None,
                                self.udp.sendto,
                                "QCX-SYN".encode("utf-8"),
                                ("255.255.255.255", 2222)
                            )
                        else:
                            continue
                        
                        # self.udp.sendto(
                        #     "QCX-SYN".encode("utf-8"), ("255.255.255.255", 2222)
                        # )

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
                            device: Device = Device()
                            connection: TcpConnection = TcpConnection()
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
        send_msgs: list[tuple],
        target_device_uid: UnitId,
        callback: Callable | None = None,
        time_to_live_secs: float = -1.0,
        **kwargs: Any
    ) -> bool:

        if not send_msgs and callback is not None:
            LOGGER.error(f"No message queue to send in message to {target_device_uid}!")
            await callback(None, target_device_uid)
            return False

        msg: Message = Message(
            datetime.datetime.now(),
            target_device_uid,
            msg_queue = send_msgs,
            callback = callback,
            time_to_live_secs = time_to_live_secs,
            **kwargs
        )

        if not await msg.check_msg_ttl():
            return False

        task_log(
            f"new message {msg.msg_counter} target {target_device_uid} {send_msgs}", LOGGER.trace
        )

        self.message_queue.setdefault(str(target_device_uid), []).append(msg)

        if self.__read_tcp_task:
            # if still waiting for incoming connections, restart the process
            # with a new udp broadcast
            self.__read_tcp_task.cancel()
        self.search_and_send_loop_task_alive()
        return True
        
    async def discover_devices(self, args: argparse.Namespace,
        message_queue_tx_local: list, target_device_uids: set) -> None:
        """Discover devices."""

        print(SEPARATION_WIDTH * "-")
        print("Search local network for devices ...")
        print(SEPARATION_WIDTH * "-")

        discover_end_event: asyncio.Event = asyncio.Event()
        discover_timeout_secs: float = 2.5

        async def discover_answer_end(
            answer: TypeJson, uid: str
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
            discover_answer_end,
            discover_timeout_secs,
        )

        await discover_end_event.wait()
        if self.devices:
            target_device_uids = set(
                u_id for u_id, v in self.devices.items()
            )

def encrypt_and_send_msg(msg: str, device: Device, connection: TcpConnection) -> bool:
    info_str: str = (
        (f"{task_name()} - " if LOGGER.level == logging.DEBUG else "")
        + 'Sending in local network to "'
        + device.get_name()
        + '": '
        + json.dumps(json.loads(msg), sort_keys=True, indent=4)
    )

    LOGGER.info(info_str)
    plain: bytes = msg.encode("utf-8")
    while len(plain) % 16:
        plain = plain + bytes([0x20])

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
