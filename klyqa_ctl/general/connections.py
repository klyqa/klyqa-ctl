"""Local and cloud connections"""

from __future__ import annotations
import datetime
import json
import socket
from typing import Any

from klyqa_ctl.devices.device import *
from klyqa_ctl.general.general import *


PROD_HOST: str = "https://app-api.prod.qconnex.io"
TEST_HOST: str = "https://app-api.test.qconnex.io"

