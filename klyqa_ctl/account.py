#!/usr/bin/env python3
"""Klyqa account"""
from __future__ import annotations
import asyncio
import datetime
from klyqa_ctl.devices.device import KlyqaDevice
from klyqa_ctl.general.general import TypeJSON

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
except:
    from Crypto.Cipher import AES  # provided by pycryptodome

from typing import TypeVar

class Account:
    """

    Klyqa account
    * devices
    * account settings

    """

    host: str
    access_token: str
    username: str
    password: str
    username_cached: bool

    devices: dict[str, KlyqaDevice]

    settings: TypeJSON | None
    settings_cached: bool

    __settings_lock: asyncio.Lock
    _settings_loaded_ts: datetime.datetime | None

    # Set of current accepted connections to an IP. One connection is most of the time
    # enough to send all messages for that device behind that connection (in the aes send message method).
    # If connection is currently finishing due to sent messages and no messages left for that device and a new
    # message appears in the queue, send a new broadcast and establish a new connection.
    #

    def __init__(
        self,
        username: str = "",
        password: str = "",
        offline: bool = False,
        device_configs: dict = {},
    ) -> None:
        """! Initialize the account with the login data, tcp, udp datacommunicator and tcp
        communication tasks."""
        self.username = username
        self.password = password
        self.devices = {}
        self.settings = {}
        self.access_token: str = ""
        self.username_cached = False
        self.settings_cached = False
        self._settings_loaded_ts = None
        
        self.offline = offline
        self.device_configs = device_configs
        
        self.__settings_lock: asyncio.Lock  = asyncio.Lock()
