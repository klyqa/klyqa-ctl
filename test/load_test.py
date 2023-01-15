""" Load test for send multiple messages to multiple devices. """

import argparse
import asyncio
import datetime
import json
import random
import sys
import traceback
from typing import Any
from klyqa_ctl.account import Account
from klyqa_ctl.communication.cloud import CloudBackend
from klyqa_ctl.communication.local.communicator import LocalCommunicator
from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.light.commands import add_command_args_bulb
from klyqa_ctl.general.connections import PROD_HOST
from klyqa_ctl.general.general import LOGGER, DeviceType, task_name
from klyqa_ctl.general.message import Message
from klyqa_ctl.general.parameters import add_config_args, get_description_parser
from klyqa_ctl.klyqa_ctl import Client


async def load_test(client: Client) -> int:
        
    if client.local_communicator and not await client.local_communicator.bind_ports():
        return 1
    
    started: datetime.datetime = datetime.datetime.now()
    
    uids: list[str] = [
        "29daa5a4439969f57934",
        # "286DCD5C6BDA",
        # "00ac629de9ad2f4409dc",
        # "04256291add6f1b414d1",
        "cd992e921b3646b8c18a",
        "1a8379e585321fdb8778"
        ]
    
    messages_answered: int = 0
    messages_sent: int = 0
    
    tasks: list[asyncio.Task] = []
    for u_id in uids:
        args_all: list[list[str]] = []
        args_all.append(["--request"])
        args_all.append(["--color", str(random.randrange(0, 255)), str(random.randrange(0, 255)), str(random.randrange(0, 255))])
        args_all.append(["--temperature", str(random.randrange(2000, 6500))])
        args_all.append(["--brightness", str(random.randrange(0, 100))])
        args_all.append(["--WW"])
        
        async def send_answer_cb(msg: Message, uid: str) -> None:
            nonlocal messages_answered
            if msg.answer_utf8:
                messages_answered = messages_answered + 1
                LOGGER.debug("Send_answer_cb %s", str(uid))
                LOGGER.info((f"{task_name()} - " if LOGGER.level == 10 else "")
                    + "Message answer %s: %s",msg.target_uid, 
                    json.dumps(json.loads(msg.answer_utf8), sort_keys=True, indent=4)
                    if msg else "empty msg")
            else:
                LOGGER.info("MSG-TTL: No answer from %s", uid)
        
        for args in args_all:

            parser: argparse.ArgumentParser = get_description_parser()

            args.extend(["--local", "--device_unitids", f"{u_id}"])

            args.insert(0, DeviceType.lighting.name)
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
    
    LOGGER.info("End. Messages sent: %s, Messages answered: %s", messages_sent, messages_answered)
    time_run: datetime.timedelta = datetime.datetime.now() - started
    LOGGER.info("Time diff run: %s", time_run)
    return 0

async def main() -> None:
            
    controller_data: ControllerData = ControllerData(interactive_prompts = True, 
        offline = False)  
 
    # build offline version here.
    account = Account("frederick.stallmeyer@qconnex.com", "pass0w0rd")
    local_communicator: LocalCommunicator = LocalCommunicator(controller_data, account)
    cloud_backend: CloudBackend = CloudBackend(controller_data, account, PROD_HOST, False)
    
    if cloud_backend and not account.access_token:
        try:
            if await cloud_backend.login(print_onboarded_devices = True):
                LOGGER.debug("login finished")
            else:
                raise Exception()
        except:
            LOGGER.error("Error during login.")
            LOGGER.debug(f"{traceback.format_exc()}")
            sys.exit(1)
    
    client: Client = Client(controller_data, local_communicator, cloud_backend, account)
    await load_test(client)
    
    
if __name__ == '__main__':
    asyncio.run(main())