""" Load test for send multiple messages to multiple devices. """

import argparse
import asyncio
import datetime
import json
import random
from typing import Any

from klyqa_ctl.communication.local.connection_handler import (
    LocalConnectionHandler,
)
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.light.commands import add_command_args_bulb
from klyqa_ctl.general.general import (
    LOGGER,
    TRACE,
    DeviceType,
    set_debug_logger,
    set_logger,
    task_name,
)
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.parameters import (
    add_config_args,
    get_description_parser,
)
from klyqa_ctl.klyqa_ctl import Client


async def load_test(client: Client) -> int:

    if client.local and not await client.local.bind_ports():
        return 1

    started: datetime.datetime = datetime.datetime.now()

    uids: list[str] = [
        "29daa5a4439969f57934",
        # "286DCD5C6BDA",
        # "00ac629de9ad2f4409dc",
        # "04256291add6f1b414d1",
        "cd992e921b3646b8c18a",
        "1a8379e585321fdb8778",
    ]

    messages_answered: int = 0
    messages_sent: int = 0

    tasks: list[asyncio.Task] = []
    for u_id in uids:
        args_all: list[list[str]] = []
        args_all.append(["--request"])
        args_all.append(
            [
                "--color",
                str(random.randrange(0, 255)),
                str(random.randrange(0, 255)),
                str(random.randrange(0, 255)),
            ]
        )
        args_all.append(["--temperature", str(random.randrange(2000, 6500))])
        args_all.append(["--brightness", str(random.randrange(0, 100))])
        args_all.append(["--WW"])

        async def send_answer_cb(msg: Message, uid: str) -> None:
            nonlocal messages_answered
            if msg.answer_utf8:
                messages_answered = messages_answered + 1
                LOGGER.debug("Send_answer_cb %s", str(uid))
                LOGGER.info(
                    (f"{task_name()} - " if LOGGER.level == 10 else "")
                    + "Message answer %s: %s",
                    msg.target_uid,
                    json.dumps(
                        json.loads(msg.answer_utf8), sort_keys=True, indent=4
                    )
                    if msg
                    else "empty msg",
                )
            else:
                LOGGER.info("MSG-TTL: No answer from %s", uid)

        for args in args_all:

            parser: argparse.ArgumentParser = get_description_parser()

            args.extend(["--debug", "--local", "--device_unitids", f"{u_id}"])

            args.insert(0, DeviceType.LIGHTING.value)
            add_config_args(parser=parser)
            add_command_args_bulb(parser=parser)

            args_parsed: argparse.Namespace = parser.parse_args(args=args)

            new_task: asyncio.Task[Any] = asyncio.create_task(
                client.send_to_devices(
                    args_parsed,
                    args,
                    async_answer_callback=send_answer_cb,
                    timeout_ms=10000 * 1000,
                )
            )
            messages_sent = messages_sent + 1
            # await asyncio.wait([new_task]) # single task debug
            # await asyncio.sleep(0.1)
            tasks.append(new_task)

    for task in tasks:
        try:
            await asyncio.wait([task], timeout=0.1)
        except asyncio.TimeoutError:
            pass

    for task in tasks:
        try:
            # await asyncio.wait([task])
            await task
        except asyncio.TimeoutError:
            pass

    LOGGER.info(
        "End. Messages sent: %s, Messages answered: %s",
        messages_sent,
        messages_answered,
    )
    time_run: datetime.timedelta = datetime.datetime.now() - started
    LOGGER.info("Time diff run: %s", time_run)
    return 0


async def main() -> None:

    set_logger()
    set_debug_logger(level=TRACE)

    client: Client = await Client.create(
        interactive_prompts=True, offline=False
    )

    await load_test(client)


if __name__ == "__main__":
    asyncio.run(main())
