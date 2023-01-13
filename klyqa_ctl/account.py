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

from typing import Any, TypeVar

class Account:
    """

    Klyqa account
    * devices
    * account settings

    """

    # Set of current accepted connections to an IP. One connection is most of the time
    # enough to send all messages for that device behind that connection (in the aes send message method).
    # If connection is currently finishing due to sent messages and no messages left for that device and a new
    # message appears in the queue, send a new broadcast and establish a new connection.
    #

    def __init__(
        self,
        username: str = "",
        password: str = "",
        device_configs: dict = {},
    ) -> None:
        """! Initialize the account with the login data, tcp, udp datacommunicator and tcp
        communication tasks."""
        self.username: str = username
        self.password: str = password
        self.devices: dict[str, KlyqaDevice] = {}
        self.settings: TypeJSON | None = {}
        self.access_token: str = ""
        self.username_cached: bool = False
        self.settings_cached: bool = False
        self._settings_loaded_ts: datetime.datetime | None = None
        
        self.device_configs: dict[Any, Any] = device_configs
        
        self._attr_settings_lock: asyncio.Lock = asyncio.Lock()


    @property
    def settings_lock(self) -> asyncio.Lock:
        """Return the account settings lock."""
        return self._attr_settings_lock