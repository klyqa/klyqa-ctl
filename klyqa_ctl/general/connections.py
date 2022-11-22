"""Local and cloud connections"""

from __future__ import annotations
import datetime
import json
import socket
from typing import Any
from ..devices.device import *

from .general import *

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
    from Cryptodome.Random import get_random_bytes  # pycryptodome
except:
    from Crypto.Cipher import AES  # provided by pycryptodome
    from Crypto.Random import get_random_bytes  # pycryptodome


def send_msg(msg, device: KlyqaDevice, connection: LocalConnection):
    info_str: str = (
        'Sending in local network to "'
        + device.get_name()
        + '": '
        + json.dumps(json.loads(msg), sort_keys=True, indent=4)
    )

    LOGGER.info(info_str)
    plain = msg.encode("utf-8")
    while len(plain) % 16:
        plain = plain + bytes([0x20])

    if connection.sendingAES is None:
        return False
    cipher = connection.sendingAES.encrypt(plain)

    while True:
        try:
            if connection.socket:
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

    sendingAES = None
    receivingAES = None
    address: dict[str, str | int] = {"ip": "", "port": -1}
    socket: socket.socket | None = None
    received_packages: list[Any] = []
    sent_msg_answer: dict[str, Any] = {}
    aes_key_confirmed: bool = False

    def __init__(self) -> None:
        self.state = "WAIT_IV"
        self.localIv = get_random_bytes(8)

        self.sendingAES = None
        self.receivingAES = None
        self.address = {"ip": "", "port": -1}
        self.socket = None
        self.received_packages = []
        self.sent_msg_answer = {}
        self.aes_key_confirmed = False
        self.started: datetime.datetime = datetime.datetime.now()


class CloudConnection:
    """CloudConnection"""

    received_packages = []
    connected: bool

    def __init__(self) -> None:
        self.connected = False
        self.received_packages = []


PROD_HOST = "https://app-api.prod.qconnex.io"
TEST_HOST = "https://app-api.test.qconnex.io"


class Data_communicator:
    def __init__(self, server_ip: str = "0.0.0.0") -> None:
        self.tcp: socket.socket | None = None
        self.udp: socket.socket | None = None
        self.server_ip: str = server_ip

    def shutdown(self) -> None:

        try:
            if self.tcp:
                self.tcp.shutdown(socket.SHUT_RDWR)
                self.tcp.close()
                LOGGER.debug("Closed TCP port 3333")
                self.tcp = None
        except:
            pass

        try:
            if self.udp:
                self.udp.close()
                LOGGER.debug("Closed UDP port 2222")
                self.udp = None
        except:
            pass

    async def bind_ports(self) -> bool:
        """bind ports."""
        # await tcp_udp_port_lock.acquire()
        self.shutdown()
        server_address: tuple[str, int]
        try:

            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if self.server_ip is not None:
                server_address = (self.server_ip, 2222)
            else:
                server_address = ("0.0.0.0", 2222)
            self.udp.bind(server_address)
            LOGGER.debug("Bound UDP port 2222")

        except Exception as e:
            LOGGER.error(
                "Error on opening and binding the udp port 2222 on host for initiating the device communication."
            )
            return False

        try:
            self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_address = ("0.0.0.0", 3333)
            self.tcp.bind(server_address)
            LOGGER.debug("Bound TCP port 3333")
            self.tcp.listen(1)

        except Exception as e:
            LOGGER.error(
                "Error on opening and binding the tcp port 3333 on host for initiating the device communication."
            )
            return False
        return True
