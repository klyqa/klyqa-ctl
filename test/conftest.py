from __future__ import annotations

from typing import Generator

import pytest

from klyqa_ctl.general.general import TRACE, set_debug_logger
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
