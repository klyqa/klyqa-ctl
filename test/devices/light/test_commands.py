from __future__ import annotations

import json

from klyqa_ctl.devices.light.commands import RoutineAction, RoutinePutCommand
from klyqa_ctl.general.general import CommandType, TypeJson


def test_routine_put_command_ww() -> None:
    """Test put routine command"""
    cmd: RoutinePutCommand = RoutinePutCommand.create(scene_label="Warm White")
    assert cmd is not None, "Routine command put failed."


def test_routine_put_command_jazz() -> None:
    """Test put routine command"""
    cmd: RoutinePutCommand = RoutinePutCommand.create(scene_label="Jazz Club")
    assert cmd is not None, "Routine command put failed."


def test_routine_put_command() -> None:
    """Test put routine command"""
    cmd: RoutinePutCommand = RoutinePutCommand.create(scene_label="Jazz Club")
    assert cmd is not None, "Routine command put failed."

    j: TypeJson = json.loads(cmd.msg_str())
    assert j["type"] == CommandType.ROUTINE.value
    assert j["action"] == RoutineAction.PUT.value
    assert j["id"] != ""
    assert j["scene"] != ""
    assert j["commands"] != ""
