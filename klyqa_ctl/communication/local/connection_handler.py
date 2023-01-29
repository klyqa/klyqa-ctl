"""Local device communication"""

from __future__ import annotations

import asyncio
from asyncio import AbstractEventLoop, CancelledError, Task
import datetime
import json
import select
import socket
from typing import Any

from klyqa_ctl.communication.connection_handler import ConnectionHandler
from klyqa_ctl.communication.local.connection import (
    AesConnectionState,
    DeviceTcpReturn,
    TcpConnection,
)
from klyqa_ctl.communication.local.data_package import DataPackage, PackageType
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.device import CommandWithCheckValues, Device
from klyqa_ctl.devices.light.commands import PingCommand, TransitionCommand
from klyqa_ctl.devices.light.light import Light
from klyqa_ctl.devices.response_identity_message import ResponseIdentityMessage
from klyqa_ctl.devices.vacuum.vacuum import VacuumCleaner
from klyqa_ctl.general.general import (
    DEFAULT_MAX_COM_PROC_TIMEOUT_SECS,
    LOGGER,
    SEND_LOOP_MAX_SLEEP_TIME,
    SEPARATION_WIDTH,
    Command,
    ReferencePass,
    TypeJson,
    task_log,
    task_log_debug,
    task_log_error,
    task_log_trace,
    task_log_trace_ex,
    task_name,
)
from klyqa_ctl.general.message import BroadCastMessage, Message, MessageState
from klyqa_ctl.general.unit_id import UnitId

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
except ImportError:
    from Crypto.Cipher import AES  # provided by pycryptodome

SO_BINDTODEVICE_LINUX: int = 25


