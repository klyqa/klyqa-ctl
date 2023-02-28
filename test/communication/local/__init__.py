import asyncio
from test.conftest import TEST_UNIT_ID
import time
from typing import Any

import mock

from klyqa_ctl.general.general import QCX_SYN

TEST_IP: str = "192.168.8.4"

TEST_PORT: int = 50222

DATA_IDENTITY: bytes = (
    b'\x00\xda\x00\x00{"type":"ident","ident":{"fw_version":"virtual","fw_build":"1","hw_version":"1","manufacturer_id":"59a58a9f-59ca-4c46-96fc-791a79839bc7","product_id":"@qcx.lighting.rgb-cw-ww.virtual","unit_id":"'
    + TEST_UNIT_ID.encode("utf-8")
    + b'"}}'
)


class UDPSynSocketRecvMock(mock.MagicMock):  # type: ignore[misc]
    """Mock the receive method of the UDP socket"""

    def __call__(self, *args: Any, **kwargs: Any) -> tuple:
        """Call mocked SYN send from device with 1 sec delay."""

        ret_val: bytes = QCX_SYN

        if self.call_count > 0:
            time.sleep(1.0)

        if self.call_count >= 10:
            # mock 10 syns then sleep
            asyncio.run(asyncio.sleep(1000.0))

        super().__call__(self, *args, **kwargs)
        self._mock_call(*args, **kwargs)

        return (ret_val, (TEST_IP, TEST_PORT))
