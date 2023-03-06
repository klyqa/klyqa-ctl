"""Onboard device."""
from __future__ import annotations

import json
import os
import socket
import ssl

from klyqa_ctl.general.general import (
    TypeJson,
    task_log,
    task_log_debug,
    task_log_error,
)


def build_configuration_and_backend_url(
    ssid: str,
    pw: str,
    aes: str = "00112233445566778899AABBCCDDEEFF",
    acc_token: str = "",
    backend_url: str = "mqtt.prod.qconnex.io",
) -> str:

    if "QC_BACKEND_URL" in os.environ:
        backend_url = os.environ["QC_BACKEND_URL"]

    configuration = (
        '{"type":"configure","ssid":"'
        + ssid.encode("utf-8").hex()
        + '","password":"'
        + pw.encode("utf-8").hex()
        + '","aes_key":"'
        + aes
        + '", "access_token" : "'
        + acc_token
        + '", "backend_url" : "'
        + backend_url
        + '"}'
    )
    return configuration


class Onboard:
    """Onboard devices"""

    def __init__(self) -> None:
        pass

    def build_tcp_socket_connection(self) -> ssl.SSLSocket:
        """establish tcp connection which is used for communication during
        Onboard process
        will be called by function >onboard_device<

        Returns
        -------
        ssl.SSLSocket
            return Onboard_tcp
        """

        task_log_debug("[Onboard].Onboard: start build_tcp_socket_connection")

        sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # s.setsockopt(socket.SOL_SOCKET, 25, "wlan1".encode("utf-8"))

        context: ssl.SSLContext = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.verify_flags = ssl.VERIFY_DEFAULT.VERIFY_DEFAULT
        context.options |= 0x4

        sec_sock: ssl.SSLSocket = context.wrap_socket(
            sock, server_hostname="10.42.42.10"
        )
        sec_sock.connect(("10.42.42.10", 2223))
        sec_sock.settimeout(3)
        task_log_debug(
            "[Onboard].Onboard: build_tcp_socket_connection -> ready"
        )
        return sec_sock

    def Onboard_receive(self, sec_s: ssl.SSLSocket) -> None:
        """receive data from tcp_connection

        Parameters
        ----------
        sec_s : ssl.SSLSocket
            tcp_connection which data will be received from

        Returns
        -------
        list
            list of data, which has been fetched from tcp_connection
        """
        dbg_name: str = "[Onboard].Onboard_receive :"

        task_log_debug(str(dbg_name) + "start ")
        data: bytes = b"x"
        try:
            while len(data):
                data = sec_s.recv(65536)
                DUT_Type: str = Onboard.Lamp_typ(self, data)
                task_log_debug(
                    str(dbg_name)
                    + " data from ["
                    + str(DUT_Type)
                    + "]: "
                    + str(data)
                )

        except socket.timeout:
            task_log_debug(str(dbg_name) + "socket.timeout ")
            pass

        except Exception as e:
            tmp_log: str = (
                "---> F E H L E R  "
                + str(dbg_name)
                + ": ->  "
                + "({})".format(e)
            )  # KeyboardInterrupt:
            task_log_error(tmp_log, exc_info=True)
            pass

    def onboarding_device(self) -> None:
        """Onboarding procedure."""

        dbg_name: str = "[Onboard].onbaording: "
        task_log(str(dbg_name) + "start Onboard")
        sec_s: ssl.SSLSocket | None = None
        try:

            sec_s = Onboard.build_tcp_socket_connection(self)
            # Onboard.Onboard_receive(self, sec_s)
            tmp_str: bytes = b""

            tmp_str = b"""\0\x20\0\0{"type":"scan_wifi"}            """
            task_log_debug(str(dbg_name) + "first send  : " + str(tmp_str))
            sec_s.send(tmp_str)

            Onboard.Onboard_receive(self, sec_s)

            json: bytes = (
                b'{"type":"identify_uuid","challenge":'
                b'"00112233445566778899AABBCCDDEEFF"}'
            )
            tmp_str = b"\0\x50\0\0" + json + b"         "

            task_log_debug(str(dbg_name) + "second send  : " + str(tmp_str))
            sec_s.send(tmp_str)
            Onboard.Onboard_receive(self, sec_s)

            configuration: str = build_configuration_and_backend_url(
                "QCXLTestNET", "iotHH0049"
            )

            while len(configuration) % 16:
                configuration = configuration + " "
            low: int = len(configuration) % 256
            high: int = len(configuration) // 256

            # print("Sending: ", bytes([high, low, 0, 0]) +
            # configuration.encode('utf8'))
            tmp_str = bytes([high, low, 0, 0]) + configuration.encode("utf8")

            task_log_debug(str(dbg_name) + "Sending : " + str(tmp_str))

            sec_s.send(tmp_str)
            Onboard.Onboard_receive(self, sec_s)
            sec_s.close()
            task_log_debug(str(dbg_name) + "connection closed")

        except Exception as e:
            tmp_log: str = (
                "---> F E H L E R  "
                + str(dbg_name)
                + " ->  "
                + "({})".format(e)
            )
            task_log_error(tmp_log, exc_info=True)
            pass

        finally:
            if sec_s:
                sec_s.close()
        return

    def Lamp_typ(self, data: bytes) -> str:
        """check the wifi response for the type of KLYQA device
        Parameters
        ----------
            data
                received list from the bulb
        Returns
        -------
            list
                 type of KLYQA devices
        """

        new_data: bytes = data
        str5: str = ""

        try:
            new_data.decode()
            json_object: TypeJson = json.loads(new_data)

            if json_object["type"] == "scan_wifi_results":
                # if 'ident' in json_object and 'product_id' in
                # json_object['ident']:
                str4: str = json_object["ident"]["product_id"]
                str5 = str4.split(".")[-1]
                task_log_debug("[Onboard].Lamp_typ  : " + str(str5))

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):  # skip first unreadable message data
            pass

        return str5
