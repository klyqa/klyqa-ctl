from __future__ import annotations

from typing import Generator

import pytest

from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.general.general import TRACE, get_asyncio_loop, set_debug_logger
from klyqa_ctl.local_controller import LocalController

SUT_UNIT_ID: str = "00ac629de9ad2f4409dc"
SUT_DEVICE_KEY: str = "e901f036a5a119a91ca1f30ef5c207d6"


class LcSingleton:
    """LocalController singleton for pytests"""

    _instance: LcSingleton | None = None
    lc: LocalController = LocalController.create_standalone()

    def __init__(self) -> None:
        raise RuntimeError("Call instance() instead")

    @classmethod
    def instance(cls) -> LcSingleton:
        """Singleton creator"""

        if cls._instance is None:
            print("Creating new LC instance")
            cls._instance = cls.__new__(cls)

            cls._instance.lc = LocalController.create_standalone()
        return cls._instance


@pytest.fixture
def local_controller() -> Generator[LocalController, None, None]:
    """Generate a local controller instance with debug logger."""

    set_debug_logger(level=TRACE)
    _local_controller: LcSingleton = LcSingleton.instance()
    yield _local_controller.lc


TEST_UNIT_ID = "29daa5a4439969f57934"
TEST_AES_KEY = "53b962431abc7af6ef84b43802994424"


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
    lc_hdl

    yield lc_hdl
    get_asyncio_loop().run_until_complete(lc_hdl.shutdown())
