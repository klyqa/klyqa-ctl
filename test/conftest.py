from __future__ import annotations

from typing import Generator

import mock
import pytest

from klyqa_ctl.communication.local.connection_handler import LocalConnectionHandler
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.general.general import TRACE, get_asyncio_loop, set_debug_logger
from klyqa_ctl.local_controller import LocalController

SUT_UNIT_ID: str = "00ac629de9ad2f4409dc"
SUT_DEVICE_KEY: str = "e901f036a5a119a91ca1f30ef5c207d6"


@pytest.fixture
def local_controller() -> Generator[LocalController, None, None]:
    """Generate a local controller standalone."""

    lc: LocalController = LocalController.create_standalone()
    yield lc
    get_asyncio_loop().run_until_complete(lc.shutdown())


TEST_UNIT_ID = "29daa5a4439969f57934"
TEST_AES_KEY = "53b962431abc7af6ef84b43802994424"
TEST_PRODUCT_ID = "@klyqa.lighting.rgb-cw-ww.e27"


@pytest.fixture
def controller_data_lc_lib() -> ControllerData:

    ctl_data: ControllerData = get_asyncio_loop().run_until_complete(
        ControllerData.create_default(interactive_prompts=False, offline=True)
    )
    ctl_data.add_aes_key(TEST_UNIT_ID, TEST_AES_KEY)

    return ctl_data


@pytest.fixture
def lc_con_hdl(
    controller_data_lc_lib,
) -> Generator[LocalConnectionHandler, None, None]:
    """Generate a local controller instance."""

    lc_hdl: LocalConnectionHandler = LocalConnectionHandler.create_default(
        controller_data=controller_data_lc_lib
    )
    with mock.patch("socket.socket"):
        get_asyncio_loop().run_until_complete(lc_hdl.bind_ports())

    yield lc_hdl
    get_asyncio_loop().run_until_complete(lc_hdl.shutdown())
