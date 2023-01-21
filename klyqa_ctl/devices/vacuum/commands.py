"""Vacuum cleaner commands"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Callable
from klyqa_ctl.devices.light.commands import RequestCommand
from klyqa_ctl.devices.vacuum import VcSuctionStrengths, VcWorkingMode, CommandType
from klyqa_ctl.general.general import LOGGER, CommandTyped, TypeJson
from klyqa_ctl.general.general import CommandType as MessageCommandType

@dataclass
class ProductinfoCommand(RequestCommand):        
    def productinfo_json(self) -> TypeJson:
            return {"action": "productinfo"}
            
    def json(self) -> TypeJson:
        return super().json() | self.productinfo_json()

@dataclass
class RequestGetCommand(RequestCommand):
    def get_json(self) -> TypeJson:
            return {"action": "get"}
            
    def json(self) -> TypeJson:
        return super().json() | self.get_json()

@dataclass
class RequestResetCommand(RequestCommand):
    def reset_json(self) -> TypeJson:
            return {"action": "reset"}
            
    def json(self) -> TypeJson:
        return super().json() | self.reset_json()

@dataclass
class RequestSetCommand(RequestCommand):
    def set_json(self) -> TypeJson:
            return {"action": "set"}
            
    def json(self) -> TypeJson:
        return super().json() | self.set_json()
        
class RoutineCommandActions(str, Enum):
    ACTION = "action"
    COUNT = "count"
    LIST = "list"
    DELETE = "delete"
    START = "start"
    PUT = "put"

@dataclass
class RoutineCommand(RequestCommand):
    type: MessageCommandType = MessageCommandType.ROUTINE
    action: RoutineCommandActions = RoutineCommandActions.ACTION
    id: str | None = None
    scene: str | None = None
    commands: str | None = None

    def routine_json(self) -> TypeJson:
        r: TypeJson = TypeJson()
        r["action"] = self.action
        if self.id is not None:
            r["id"] = self.id
        if self.scene is not None:
            r["scene"] = self.scene
        if self.commands is not None:
            r["commands"] = self.commands
        return r
            
    def json(self) -> TypeJson:
        return super().json() | self.routine_json()


async def create_device_message(
    args: argparse.Namespace,
    args_in: list[Any],
    send_to_devices_callable: Callable[[argparse.Namespace], Any],
    message_queue_tx_local: list[Any],
    message_queue_tx_command_cloud: list[Any],
    message_queue_tx_state_cloud: list[Any],
) -> None:
    """process_args_to_msg_cleaner"""

    def local_and_cloud_command_msg(json_msg: TypeJson, timeout: int) -> None:
        message_queue_tx_local.append((json.dumps(json_msg), timeout))
        message_queue_tx_command_cloud.append(json_msg)

    if args.command is not None:

        if args.command == "productinfo":
            local_and_cloud_command_msg(
                ProductinfoCommand().json(), 100
            )

        if args.command == CommandType.GET.name:
            get_command(args, local_and_cloud_command_msg)

        elif args.command == CommandType.SET.name:
            set_command(args, local_and_cloud_command_msg)

        elif args.command == CommandType.RESET.name:
            reset_command(args, local_and_cloud_command_msg)

        elif args.command == "routine":
            routine(args)

def get_command(args: argparse.Namespace, local_and_cloud_command_msg: Callable) -> None:
    """Get command."""
    
    get_dict: dict[str, Any] = RequestGetCommand().json()
    if args.power or args.all:
        get_dict["power"] = None
    if args.cleaning or args.all:
        get_dict["cleaning"] = None
    if args.beeping or args.all:
        get_dict["beeping"] = None
    if args.battery or args.all:
        get_dict["battery"] = None
    if args.sidebrush or args.all:
        get_dict["sidebrush"] = None
    if args.rollingbrush or args.all:
        get_dict["rollingbrush"] = None
    if args.filter or args.all:
        get_dict["filter"] = None
    if args.carpetbooster or args.all:
        get_dict["carpetbooster"] = None
    if args.area or args.all:
        get_dict["area"] = None
    if args.time or args.all:
        get_dict["time"] = None
    if args.calibrationtime or args.all:
        get_dict["calibrationtime"] = None
    if args.workingmode or args.all:
        get_dict["workingmode"] = None
    if args.workingstatus or args.all:
        get_dict["workingstatus"] = None
    if args.suction or args.all:
        get_dict["suction"] = None
    if args.water or args.all:
        get_dict["water"] = None
    if args.direction or args.all:
        get_dict["direction"] = None
    if args.errors or args.all:
        get_dict["errors"] = None
    if args.cleaningrec or args.all:
        get_dict["cleaningrec"] = None
    if args.equipmentmodel or args.all:
        get_dict["equipmentmodel"] = None
    if args.alarmmessages or args.all:
        get_dict["alarmmessages"] = None
    if args.commissioninfo or args.all:
        get_dict["commissioninfo"] = None
    if args.mcu or args.all:
        get_dict["mcu"] = None
    local_and_cloud_command_msg(get_dict, 1000)

def reset_command(args: argparse.Namespace, local_and_cloud_command_msg: Callable) -> None:
    """Reset command."""
    
    reset_dict: dict[str, Any] = RequestResetCommand().json()
    
    if args.sidebrush:
        reset_dict["sidebrush"] = None
    if args.rollingbrush:
        reset_dict["rollingbrush"] = None
    if args.filter:
        reset_dict["filter"] = None
    local_and_cloud_command_msg(reset_dict, 1000)

def set_command(args: argparse.Namespace, local_and_cloud_command_msg: Callable) -> None:
    """Set command."""
    
    set_dict: dict[str, Any] = RequestSetCommand().json()
   
    if args.power is not None:
        set_dict["power"] = args.power
    if args.cleaning is not None:
        set_dict["cleaning"] = args.cleaning
    if args.beeping is not None:
        set_dict["beeping"] = args.beeping
    if args.carpetbooster is not None:
        set_dict["carpetbooster"] = args.carpetbooster
    if args.workingmode is not None:
        mode: int = VcWorkingMode[args.workingmode].value
        set_dict["workingmode"] = mode
    if args.suction is not None:
        suction: int = VcSuctionStrengths[args.suction].value
        set_dict["suction"] = suction - 1
    if args.water is not None:
        set_dict["water"] = args.water
    if args.direction is not None:
        set_dict["direction"] = args.direction
    if args.commissioninfo is not None:
        set_dict["commissioninfo"] = args.commissioninfo
    if args.calibrationtime is not None:
        set_dict["calibrationtime"] = args.calibrationtime
    local_and_cloud_command_msg(set_dict, 1000)

def routine(args: argparse.Namespace) -> None:
    """Set routine."""
    
    routine_dict: dict[str, str] = RoutineCommand().json()

    if args.count:
        # routine_dict["action"] = "count"
        routine_dict = RoutineCommand(action=RoutineCommandActions.COUNT).json()

    if args.list:
        # routine_dict["action"] = "list"
        routine_dict = RoutineCommand(action=RoutineCommandActions.LIST).json()

    if args.put:
        if args.id and args.commands:
            routine_dict = RoutineCommand(action=RoutineCommandActions.PUT, id=args.id, scene="none", commands=args.commands).json()
            # routine_dict["action"] = "put"
            # routine_dict["id"] = args.id
            # routine_dict["scene"] = "none"
            # routine_dict["commands"] = args.commands
        else:
            LOGGER.error("No ID and/or Commands given!")

    if args.delete:
        if args.id:
            routine_dict["action"] = "delete"
            routine_dict["id"] = args.id
        else:
            LOGGER.error("No ID to delete given!")

    if args.start:
        if args.id:
            routine_dict["action"] = "start"
            routine_dict["id"] = args.id
