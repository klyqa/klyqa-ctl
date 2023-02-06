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
from klyqa_ctl.communication.local.data_package import (
    DataPackage,
    PackageException,
    PackageType,
)
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.commands import CommandWithCheckValues, PingCommand
from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.response_identity_message import ResponseIdentityMessage
from klyqa_ctl.general.general import (
    DEFAULT_MAX_COM_PROC_TIMEOUT_SECS,
    DEFAULT_SEND_TIMEOUT_MS,
    LOGGER,
    QCX_ACK,
    QCX_DSYN,
    QCX_SYN,
    SEND_LOOP_MAX_SLEEP_TIME,
    SEPARATION_WIDTH,
    Address,
    Command,
    ReferencePass,
    TypeJson,
    get_asyncio_loop,
    task_log,
    task_log_debug,
    task_log_error,
    task_log_trace,
    task_log_trace_ex,
    task_name,
)
from klyqa_ctl.general.message import Message, MessageState
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
        """Initialize local connection handler."""

        self._attr_controller_data: ControllerData = controller_data
        self._attr_devices: dict[str, Device] = controller_data.devices
        self._attr_tcp: socket.socket | None = None
        self._attr_udp: socket.socket | None = None
        self.udp_broadcast_task: asyncio.Task | None = None
        self.send_udp_broadcast_task_loop_set: asyncio.Event = asyncio.Event()
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
        self._attr_read_udp_socket_task_hdl: Task[None] | None = None
        self._attr_broadcast_discovery: bool = True

    @property
    def network_interface(self) -> str | None:
        """Get network interface."""

        return self._attr_network_interface

    @network_interface.setter
    def network_interface(self, network_interface: str | None) -> None:
        self._attr_network_interface = network_interface

    @property
    def broadcast_discovery(self) -> bool:
        """Get broadcast device discovery switch state."""

        return self._attr_broadcast_discovery

    @broadcast_discovery.setter
    def broadcast_discovery(self, broadcast_discovery: bool) -> None:
        self._attr_broadcast_discovery = broadcast_discovery

    @property
    def controller_data(self) -> ControllerData:
        """Get controller data."""

        return self._attr_controller_data

    @controller_data.setter
    def controller_data(self, controller_data: ControllerData) -> None:
        self._attr_controller_data = controller_data

    @property
    def devices(self) -> dict[str, Device]:
        """Get devices list."""

        return self._attr_devices

    @devices.setter
    def devices(self, devices: dict[str, Device]) -> None:
        self._attr_devices = devices

    @property
    def tcp(self) -> socket.socket | None:
        """Get TCP socket."""

        return self._attr_tcp

    @tcp.setter
    def tcp(self, tcp: socket.socket | None) -> None:
        self._attr_tcp = tcp

    @property
    def udp(self) -> socket.socket | None:
        """Get UDP socket."""

        return self._attr_udp

    @udp.setter
    def udp(self, udp: socket.socket | None) -> None:
        self._attr_udp = udp

    @property
    def server_ip(self) -> str:
        """Get server ip."""

        return self._attr_server_ip

    @server_ip.setter
    def server_ip(self, server_ip: str) -> None:
        self._attr_server_ip = server_ip

    @property
    def message_queue(self) -> dict[str, list[Message]]:
        """Get message queue."""

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
        """Get connection handle task."""

        return self._attr_handlec_connections_task

    @handle_connections_task.setter
    def handle_connections_task(
        self, handle_connections_tasks: Task | None
    ) -> None:
        self._attr_handlec_connections_task = handle_connections_tasks

    @property
    def handle_connections_task_end_now(self) -> bool:
        """Get connection handle task end now."""

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
        """Read TCP socket task."""

        return self.__attr_read_tcp_task

    @__read_tcp_task.setter
    def __read_tcp_task(self, read_tcp_task: Task | None) -> None:
        self.__attr_read_tcp_task = read_tcp_task

    @property
    def current_addr_connections(self) -> set[str]:
        """Get current address connections."""

        return self._attr_current_addr_connections

    @current_addr_connections.setter
    def current_addr_connections(
        self, current_addr_connections: set[str]
    ) -> None:
        self._attr_current_addr_connections = current_addr_connections

    async def shutdown(self) -> None:
        """Close sockets and unbind local ports."""

        await self.handle_connections_task_stop()
        if (
            self._attr_read_udp_socket_task_hdl
            and not self._attr_read_udp_socket_task_hdl.done()
        ):
            try:
                self._attr_read_udp_socket_task_hdl.cancel()
            except CancelledError:
                task_log_debug("Read UDP socket task cancelled.")

        if self.tcp:
            try:
                task_log_debug("Closing TCP port 3333")
                self.tcp.shutdown(socket.SHUT_RDWR)
                self.tcp.close()
                self.tcp = None
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error("Error on closing local tcp port 3333.")
                task_log_trace_ex()

        if self.udp:
            try:
                task_log_debug("Closing UDP port 2222")
                self.udp.close()
                self.udp = None
            except (socket.herror, socket.gaierror, socket.timeout):
                LOGGER.error("Error on closing local udp port 2222.")
                task_log_trace_ex()

    async def bind_ports(self) -> bool:
        """bind ports."""

        server_address: tuple[str, int]
        try:
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
                        "Error on opening and binding the udp port 2222 on"
                        " host for initiating the local device communication."
                    )
                    task_log_trace_ex()
                    return False
                task_log_debug("Bound UDP port 2222")
        except OSError:
            task_log_error("Could not bind the UDP Port 2222!")
            task_log_trace_ex()
            return False

        try:
            if not self.tcp:
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
                        "Error on opening and binding the tcp port 3333 on"
                        " host for initiating the local device communication."
                    )
                    task_log_trace_ex()
                    return False
                task_log_debug("Bound TCP port 3333")
                self.tcp.listen(1)
        except OSError:
            task_log_error("Could not bind the TCP port 3333!")
            task_log_trace_ex()
            return False

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
        log: list

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

        if device.u_id != "no_uid" and device.u_id not in self.devices:

            is_new_device = True
            new_dev: Device = (
                await self.controller_data.get_or_create_device_ident(
                    identity=identity
                )
            )
            new_dev.ident = identity
            if (
                type(new_dev) == Device
            ):  # pylint: disable=unidiomatic-typecheck
                log = [
                    "Found new device %s but don't know the product id %s.",
                    identity.unit_id,
                    identity.product_id,
                ]
                LOGGER.info(*log)
                task_log_debug(*log)
            else:
                if is_new_device:
                    log = ["Found new device %s", identity.unit_id]
                    LOGGER.info(*log)
                    task_log_debug(*log)

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
        device.local_con = self

        if (
            device.u_id not in self.message_queue
            or not self.message_queue[device.u_id]
        ):
            if device.u_id in self.message_queue:
                del self.message_queue[device.u_id]
            return DeviceTcpReturn.NO_MESSAGE_TO_SEND

        if not is_new_device and device.ident:
            task_log(f"Found device {device.ident.unit_id}")
        loop: asyncio.AbstractEventLoop = get_asyncio_loop()

        if "all" in self.controller_data.aes_keys:
            connection.aes_key = self.controller_data.aes_keys["all"]
        elif (
            isinstance(self.controller_data.aes_keys, dict)
            and device.u_id in self.controller_data.aes_keys
        ):
            connection.aes_key = self.controller_data.aes_keys[device.u_id]
        else:
            task_log_error("No AES key for device %s! Removing it's messages.")
            for uid, msg in self.message_queue.items():
                if uid == device.uid:
                    task_log_debug(
                        "Removing message %s",
                        msg,
                    )
                    self.remove_msg_from_queue(msg, device)

        try:
            if connection.socket is not None:
                task_log_debug("Sending local initial vector.")
                iv_data: bytes = DataPackage.create(
                    connection.local_iv, PackageType.IV
                ).serialize()
                await loop.sock_sendall(connection.socket, iv_data)
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

            if msg_sent and device is not None:
                await msg_sent.call_cb()
                task_log_debug(
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
        """Remove message from message queue."""

        if not device:
            return
        if msg not in self.message_queue[device.u_id]:
            return

        task_log("remove message from queue")
        self.message_queue[device.u_id].remove(msg)
        # msg.state = MessageState.SENT

        if (
            device.u_id in self.message_queue
            and not self.message_queue[device.u_id]
        ):
            del self.message_queue[device.u_id]

    async def _send_msg(
        self,
        connection: TcpConnection,
        device: Device,
        msg_to_sent_r: ReferencePass,
    ) -> DeviceTcpReturn:
        """Select message to send and check the values range limits."""

        msg: Message | None = None
        return_val: DeviceTcpReturn = DeviceTcpReturn.NO_ERROR

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

                msg_to_sent_r.ref = msg

                command: Command = msg.msg_queue[j]
                text: str = command.msg_str()
                if isinstance(command, CommandWithCheckValues):
                    cwcv: CommandWithCheckValues = command
                    if (
                        not cwcv._force  # pylint: disable=protected-access
                        and not cwcv.check_values(device=device)
                    ):
                        msg.state = MessageState.VALUE_RANGE_LIMITS
                        self.remove_msg_from_queue(msg, device)
                        return DeviceTcpReturn.MSG_VALUES_OUT_OF_RANGE_LIMITS

                try:
                    if await connection.encrypt_and_send_msg(text, device):

                        return_val = DeviceTcpReturn.NO_ERROR
                        j = j + 1
                        msg.msg_queue_sent.append(text)

                        msg.state = MessageState.SENT
                        self.remove_msg_from_queue(msg, device)
                    else:
                        LOGGER.error("Could not send message!")
                        return DeviceTcpReturn.SEND_ERROR

                except socket.error:
                    LOGGER.error("Socket error while trying to send message!")
                    task_log_trace_ex()
                    return DeviceTcpReturn.SEND_ERROR

            else:
                self.remove_msg_from_queue(msg, device)

        return return_val

    async def handle_connection(
        self,
        device_ref: ReferencePass,
        connection: TcpConnection,
        msg_sent_r: ReferencePass,
    ) -> DeviceTcpReturn:
        """
        Make AES handshake.
        Getting the identity of the device.
        Send the commands in message queue to the device with the device u_id
        or to any device.

        Params:
            device: Device reference - (initial) device object with the tcp
                connection
            connection - TCP connection tunnel to the device
            msg_sent_r - Message reference object to send

        Returns: DeviceTcpReturn
        """

        device: Device = device_ref.ref
        if device is None or connection.socket is None:
            return DeviceTcpReturn.UNKNOWN_ERROR

        data: bytes = b""
        return_val: DeviceTcpReturn = DeviceTcpReturn.NOTHING_DONE
        communication_finished: bool = False

        if msg_sent_r.ref and msg_sent_r.ref.state == MessageState.ANSWERED:
            msg_sent_r.ref = None

        while not communication_finished and (
            device.u_id == "no_uid"
            or type(device) == Device  # pylint: disable=unidiomatic-typecheck
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
                return_val = await self._send_msg(
                    connection, device_ref.ref, msg_sent_r
                )
                if return_val != DeviceTcpReturn.NO_ERROR:
                    return return_val

            data_ref: ReferencePass = ReferencePass(data)
            read_data_ret: DeviceTcpReturn = (
                await connection.read_local_tcp_socket(data_ref)
            )
            if read_data_ret != DeviceTcpReturn.NO_ERROR:
                return read_data_ret
            data = data_ref.ref

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
        try:
            package: DataPackage = DataPackage.deserialize(data_ref.ref)
        except PackageException:
            return DeviceTcpReturn.RESPONSE_ERROR

        data_ref.ref = data_ref.ref[4 + package.length :]

        if (
            connection.state == AesConnectionState.WAIT_IV
            and package.ptype == PackageType.PLAIN
        ):

            return_val = await self.process_device_identity_package(
                connection, package.data, device_ref
            )
            if return_val != DeviceTcpReturn.NO_ERROR:
                return return_val

        if (
            connection.state == AesConnectionState.WAIT_IV
            and package.ptype == PackageType.IV
        ):
            return_val = await self.process_aes_initial_vector_package(
                connection, package.data, device_ref.ref
            )
            if return_val != DeviceTcpReturn.NO_ERROR:
                return return_val

        elif (
            connection.state == AesConnectionState.CONNECTED
            and package.ptype == PackageType.ENC
        ):
            return_val = await self.process_message_answer_package(
                connection, package.data, device_ref.ref, msg_sent
            )
        else:
            task_log_debug(
                "No answer to process. Waiting on answer of the device ... "
            )
        return return_val

    async def device_handle_local_tcp(
        self, device: Device, connection: TcpConnection
    ) -> DeviceTcpReturn:
        """Handle the incoming tcp connection to the device."""

        return_state: DeviceTcpReturn = DeviceTcpReturn.NOTHING_DONE

        r_device: ReferencePass = ReferencePass(device)
        msg_to_sent_ref: ReferencePass = ReferencePass(None)

        task_log_debug(f"New tcp connection to device at {connection.address}")
        try:
            return_state = await self.handle_connection(
                r_device, connection=connection, msg_sent_r=msg_to_sent_ref
            )
        except CancelledError:
            LOGGER.error(
                "Cancelled local send to %s!", connection.address["ip"]
            )
        except Exception as exception:
            task_log_trace_ex()
            task_log_error(
                "Unhandled exception during local communication! "
                + str(type(exception))
            )
            msg_to_sent_ref.ref.exception = exception
        finally:

            msg_to_sent: Message | None = msg_to_sent_ref.ref

            if msg_to_sent:
                # release message wait for callback
                await msg_to_sent.call_cb()

                if return_state in [
                    DeviceTcpReturn.TCP_SOCKET_CLOSED_UNEXPECTEDLY
                ]:
                    # Something bad could have happened with the device.
                    # Remove the message precautiously from the
                    # message queue.
                    if msg_to_sent:
                        self.remove_msg_from_queue(msg_to_sent, device)

            device = r_device.ref
            if connection.socket is not None:
                try:
                    connection.socket.shutdown(socket.SHUT_RDWR)
                    connection.socket.close()
                finally:
                    connection.socket = None
            self.current_addr_connections.remove(str(connection.address["ip"]))

            unit_id: str = f" Unit-ID: {device.u_id}" if device.u_id else ""

            if str(device.u_id) in self.devices:
                device_b: Device = self.devices[device.u_id]
                device_b.use_unlock()

            elif return_state == DeviceTcpReturn.UNKNOWN_ERROR:
                LOGGER.error(
                    "Unknown error during send (and handshake) with"
                    " device %s.",
                    unit_id,
                )

            task_log(
                "Finished tcp connection to device"
                f" {connection.address['ip']} with return state:"
                f" {return_state}"
            )

        return return_state

    async def reconnect_socket_udp(self) -> None:
        """Reconnect UDP socket."""

        if self.udp:
            self.udp.close()
            self.udp = None
        if not await self.bind_ports():
            raise socket.error

    async def reconnect_socket_tcp(self) -> None:
        """Reconnect TCP socket."""

        if self.tcp:
            self.tcp.close()
            self.tcp = None
        if not await self.bind_ports():
            raise socket.error

    async def read_udp_socket(self) -> None:
        """Read UDP socket for incoming syns."""

        loop: AbstractEventLoop = get_asyncio_loop()
        if not self.udp:
            return

        data: bytes
        addr_tup: tuple
        address: Address
        while True:
            data, addr_tup = await loop.run_in_executor(
                None, self.udp.recvfrom, 4096
            )
            address = Address(*addr_tup)
            task_log_debug(
                "Received UDP package %r from %s.", data, address.__dict__
            )
            if data == QCX_SYN or data == QCX_DSYN:
                try:
                    ack_data: bytes = QCX_ACK
                    task_log_debug(
                        "Send %r to %s.", ack_data, address.__dict__
                    )
                    self.udp.sendto(ack_data, addr_tup)
                except socket.error:
                    await self.reconnect_socket_udp()

    async def send_udp_broadcast_task(self) -> bool:
        """Send qcx-syn broadcast on udp socket."""

        loop: AbstractEventLoop = get_asyncio_loop()
        try:
            if not await self.bind_ports():
                return False
        except Exception as ex:
            task_log_trace_ex()
            task_log_error(
                "Error binding the UDP port 2222 and TCP port 3333!"
            )
            return False

        try:
            task_log_debug("Broadcasting QCX-SYN Burst")
            if self.udp:
                await loop.run_in_executor(
                    None,
                    self.udp.sendto,
                    QCX_SYN,
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

    async def send_udp_broadcast_task_loop(self) -> None:
        """Send UDP broadcast in a loop with timeout or when event lock set."""

        while True:
            await self.send_udp_broadcast_task()
            self.send_udp_broadcast_task_loop_set.clear()
            try:
                await asyncio.wait_for(
                    self.send_udp_broadcast_task_loop_set.wait(), timeout=1
                )
            except asyncio.TimeoutError:
                pass

    async def send_udp_broadcast(self) -> None:
        """Start send UDP broadcasts for discover."""

        loop: AbstractEventLoop = get_asyncio_loop()

        if self.udp_broadcast_task is None or self.udp_broadcast_task.done():
            self.udp_broadcast_task = loop.create_task(
                self.send_udp_broadcast_task_loop()
            )
        else:
            self.send_udp_broadcast_task_loop_set.set()

    async def standby(self) -> None:
        """Standby search devices and create incoming connection tasks."""

        loop: AbstractEventLoop = get_asyncio_loop()
        try:
            task_log_debug("sleep task create (broadcasts)..")
            self.__send_loop_sleep = loop.create_task(
                asyncio.sleep(
                    SEND_LOOP_MAX_SLEEP_TIME
                    if (len(self.message_queue) > 0)
                    else 1000000000
                )
            )

            task_log_debug("sleep task wait..")
            await asyncio.wait([self.__send_loop_sleep])

            task_log_debug("sleep task done..")
        except CancelledError:
            task_log_debug("sleep cancelled1.")

    async def read_incoming_tcp_con_task(
        self,
    ) -> tuple[list[Any], list[Any], list[Any]] | None:
        """Read incoming connections on tcp socket."""

        loop: AbstractEventLoop = get_asyncio_loop()

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
            task_log_debug("cancelled tcp reading.")
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

    def check_messages_ttl_task_alive(self) -> None:
        """Ensure task for checking messages in queue are not end of live."""

        loop: AbstractEventLoop = get_asyncio_loop()

        if not self.msg_ttl_task or self.msg_ttl_task.done():
            self.msg_ttl_task = loop.create_task(
                self.check_messages_time_to_live()
            )

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
                        task_log_debug(
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
        loop: AbstractEventLoop = get_asyncio_loop()
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
            task_log_debug(f"Address {addr[0]} already in connection.")

    async def read_udp_socket_task(self) -> None:
        """Start read UDP socket for incoming syncs, when not running."""

        if (
            self._attr_read_udp_socket_task_hdl
            and not self._attr_read_udp_socket_task_hdl.done()
        ):
            return
        loop: AbstractEventLoop = get_asyncio_loop()
        self._attr_read_udp_socket_task_hdl = loop.create_task(
            self.read_udp_socket()
        )

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
                stop: bool = False
                if stop:
                    break

                await self.read_udp_socket_task()
                if self.message_queue:
                    read_incoming_connections: bool = True

                    if self.broadcast_discovery:
                        await self.send_udp_broadcast()

                    if not read_incoming_connections:
                        await self.standby()

                    while read_incoming_connections:
                        self.__read_tcp_task = asyncio.create_task(
                            self.read_incoming_tcp_con_task()
                        )

                        task_log_debug("Reading incoming connections..")
                        try:
                            await asyncio.wait_for(
                                self.__read_tcp_task, timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            task_log_debug(
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

                        task_log_debug("Reading tcp port done..")

                        if self.tcp not in readable:
                            break
                        else:
                            await self.handle_incoming_tcp_connection(
                                proc_timeout_secs
                            )

                    self.check_messages_ttl_task_alive()

                await self.connection_tasks_time_to_live(proc_timeout_secs)
                if self.udp_broadcast_task:
                    self.udp_broadcast_task.cancel()

                if not self.message_queue:
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
            task_log_trace_ex()
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
            task_log_debug("stop send and search loop.")
            if self.handle_connections_task:
                self.handle_connections_task_end_now = True
                self.handle_connections_task.cancel(
                    msg="Shutdown search and send loop."
                )
            try:
                task_log_debug("wait for send and search loop to end.")
                await asyncio.wait_for(
                    self.handle_connections_task, timeout=0.1
                )
                task_log_debug("wait end for send and search loop.")
            except Exception:
                task_log_trace_ex()
            task_log_debug("wait end for send and search loop.")

    def search_and_send_loop_task_alive(self) -> None:
        """Ensure broadcast's and connection handler's task is alive."""
        loop: AbstractEventLoop = get_asyncio_loop()

        self.check_messages_ttl_task_alive()

        if (
            not self.handle_connections_task
            or self.handle_connections_task.done()
        ):
            task_log_debug("search and send loop task created.")
            self.handle_connections_task = loop.create_task(
                self.handle_connections()
            )
        try:
            if self.__send_loop_sleep is not None:
                self.__send_loop_sleep.cancel()
        except Exception:
            task_log_trace_ex()

    async def send_command_to_device(
        self,
        unit_id: UnitId,
        send_msgs: list[Command],
        aes_key: str = "",
        time_to_live_secs: float = DEFAULT_SEND_TIMEOUT_MS,
        **kwargs: Any,
    ) -> Message | None:
        """Add message to message's queue."""
        if not send_msgs:
            LOGGER.error("No message queue to send in message to %s!", unit_id)
            return None

        if aes_key:
            self.controller_data.aes_keys[str(unit_id)] = bytes.fromhex(
                aes_key
            )

        response_event: asyncio.Event = asyncio.Event()

        async def answer(
            msg: Message | None = None, unit_id: str = ""
        ) -> None:
            response_event.set()

        msg: Message = Message(
            datetime.datetime.now(),
            unit_id,
            msg_queue=send_msgs,
            callback=answer,
            time_to_live_secs=time_to_live_secs,
            **kwargs,
        )

        if not await msg.check_msg_ttl():
            return msg

        task_log_trace(
            f"new message {msg.msg_counter} target {unit_id} {send_msgs}"
        )

        self.message_queue.setdefault(str(unit_id), []).append(msg)

        await self.send_udp_broadcast()
        self.search_and_send_loop_task_alive()

        await response_event.wait()
        return msg

    async def send_to_device(
        self,
        unit_id: str,
        command: str,
        key: str,
        time_to_live_secs: float = DEFAULT_SEND_TIMEOUT_MS,
    ) -> str:
        """Sends command string to device with unit id and aes key."""

        self.controller_data.aes_keys[str(unit_id)] = bytes.fromhex(key)

        msg_answer: str = ""
        command_obj: Command = Command(_json=json.loads(command))

        msg: Message | None = await self.send_command_to_device(
            send_msgs=[command_obj],
            unit_id=UnitId(unit_id),
            time_to_live_secs=time_to_live_secs,
        )
        if msg:
            if msg.exception:
                raise msg.exception
            msg_answer = msg.answer_utf8

        return msg_answer

    async def discover_devices(
        self,
        timeout_secs: float = 2.5,
    ) -> None:
        """Discover devices."""

        print(SEPARATION_WIDTH * "-")
        print("Search local network for devices ...")
        print(SEPARATION_WIDTH * "-")

        task_log_debug("discover ping start")
        # send a message to uid "all" which is fake but will get the
        # identification message from the devices in the aes_search
        # and send msg function and we can send then a real
        # request message to these discovered devices.
        await self.send_command_to_device(
            UnitId("all"),
            [PingCommand()],
            time_to_live_secs=timeout_secs,
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
