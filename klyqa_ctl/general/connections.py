"""Local and cloud connections"""

from __future__ import annotations
import datetime
import json
import socket
from typing import Any

from klyqa_ctl.devices.device import *
from klyqa_ctl.general.general import *


class CloudConnection:
    """CloudConnection"""

    received_packages: list[Any]
    connected: bool

    def __init__(self) -> None:
        self.connected = False
        self.received_packages = []

PROD_HOST: str = "https://app-api.prod.qconnex.io"
TEST_HOST: str = "https://app-api.test.qconnex.io"

