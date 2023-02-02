"""Test the LocalController class with various commands."""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any

from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.light.commands import (
    BrightnessCommand,
    ColorCommand,
    FwUpdateCommand,
    PingCommand,
    RequestCommand,
    RoutineDeleteCommand,
    RoutineListCommand,
    RoutinePutCommand,
    RoutineStartCommand,
    TemperatureCommand,
)
from klyqa_ctl.devices.light.light import Light
from klyqa_ctl.devices.light.scenes import SCENES
from klyqa_ctl.general.general import (  # AES_KEY_DEV,
    AES_KEY_DEV,
    AES_KEY_DEV_BYTES,
    LOGGER,
    TRACE,
    RgbColor,
    get_asyncio_loop,
    set_debug_logger,
)
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.unit_id import UnitId
from klyqa_ctl.local_controller import LocalController

# async def discover(con: LocalConnectionHandler, timeout: float = 0.3) -> None:

#     loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
#     if con:
#         try:
#             await asyncio.wait_for(
#                 loop.create_task(
#                     con.send_message([PingCommand()], UnitId("all"), timeout)
#                 ),
#                 timeout=timeout,
#             )
#         except asyncio.TimeoutError:
#             pass


def main() -> None:
    """Main."""

    set_debug_logger(TRACE)

    print(AES_KEY_DEV_BYTES.hex())
    print(AES_KEY_DEV)

    loop: asyncio.AbstractEventLoop = get_asyncio_loop()

    lc: LocalController = LocalController.create_standalone(
        network_interface="eth0", interactive_prompts=False
    )

    if lc.connection_hdl:
        loop.run_until_complete(lc.connection_hdl.discover_devices(0.3))

    dev: Device | None = None
    if "00ac629de9ad2f4409dc" in lc.controller_data.devices:
        dev = lc.controller_data.devices["00ac629de9ad2f4409dc"]

    # lc.controller_data.device_configs["@qcx.lighting.rgb-cw-ww.virtual"]
    unit_id: UnitId = UnitId("00ac629de9ad2f4409dc")
    aes_key: str = "e901f036a5a119a91ca1f30ef5c207d6"

    req_color: ColorCommand = ColorCommand(
        color=RgbColor(random.randrange(0, 255), 22, 122), transition_time=4000
    )  # , force=True)json

    reply: str = lc.send_to_device(
        str(unit_id), aes_key, json.dumps(req_color.json())
    )

    if dev:
        light: Light = dev

        light.local_con = lc.connection_hdl
        if light.local_con:

            ret: Message | None = loop.run_until_complete(
                light.send_msg_local([PingCommand()], 3333)
            )
            if ret:
                reply = ret.answer_utf8
            print(reply)

            ret = loop.run_until_complete(
                light.send_msg_local([req_color], 3333)
            )
            if ret:
                reply = ret.answer_utf8
            print(reply)


async def async_main() -> None:
    """Async main."""

    set_debug_logger(TRACE)
    # rc: RoutinePutCommand = RoutinePutCommand(action="put")
    # print(rc.json())

    # rc2 = RoutineListCommand()
    # print(rc2.json())

    # rcp = RoutinePutCommand(
    #     id="ok", commands=SCENES[0]["commands"], scene=SCENES[0]["label"]
    # )
    # print(rcp.json())

    # rc3 = RoutineStartCommand(id="ok")
    # print(rc3.json())

    # rdc = RoutineDeleteCommand(id="ok")
    # print(rdc.json())

    loop: asyncio.AbstractEventLoop = get_asyncio_loop()

    lc: LocalController = LocalController.create_standalone(
        network_interface="eth0", interactive_prompts=False
    )
    # lc.controller_data.device_configs["@qcx.lighting.rgb-cw-ww.virtual"]
    unit_id: UnitId = UnitId("00ac629de9ad2f4409dc")
    aes_key: str = "e901f036a5a119a91ca1f30ef5c207d6"

    req_color: ColorCommand = ColorCommand(
        color=RgbColor(random.randrange(0, 255), 22, 122), transition_time=4000
    )  # , force=True)json
    lc.send_to_device(str(unit_id), aes_key, json.dumps(req_color.json()))

    sends: list = [
        # (
        #     unit_id,
        #     aes_key,
        #     BrightnessCommand(brightness=random.randrange(0, 100)),
        # ),
        (
            unit_id,
            aes_key,
            TemperatureCommand(temperature=random.randrange(2500, 6000)),
        ),
        # (
        #     unit_id,
        #     aes_key,
        #     FwUpdateCommand(
        #         url=(
        #             "http://firmware.prod.qconnex.io/firmware/download/"
        #             "814c9be3-b929-4848-bc80-709da52a14c6?inline=true"
        #         )
        #     ),
        # ),
        # (
        #     unit_id,
        #     aes_key,
        #     PingCommand(),
        # ),
        # (
        #     unit_id,
        #     aes_key,
        #     req_color,
        # ),
        # (
        #     unit_id,
        #     aes_key,
        #     RequestCommand(),
        # ),
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
    responds: dict = {}
    tasks: list = []

    count: int = 0
    # for s in sends:
    #     tasks.append(
    #         (
    #             count,
    #             s[0],
    #             loop.create_task(lc.sendToDevice(s[0], s[1], str(s[2]))),
    #         )
    #     )
    #     count = count + 1
    for s in sends:
        tasks.append(
            (count, s[0], loop.create_task(lc.send_to_device_native(*s)))
        )
        count = count + 1

    await asyncio.wait([t for c, u_id, t in tasks])

    t: asyncio.Task[Any]
    for count, u_id, t in tasks:
        responds[t.get_name()] = t.result()
        LOGGER.info(f"{t.get_name()}: {count} {u_id} {t.result()}")

    # print(response)
    # await asyncio.sleep(1.2)

    await lc.shutdown()


if __name__ == "__main__":
    main()
    # loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    # loop.run_until_complete(async_main())