class LocalConnectionHandler(ConnectionHandler):  # type: ignore[misc]
    """Data communicator for local device connection.

    Important: Call async function shutdown() after using send method,
    or the send message loop will keep running."""

    # Set of current accepted connections to an IP. One connection is most of
    # the time enough to send all messages for that device behind that
    # connection (in the aes send message method).
    # If connection is currently finishing due to sent messages and no
    # messages left for that device and a new message appears in the queue,
    # send a new broadcast and establish a new connection.
    #
    _attr_current_addr_connections: set[str]

    def __init__(
        self,
        controller_data: ControllerData,
        server_ip: str = "0.0.0.0",
        network_interface: str | None = None,
    ) -> None:
        self._attr_controller_data: ControllerData = controller_data
        self._attr_devices: dict[str, Device] = controller_data.devices
        self._attr_tcp: socket.socket | None = None
        self._attr_udp: socket.socket | None = None
        self._attr_server_ip: str = server_ip
        # here message queue key needs to be string not UnitId to be hashable
        # for dictionaries and sets
        self._attr_message_queue: dict[str, list[Message]] = {}
        self.__attr_send_loop_sleep: Task | None = None
        self.__attr_tasks_done: list[
            tuple[Task, datetime.datetime, datetime.datetime]
        ] = []
        self.__attr_tasks_undone: list[tuple[Task, datetime.datetime]] = []
        self._attr_handlec_connections_task: Task | None = None
        self._attr_handle_connections_task_end_now: bool = False
        self.__attr_read_tcp_task: Task | None = None
        self.msg_ttl_task: Task | None = None
        self._attr_current_addr_connections = set()
        self._attr_network_interface: str | None = network_interface

    @property
    def network_interface(self) -> str | None:
        return self._attr_network_interface

    @network_interface.setter
    def network_interface(self, network_interface: str | None) -> None:
        self._attr_network_interface = network_interface

    @property
    def controller_data(self) -> ControllerData:
        return self._attr_controller_data

    @controller_data.setter
    def controller_data(self, controller_data: ControllerData) -> None:
        self._attr_controller_data = controller_data

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
    def tcp(self, tcp: socket.socket | None) -> None:
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
    def __tasks_done(
        self,
    ) -> list[tuple[Task, datetime.datetime, datetime.datetime]]:
        return self.__attr_tasks_done

    @__tasks_done.setter
    def __tasks_done(
        self,
        tasks_done: list[tuple[Task, datetime.datetime, datetime.datetime]],
    ) -> None:
        self.__attr_tasks_done = tasks_done

    @property
    def __tasks_undone(self) -> list[tuple[Task, datetime.datetime]]:
        return self.__attr_tasks_undone

    @__tasks_undone.setter
    def __tasks_undone(
        self, tasks_undone: list[tuple[Task, datetime.datetime]]
    ) -> None:
        self.__attr_tasks_undone = tasks_undone

    @property
    def handle_connections_task(self) -> Task | None:
        return self._attr_handlec_connections_task

    @handle_connections_task.setter
    def handle_connections_task(
        self, handle_connections_tasks: Task | None
    ) -> None:
        self._attr_handlec_connections_task = handle_connections_tasks

    @property
    def handle_connections_task_end_now(self) -> bool:
        return self._attr_handle_connections_task_end_now

    @handle_connections_task_end_now.setter
    def handle_connections_task_end_now(
        self, handle_connections_task_end_now: bool
    ) -> None:
        self._attr_handle_connections_task_end_now = (
            handle_connections_task_end_now
        )

    @property
    def __read_tcp_task(self) -> Task | None:
        return self.__attr_read_tcp_task

    @__read_tcp_task.setter
    def __read_tcp_task(self, read_tcp_task: Task | None) -> None:
        self.__attr_read_tcp_task = read_tcp_task

    @property
    def current_addr_connections(self) -> set[str]:
        return self._attr_current_addr_connections

    @current_addr_connections.setter
    def current_addr_connections(
        self, current_addr_connections: set[str]
    ) -> None:
        self._attr_current_addr_connections = current_addr_connections

    async def shutdown(self) -> None:

        await self.handle_connections_task_stop()

        if self.tcp:
            try:
                LOGGER.debug("Closing TCP port 3333")
                self.tcp.shutdown(socket.SHUT_RDWR)
                self.tcp.close()
                self.tcp = None
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error("Error on closing local tcp port 3333.")
                task_log_trace_ex()

        if self.udp:
            try:
                LOGGER.debug("Closing UDP port 2222")
                self.udp.close()
                self.udp = None
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error("Error on closing local udp port 2222.")
                task_log_trace_ex()

    async def bind_ports(self) -> bool:
        """bind ports."""
        server_address: tuple[str, int]

        if (
            not self.udp
        ):  # or self.udp._closed or self.udp.__getstate__() == -1:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if self.network_interface is not None:
                self.udp.setsockopt(
                    socket.SOL_SOCKET,
                    SO_BINDTODEVICE_LINUX,
                    str(self.network_interface + "\0").encode("utf-8"),
                )
            server_address = (self.server_ip, 2222)
            try:
                self.udp.bind(server_address)
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error(
                    "Error on opening and binding the udp port 2222 on host"
                    " for initiating the local device communication."
                )
                task_log_trace_ex()
                return False
            LOGGER.debug("Bound UDP port 2222")

        if not self.tcp:  # or self.tcp.closed() or self.tcp.fileno() == -1:
            self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            if self.network_interface is not None:
                self.tcp.setsockopt(
                    socket.SOL_SOCKET,
                    SO_BINDTODEVICE_LINUX,
                    str(self.network_interface + "\0").encode("utf-8"),
                )
            server_address = ("0.0.0.0", 3333)
            try:
                self.tcp.bind(server_address)
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error(
                    "Error on opening and binding the tcp port 3333 on host"
                    " for initiating the local device communication."
                )
                task_log_trace_ex()
                return False
            LOGGER.debug("Bound TCP port 3333")
            self.tcp.listen(1)
        return True

    async def process_device_identity_package(
        self,
        connection: TcpConnection,
        data: bytes,
        device_ref: ReferencePass,
    ) -> DeviceTcpReturn:
        """Process the device identity package."""
        # Check identification package from device, lock the device object for
        # changes, safe the idenfication to device object if it is a not known
        # device, send the local initial vector for the encrypted communication
        # to the device.

        device: Device = device_ref.ref

        task_log_debug("Plain: %s", str(data))
        try:
            json_response: dict[str, Any] = json.loads(data)
            identity: ResponseIdentityMessage = ResponseIdentityMessage(
                **json_response["ident"]
            )
            device.u_id = identity.unit_id
        except json.JSONDecodeError:
            return DeviceTcpReturn.NO_UNIT_ID

        is_new_device: bool = False
        if self.controller_data.add_devices_lock:
            await self.controller_data.add_devices_lock.acquire_within_task()

        if device.u_id != "no_uid" and device.u_id not in self.devices:
            is_new_device = True
            new_dev: Device | None = None
            if ".lighting" in identity.product_id:
                new_dev = Light()
            elif ".cleaning" in identity.product_id:
                new_dev = VacuumCleaner()
            if not new_dev:
                LOGGER.info(
                    f"Found new device {identity.unit_id} but don't know the"
                    f" product id {identity.product_id}."
                )
                task_log_debug(
                    f"Found new device {identity.unit_id} but don't know the"
                    f" product id {identity.product_id}."
                )
            else:
                if is_new_device:
                    LOGGER.info(f"Found new device {identity.unit_id}")
                    task_log_debug(f"Found new device {identity.unit_id}")
                new_dev.ident = identity
                new_dev.u_id = UnitId(identity.unit_id)
                if (
                    new_dev.ident
                    and new_dev.ident.product_id
                    in self.controller_data.device_configs
                ):
                    new_dev.read_device_config(
                        device_config=self.controller_data.device_configs[
                            new_dev.ident.product_id
                        ]
                    )

                self.devices[device.u_id] = new_dev

        if self.controller_data.add_devices_lock:
            self.controller_data.add_devices_lock.release_within_task()

        # cached client device (self.devices), incoming device object created
        # on tcp connection acception
        if device.u_id not in self.devices:
            return DeviceTcpReturn.NOTHING_DONE
        device_repl: Device = self.devices[device.u_id]

        if await device_repl.use_lock():
            device_repl.local_addr = connection.address
            device = device_repl
            device_ref.ref = device_repl
        else:
            err: str = (
                f"{task_name()} - Couldn't get use lock for device"
                f" {device_repl.get_name()} {connection.address})"
            )
            LOGGER.error(err)
            return DeviceTcpReturn.DEVICE_LOCK_TIMEOUT

        connection.received_packages.append(json_response)
        device.save_device_message(json_response)

        if (
            device.u_id not in self.message_queue
            or not self.message_queue[device.u_id]
        ):
            if device.u_id in self.message_queue:
                del self.message_queue[device.u_id]
            return DeviceTcpReturn.NO_MESSAGE_TO_SEND

        if not is_new_device and device.ident:
            task_log(f"Found device {device.ident.unit_id}")
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        if "all" in self.controller_data.aes_keys:
            connection.aes_key = self.controller_data.aes_keys["all"]
        # elif use_dev_aes or "dev" in self.controller_data.aes_keys:
        #     connection.aes_key = AES_KEY_DEV
        elif (
            isinstance(self.controller_data.aes_keys, dict)
            and device.u_id in self.controller_data.aes_keys
        ):
            connection.aes_key = self.controller_data.aes_keys[device.u_id]
        try:
            if connection.socket is not None:
                # for prod do in executor or task for more asyncio schedule
                # task executions
                # await loop.run_in_executor(None, connection.socket.send,
                # bytes([0, 8, 0, 1]) + connection.localIv)
                # if not connection.socket.send(
                #     bytes([0, 8, 0, 1]) + connection.local_iv
                # ):
                task_log_debug("Sending local initial vector.")
                await loop.sock_sendall(
                    connection.socket,
                    bytes([0, 8, 0, 1]) + connection.local_iv,
                )
                # return DeviceTcpReturn.ERROR_LOCAL_IV
        except socket.error:
            return DeviceTcpReturn.SOCKET_ERROR

        return DeviceTcpReturn.NO_ERROR

    async def process_aes_initial_vector_package(
        self, connection: TcpConnection, data: bytes, device: Device
    ) -> DeviceTcpReturn:
        """Create the AES encryption and decryption objects."""

        connection.remote_iv = data
        connection.received_packages.append(data)
        if not connection.aes_key:
            task_log(
                "Missing AES key. Probably not in onboarded devices. Provide"
                " AES key with --aes [key]! "
                + str(device.u_id)
            )
            return DeviceTcpReturn.MISSING_AES_KEY
        connection.sending_aes = AES.new(
            connection.aes_key,
            AES.MODE_CBC,
            iv=connection.local_iv + connection.remote_iv,
        )
        connection.receiving_aes = AES.new(
            connection.aes_key,
            AES.MODE_CBC,
            iv=connection.remote_iv + connection.local_iv,
        )

        connection.state = AesConnectionState.CONNECTED
        task_log_debug("Received remote initial vector. Connected state.")

        return DeviceTcpReturn.NO_ERROR

    async def process_message_answer_package(
        self,
        connection: TcpConnection,
        answer: bytes,
        device: Device,
        msg_sent: Message | None,
    ) -> DeviceTcpReturn:
        """Process the encrypted device answer."""

        return_val: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

        cipher: bytes = answer

        plain: bytes = connection.receiving_aes.decrypt(cipher)
        connection.received_packages.append(plain)
        if (
            msg_sent is not None
            and not msg_sent.state == MessageState.ANSWERED
        ):
            msg_sent.answer = plain
            json_response: TypeJson = {}
            try:
                plain_utf8: str = plain.decode()
                json_response = json.loads(plain_utf8)
                device.save_device_message(json_response)
                connection.sent_msg_answer = json_response
                connection.aes_key_confirmed = True
                task_log(
                    f"device uid {device.u_id} aes_confirmed"
                    f" {connection.aes_key_confirmed}"
                )
            except json.JSONDecodeError:
                task_log("Could not load json message from device: ")
                LOGGER.error(
                    "Couldn't read answer from device %s!", device.u_id
                )
                task_log_debug("%s", str(answer))
                return DeviceTcpReturn.RESPONSE_ERROR

            msg_sent.answer_utf8 = plain_utf8
            msg_sent.answer_json = json_response
            msg_sent.state = MessageState.ANSWERED
            msg_sent.answered_datetime = datetime.datetime.now()
            return_val = DeviceTcpReturn.ANSWERED

            # device.recv_msg_unproc.append(msg_sent)
            # device.process_msgs()

            if (
                msg_sent
                and msg_sent.callback is not None
                and device is not None
            ):
                await msg_sent.callback(msg_sent, device.u_id)
                LOGGER.debug(
                    f"device {device.u_id} answered msg {msg_sent.msg_queue}"
                )

        task_log_debug(
            "%s Request's reply decrypted: " + str(plain),
            device.u_id if device else "",
        )
        return return_val

    def remove_msg_from_queue(
        self, msg: Message, device: Device | None
    ) -> None:
        if not device:
            return
        if msg not in self.message_queue[device.u_id]:
            return

        task_log("remove message from queue")
        self.message_queue[device.u_id].remove(msg)
        msg.state = MessageState.SENT

        if (
            device.u_id in self.message_queue
            and not self.message_queue[device.u_id]
        ):
            del self.message_queue[device.u_id]

    async def handle_connection(
        self,
        device_ref: ReferencePass,
        connection: TcpConnection,
        msg_sent_r: ReferencePass,
    ) -> DeviceTcpReturn:
        """
        FIX: return type! sometimes return value sometimes tuple...

        Finish AES handshake.
        Getting the identity of the device.
        Send the commands in message queue to the device with the device u_id
        or to any device.

        Params:
            device: Device - (initial) device object with the tcp connection
            target_device_uid - If given device_uid only send commands when
                the device unit id equals the target_device_uid
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
        pause: datetime.timedelta = datetime.timedelta(milliseconds=0)
        elapsed: datetime.timedelta = datetime.datetime.now() - last_send

        return_val: DeviceTcpReturn = DeviceTcpReturn.NOTHING_DONE

        # msg_sent_r.ref: Message | None = None
        communication_finished: bool = False

        async def __send_next_msg() -> None:
            nonlocal last_send, pause, return_val, device, msg_sent_r

            send_next: bool = elapsed >= pause
            sleep: float = (pause - elapsed).total_seconds()

            if sleep > 0:
                await asyncio.sleep(sleep)

            if (
                send_next
                and device
                # and (
                #     (
                #         device.u_id in self.message_queue
                #         and len(self.message_queue[device.u_id]) > 0
                #     )
                #     or (
                #         "all" in self.message_queue
                #         and len(self.message_queue["all"]) > 0
                #     )
                # )
            ):
                msg: Message | None = None
                if (
                    "all" in self.message_queue
                    and len(self.message_queue["all"]) > 0
                ):
                    m: Message
                    for m in self.message_queue["all"]:
                        bcm: BroadCastMessage = m
                        if device.u_id not in bcm.sent_to_uids:
                            msg = bcm
                            break
                # if (
                #     "all" in self.message_queue
                #     and len(self.message_queue["discover"]) > 0
                # ):
                #     m: Message
                #     for m in self.message_queue["discover"]:
                #         dcm: DiscoverMessage = m
                #         if device.u_id not in bcm.discovered_uids:
                #             msg = dcm
                #             break
                if (
                    not msg
                    and device.u_id in self.message_queue
                    and len(self.message_queue[device.u_id]) > 0
                ):
                    msg = self.message_queue[device.u_id][0]

                if msg:
                    task_log(
                        f"Process msg to send '{msg.msg_queue}' to device"
                        f" '{device.u_id}'."
                    )
                    j: int = 0

                    if msg.state == MessageState.UNSENT:

                        while j < len(msg.msg_queue):

                            command: Command = msg.msg_queue[j]
                            text: str = command.msg_str()
                            if isinstance(command, CommandWithCheckValues):
                                cwcv: CommandWithCheckValues = command
                                if not cwcv._force and not cwcv.check_values(
                                    device=device
                                ):
                                    self.remove_msg_from_queue(msg, device)
                                    break

                            if isinstance(command, TransitionCommand):
                                tc: TransitionCommand = command
                                pause = datetime.timedelta(
                                    milliseconds=float(tc.transition_time)
                                )

                            try:
                                # if await loop.run_in_executor(None, connection.
                                # encrypt_and_send_msg, text, device):
                                if await connection.encrypt_and_send_msg(
                                    text, device
                                ):

                                    return_val = DeviceTcpReturn.SENT
                                    if isinstance(msg, BroadCastMessage):
                                        bcm: BroadCastMessage = msg
                                        bcm.sent_to_uids.add(device.u_id)
                                    msg_sent_r.ref = msg
                                    last_send = datetime.datetime.now()
                                    j = j + 1
                                    msg.msg_queue_sent.append(text)
                                    # don't process the next message, but if
                                    # still elements in the msg_queue send them as
                                    # well
                                    send_next = False
                                    # break
                                else:
                                    LOGGER.error("Could not send message!")
                                    return_val = DeviceTcpReturn.SEND_ERROR
                                    break
                            except socket.error:
                                LOGGER.error(
                                    "Socket error while trying to send"
                                    " message!"
                                )
                                task_log_trace_ex()
                                return_val = DeviceTcpReturn.SEND_ERROR
                                break

                        if len(msg.msg_queue) == len(msg.msg_queue_sent):
                            msg.state = MessageState.SENT
                            # all messages , break now for reading response
                            self.remove_msg_from_queue(msg, device)
                    else:
                        self.remove_msg_from_queue(msg, device)

        if msg_sent_r.ref and msg_sent_r.ref.state == MessageState.ANSWERED:
            msg_sent_r.ref = None

        while not communication_finished and (
            device.u_id == "no_uid"
            or type(device) == Device
            or device.u_id in self.message_queue
            or msg_sent_r.ref
        ):

            if (
                msg_sent_r.ref
                and msg_sent_r.ref.state == MessageState.ANSWERED
            ):
                msg_sent_r.ref = None

            if (
                connection.state == AesConnectionState.CONNECTED
                and msg_sent_r.ref is None
            ):
                await __send_next_msg()
                if return_val == DeviceTcpReturn.SEND_ERROR:
                    return return_val

            data_ref: ReferencePass = ReferencePass(data)
            read_data_ret: DeviceTcpReturn = (
                await connection.read_local_tcp_socket(data_ref)
            )
            if read_data_ret != DeviceTcpReturn.NO_ERROR:
                return read_data_ret
            data = data_ref.ref

            elapsed = datetime.datetime.now() - last_send

            while not communication_finished and (len(data)):
                task_log(
                    f"TCP server received {str(len(data))} bytes from"
                    f" {str(connection.address)}"
                )

                return_val = await self.process_tcp_package(
                    connection, data_ref, msg_sent_r.ref, device_ref
                )
                data = data_ref.ref
                device = device_ref.ref
                if return_val == DeviceTcpReturn.ANSWERED:
                    msg_sent_r.ref = None
                    communication_finished = True
                elif return_val != DeviceTcpReturn.NO_ERROR:
                    return return_val

        return return_val

    async def process_tcp_package(
        self,
        connection: TcpConnection,
        data_ref: ReferencePass,
        msg_sent: Message | None,
        device_ref: ReferencePass,
    ) -> DeviceTcpReturn:
        """Read tcp socket and process packages."""

        return_val: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR
        package: DataPackage = DataPackage(data_ref.ref)

        if not package.read_raw_data():
            return DeviceTcpReturn.RESPONSE_ERROR

        data_ref.ref = data_ref.ref[4 + package.length :]

        if (
            connection.state == AesConnectionState.WAIT_IV
            and package.type == PackageType.IDENTITY
        ):

            return_val = await self.process_device_identity_package(
                connection, package.data, device_ref
            )
            if return_val != DeviceTcpReturn.NO_ERROR:
                return return_val

        if (
            connection.state == AesConnectionState.WAIT_IV
            and package.type == PackageType.AES_INITIAL_VECTOR
        ):
            return_val = await self.process_aes_initial_vector_package(
                connection, package.data, device_ref.ref
            )
            if return_val != DeviceTcpReturn.NO_ERROR:
                return return_val

        elif (
            connection.state == AesConnectionState.CONNECTED
            and package.type == PackageType.DATA
        ):
            return_val = await self.process_message_answer_package(
                connection, package.data, device_ref.ref, msg_sent
            )
        else:
            task_log(
                "No answer to process. Waiting on answer of the device ... "
            )
        return return_val

    async def device_handle_local_tcp(
        self, device: Device, connection: TcpConnection
    ) -> DeviceTcpReturn:
        """Handle the incoming tcp connection to the device."""
        return_state: DeviceTcpReturn = DeviceTcpReturn.NOTHING_DONE

        try:
            r_device: ReferencePass = ReferencePass(device)
            msg_sent_ref: ReferencePass = ReferencePass(None)

            task_log_debug(
                f"New tcp connection to device at {connection.address}"
            )
            try:
                return_state = await self.handle_connection(
                    r_device, connection=connection, msg_sent_r=msg_sent_ref
                )
            except CancelledError:
                LOGGER.error(
                    f"Cancelled local send to {connection.address['ip']}!"
                )
            except Exception as exception:
                task_log_trace_ex()
                task_log_error(
                    "Unhandled exception during local communication! "
                    + str(type(exception))
                )
                msg_sent_ref.ref.exception = exception
            finally:
                device = r_device.ref
                if connection.socket is not None:
                    try:
                        connection.socket.shutdown(socket.SHUT_RDWR)
                        connection.socket.close()
                    finally:
                        connection.socket = None
                self.current_addr_connections.remove(
                    str(connection.address["ip"])
                )

                unit_id: str = (
                    f" Unit-ID: {device.u_id}" if device.u_id else ""
                )

                # if return_state not in [
                #     DeviceTcpReturn.SENT,
                #     DeviceTcpReturn.ANSWERED,
                # ]:
                if return_state in [
                    DeviceTcpReturn.TCP_SOCKET_CLOSED_UNEXPECTEDLY
                ]:
                    # Something bad could have happened with the device.
                    # Remove the message precautiously from the
                    # message queue.
                    msg_sent: Message = msg_sent_ref.ref
                    if msg_sent:
                        await msg_sent.call_cb()
                        self.remove_msg_from_queue(msg_sent, device)

                if device.u_id in self.devices:
                    device_b: Device = self.devices[device.u_id]
                    device_b.use_unlock()

                elif return_state == DeviceTcpReturn.UNKNOWN_ERROR:
                    LOGGER.error(
                        "Unknown error during send (and handshake) with device"
                        f" {unit_id}."
                    )

                task_log(
                    "Finished tcp connection to device"
                    f" {connection.address['ip']} with return state:"
                    f" {return_state}"
                )

        except CancelledError:
            task_log_error("Device tcp task cancelled.")
        except Exception:
            task_log_trace_ex()
        return return_state

    async def send_udp_broadcast(self) -> bool:
        """Send qcx-syn broadcast on udp socket."""
        loop: AbstractEventLoop = asyncio.get_event_loop()

        try:
            task_log_debug("Broadcasting QCX-SYN Burst")
            if self.udp:
                # loop.sock_sendto python3.11+
                await loop.run_in_executor(
                    None,
                    self.udp.sendto,
                    "QCX-SYN".encode("utf-8"),
                    ("255.255.255.255", 2222),
                )
            else:
                return False

        except socket.error:
            task_log_debug("Broadcasting QCX-SYN Burst Exception")
            task_log_trace_ex()
            if not await self.bind_ports():
                LOGGER.error("Error binding ports udp 2222 and tcp 3333.")
                return False
        return True

    async def standby(self) -> None:
        """Standby search devices and create incoming connection tasks."""
        loop: AbstractEventLoop = asyncio.get_event_loop()
        try:
            LOGGER.debug("sleep task create (broadcasts)..")
            self.__send_loop_sleep = loop.create_task(
                asyncio.sleep(
                    SEND_LOOP_MAX_SLEEP_TIME
                    if (len(self.message_queue) > 0)
                    else 1000000000
                )
            )

            LOGGER.debug("sleep task wait..")
            await asyncio.wait([self.__send_loop_sleep])

            LOGGER.debug("sleep task done..")
        except CancelledError:
            LOGGER.debug("sleep cancelled1.")

    async def read_incoming_tcp_con_task(
        self,
    ) -> tuple[list[Any], list[Any], list[Any]] | None:
        loop: AbstractEventLoop = asyncio.get_event_loop()

        timeout_read: float = 0.3
        task_log_debug("Read again tcp port..")

        try:
            return await loop.run_in_executor(
                None,
                select.select,
                [self.tcp],
                [],
                [],
                timeout_read,
            )
        except CancelledError:
            LOGGER.debug("cancelled tcp reading.")
        except Exception:
            task_log_trace_ex()
            if not await self.bind_ports():
                LOGGER.error("Error binding ports udp 2222 and tcp 3333.")
        return None

    async def check_messages_time_to_live(self) -> None:
        """Check message queue for end of live messages."""
        to_del: list[str] = []
        try:
            while True:
                to_del = []
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
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            task_log_debug("Message queue time to live task ended.")

    async def connection_tasks_time_to_live(
        self, proc_timeout_secs: int = DEFAULT_MAX_COM_PROC_TIMEOUT_SECS
    ) -> None:
        """End connection tasks with run out time to live."""
        try:
            tasks_undone_new: list[Any] = []
            for task, started in self.__tasks_undone:
                if task.done():
                    self.__tasks_done.append(
                        (task, started, datetime.datetime.now())
                    )
                    exception: Any = task.exception()
                    if exception:
                        LOGGER.debug(
                            "Exception error device connection handler task in"
                            f" {task.get_coro()}: {exception}"
                        )
                else:
                    if datetime.datetime.now() - started > datetime.timedelta(
                        seconds=proc_timeout_secs
                    ):
                        task.cancel(
                            msg=(
                                "timeout of process of"
                                f" {proc_timeout_secs} seconds."
                            )
                        )
                    tasks_undone_new.append((task, started))
            self.__tasks_undone = tasks_undone_new

        except CancelledError:
            task_log_debug("__tasks_undone check cancelled.")

    async def handle_incoming_tcp_connection(
        self, proc_timeout_secs: int
    ) -> None:
        """Accept incoming tcp connection and start connection handle
        process."""
        if not self.tcp:
            return
        loop: AbstractEventLoop = asyncio.get_event_loop()
        device: Device = Device()
        addr: tuple
        connection: TcpConnection = TcpConnection()
        (
            connection.socket,
            addr,
        ) = self.tcp.accept()
        if not addr[0] in self.current_addr_connections:
            self.current_addr_connections.add(addr[0])
            connection.address["ip"] = addr[0]
            connection.address["port"] = addr[1]

            new_task: Task[DeviceTcpReturn] = loop.create_task(
                self.device_handle_local_tcp(device, connection)
            )

            loop.create_task(
                asyncio.wait_for(new_task, timeout=proc_timeout_secs)
            )

            task_log_debug(
                f"Address {connection.address['ip']} process task created."
            )
            self.__tasks_undone.append((new_task, datetime.datetime.now()))
        else:
            LOGGER.debug(f"Address {addr[0]} already in connection.")

    async def handle_connections(
        self, proc_timeout_secs: int = DEFAULT_MAX_COM_PROC_TIMEOUT_SECS
    ) -> bool:
        """Send broadcast and make tasks for incoming tcp connections.

        Params:
            proc_timeout_secs: max timeout in seconds for a device
                communication handle process

        Returns:
            true:  on success
            false: on exception or error
        """

        try:
            while not self.handle_connections_task_end_now:
                if not await self.bind_ports():
                    break
                if not self.tcp or not self.udp:
                    break
                # for debug cursor jump:
                a: bool = False
                if a:
                    break

                if self.message_queue:

                    read_broadcast_response: bool = True
                    if not await self.send_udp_broadcast():
                        read_broadcast_response = False
                        continue

                    if not read_broadcast_response:
                        await self.standby()

                    while read_broadcast_response:

                        self.__read_tcp_task = asyncio.create_task(
                            self.read_incoming_tcp_con_task()
                        )

                        task_log_debug("Reading incoming connections..")
                        try:
                            await asyncio.wait_for(
                                self.__read_tcp_task, timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            LOGGER.debug(
                                "Socket-Timeout for incoming tcp connections."
                            )

                        except socket.error:
                            LOGGER.error("Socket error!")
                            task_log_trace_ex()
                            if not await self.bind_ports():
                                LOGGER.error(
                                    "Error binding ports udp 2222 and tcp"
                                    " 3333."
                                )

                        result: tuple[
                            list[Any], list[Any], list[Any]
                        ] | None = (
                            self.__read_tcp_task.result()
                            if self.__read_tcp_task
                            else None
                        )
                        if (
                            not result
                            or not isinstance(result, tuple)
                            or not len(result) == 3
                        ):
                            task_log_debug(
                                "No incoming tcp connections read result."
                                " break"
                            )
                            break
                        readable: list[Any]
                        readable, _, _ = result if result else ([], [], [])

                        LOGGER.debug("Reading tcp port done..")

                        if self.tcp not in readable:
                            break
                        else:
                            await self.handle_incoming_tcp_connection(
                                proc_timeout_secs
                            )

                    # await self.check_messages_time_to_live()

                await self.connection_tasks_time_to_live(proc_timeout_secs)

                if not len(self.message_queue):
                    await self.standby()

        except CancelledError:
            task_log_debug("search and send to device loop cancelled.")
            self.message_queue = {}
            for task, _ in self.__tasks_undone:
                task.cancel(msg="Search and send loop cancelled.")
        except Exception as exception:
            LOGGER.error(
                "Exception on send and search loop. Stop search devices loop!"
            )
            raise exception
        task_log_debug(
            "Search devices and process incoming connnections loop ended."
        )
        return True

    async def handle_connections_task_stop(self) -> None:
        """End device search and connections handler task."""

        if self.msg_ttl_task and not self.msg_ttl_task.done():
            self.msg_ttl_task.cancel()

        while (
            self.handle_connections_task
            and not self.handle_connections_task.done()
        ):
            LOGGER.debug("stop send and search loop.")
            if self.handle_connections_task:
                self.handle_connections_task_end_now = True
                self.handle_connections_task.cancel(
                    msg="Shutdown search and send loop."
                )
            try:
                LOGGER.debug("wait for send and search loop to end.")
                await asyncio.wait_for(
                    self.handle_connections_task, timeout=0.1
                )
                LOGGER.debug("wait end for send and search loop.")
            except Exception:
                task_log_trace_ex()
            LOGGER.debug("wait end for send and search loop.")
        pass

    def search_and_send_loop_task_alive(self) -> None:
        """Ensure broadcast's and connection handler's task is alive."""
        loop: AbstractEventLoop = asyncio.get_event_loop()

        if not self.msg_ttl_task or self.msg_ttl_task.done():
            self.msg_ttl_task = loop.create_task(
                self.check_messages_time_to_live()
            )

        if (
            not self.handle_connections_task
            or self.handle_connections_task.done()
        ):
            LOGGER.debug("search and send loop task created.")
            self.handle_connections_task = loop.create_task(
                self.handle_connections()
            )
        try:
            if self.__send_loop_sleep is not None:
                self.__send_loop_sleep.cancel()
        except Exception:
            task_log_trace_ex()

    async def send_message(
        self,
        send_msgs: list[Command],
        target_device_uid: UnitId,
        time_to_live_secs: float = -1.0,
        **kwargs: Any,
    ) -> Message | None:
        """Add message to message's queue."""
        if not send_msgs:
            LOGGER.error(
                f"No message queue to send in message to {target_device_uid}!"
            )
            return None

        response_event: asyncio.Event = asyncio.Event()

        async def answer(
            msg: Message | None = None, unit_id: str = ""
        ) -> None:
            response_event.set()

        msg: Message = Message(
            datetime.datetime.now(),
            target_device_uid,
            msg_queue=send_msgs,
            callback=answer,
            time_to_live_secs=time_to_live_secs,
            **kwargs,
        )

        if not await msg.check_msg_ttl():
            return msg

        task_log_trace(
            f"new message {msg.msg_counter} target"
            f" {target_device_uid} {send_msgs}"
        )

        self.message_queue.setdefault(str(target_device_uid), []).append(msg)

        await self.send_udp_broadcast()
        self.search_and_send_loop_task_alive()

        await response_event.wait()
        return msg

    async def discover_devices(
        self,
        timeout_secs: float = 2.5,
    ) -> None:
        """Discover devices."""

        print(SEPARATION_WIDTH * "-")
        print("Search local network for devices ...")
        print(SEPARATION_WIDTH * "-")

        LOGGER.debug("discover ping start")
        # send a message to uid "all" which is fake but will get the
        # identification message from the devices in the aes_search
        # and send msg function and we can send then a real
        # request message to these discovered devices.
        await self.send_message(
            [PingCommand()],
            UnitId("all"),
            timeout_secs,
        )

    @classmethod
    def create_default(
        cls: Any,
        controller_data: ControllerData,
        server_ip: str = "0.0.0.0",
        network_interface: str | None = None,
    ) -> LocalConnectionHandler:
        """Factory for local only controller."""
        lc_hdl: LocalConnectionHandler = LocalConnectionHandler(
            controller_data,
            server_ip=server_ip,
            network_interface=network_interface,
        )

        return lc_hdl
