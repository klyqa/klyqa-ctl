"""Test the LocalController class."""
from __future__ import annotations
import asyncio
from logging import INFO
from klyqa_ctl.general.general import LOGGER, logging_hdl
from klyqa_ctl.local_controller import LocalController
from klyqa_ctl.general.unit_id import UnitId

async def main() -> None:
    lc: LocalController = LocalController()

    LOGGER.setLevel(INFO)
    logging_hdl.setLevel(INFO)
    
    unit_id: UnitId = UnitId("3cbca9af8989582f2a75")
    aes_key: str = "5aefe7eda29f76e4c31af460e10ce74c"
    
    response: str = await lc.sendToDevice(unit_id, aes_key,
                        '{"type": "request"}')
    
    print(response)
    
    await lc.shutdown()
    
if __name__ == "__main__":
    asyncio.run(main())