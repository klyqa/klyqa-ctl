"""Test the LocalController class."""
from __future__ import annotations
import asyncio
from logging import DEBUG, INFO
import random
from typing import Any
from klyqa_ctl.communication.local.communicator import LocalCommunicator
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.light.commands import ColorCommand, RequestCommand
from klyqa_ctl.general.general import LOGGER, RgbColor, logging_hdl, task_log_debug, task_log_error
from klyqa_ctl.local_controller import LocalController
from klyqa_ctl.general.unit_id import UnitId

async def main() -> None:
    # controller_data: ControllerData = ControllerData(interactive_prompts = False, offline = True)
    # await controller_data.init()
    # lcc: LocalCommunicator = LocalCommunicator(
    #     controller_data, None, server_ip = "0.0.0.0")
    
    # lc: LocalController = LocalController(lcc)
    lc = await LocalController.create_local_only(interactive_prompts = False)
    loop = asyncio.get_running_loop()
    # lc.controller_data.device_configs["@qcx.lighting.rgb-cw-ww.virtual"]

    LOGGER.setLevel(INFO)
    logging_hdl.setLevel(INFO)
    REQ = ColorCommand(colors=RgbColor(random.randrange(0, 255), 22, 122), transition_time=0) #, force=True)
    sends = [
        (UnitId("00ac629de9ad2f4409dc"),
            "e901f036a5a119a91ca1f30ef5c207d6",
            REQ
            ),
        (UnitId("00ac629de9ad2f4409dc"),
            "e901f036a5a119a91ca1f30ef5c207d6",
            RequestCommand()),
        # (UnitId("3cbca9af8989582f2a75"),
        #     "5aefe7eda29f76e4c31af460e10ce74c",
        #     REQ),
        # (UnitId("29daa5a4439969f57934"),
        #     "53b962431abc7af6ef84b43802994424",
        #     REQ),
        # (UnitId("29daa5a4439969f57934"),
        #     "53b962431abc7af6ef84b43802994424",
        #     RequestCommand()),
    ]
    responds = {}
    tasks = []
    
    count = 0
    # for s in sends:
    #     tasks.append((count, s[0], loop.create_task(lc.sendToDevice(s[0], s[1],
    #         str(s[2])))))
    #     count = count + 1
    for s in sends:
        tasks.append((count, s[0], loop.create_task(lc.sendToDeviceNative(*s))))
        count = count + 1
        
    await asyncio.wait([t for c, u_id, t in tasks])
    
    t: asyncio.Task[Any]
    for count, u_id, t in tasks:
        responds[t.get_name()] = t.result()
        print(f"{t.get_name()}: {count} {u_id} {t.result()}")
        
    # print(response)
    # await asyncio.sleep(1.2)
    
    await lc.shutdown()
    
if __name__ == "__main__":
    asyncio.run(main())