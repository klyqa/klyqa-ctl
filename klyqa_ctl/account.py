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
        self._attr_username: str = username
        self._attr_password: str = password
        self._attr_devices: dict[str, KlyqaDevice] = {}
        self._attr_settings: TypeJSON | None = {}
        self._attr_access_token: str = ""
        self._attr_username_cached: bool = False
        self._attr_settings_cached: bool = False
        self._attr__settings_loaded_ts: datetime.datetime | None = None
        self._attr_device_configs: dict[Any, Any] = device_configs
        self._attr_settings_lock: asyncio.Lock = asyncio.Lock()

    @property
    def settings_lock(self) -> asyncio.Lock:
        return self._attr_settings_lock
    
    @property
    def device_configs(self) -> dict[Any, Any]:
        return self._attr_device_configs
    
    @device_configs.setter
    def device_configs(self, device_configs: dict[Any, Any]) -> None:
        self._attr_device_configs = device_configs
    
    @property
    def username(self) -> str:
        return self._attr_username
    
    @username.setter
    def username(self, username: str) -> None:
        self._attr_username = username
    
    @property
    def password(self) -> str:
        return self._attr_password
    
    @password.setter
    def password(self, password: str) -> None:
        self._attr_password = password
    
    @property
    def devices(self) -> dict[str, KlyqaDevice]:
        return self._attr_devices
    
    @devices.setter
    def devices(self, devices: dict[str, KlyqaDevice]) -> None:
        self._attr_devices = devices
    
    @property
    def settings(self) -> TypeJSON | None:
        return self._attr_settings
    
    @settings.setter
    def settings(self, settings: TypeJSON | None) -> None:
        self._attr_settings = settings
    
    @property
    def access_token(self) -> str:
        return self._attr_access_token
    
    @access_token.setter
    def access_token(self, access_token: str) -> None:
        self._attr_access_token = access_token
    
    @property
    def username_cached(self) -> bool:
        return self._attr_username_cached
    
    @username_cached.setter
    def username_cached(self, username_cached: bool) -> None:
        self._attr_username_cached = username_cached
    
    @property
    def settings_cached(self) -> bool:
        return self._attr_settings_cached
    
    @settings_cached.setter
    def settings_cached(self, settings_cached: bool) -> None:
        self._attr_settings_cached = settings_cached
    
    @property
    def _settings_loaded_ts(self) -> datetime.datetime | None:
        return self._attr__settings_loaded_ts
    
    @_settings_loaded_ts.setter
    def _settings_loaded_ts(self, _settings_loaded_ts: datetime.datetime) -> None:
        self._attr__settings_loaded_ts = _settings_loaded_ts
    