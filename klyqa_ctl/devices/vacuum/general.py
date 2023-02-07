from enum import IntEnum


class VcWorkingStatus(IntEnum):
    SLEEP = 0
    STANDBY = 1
    CLEANING = 2
    CLEANING_AUTO = 3
    CLEANING_RANDOM = 4
    CLEANING_SROOM = 5
    CLEANING_EDGE = 6
    CLEANING_SPOT = 7
    CLEANING_COMP = 8
    DOCKING = 9
    CHARGING = 10
    CHARGING_DC = 11
    CHARGING_COMP = 12
    ERROR = 13


class VcSuctionStrengths(IntEnum):
    NULL = 0
    STRONG = 1
    SMALL = 2
    NORMAL = 3
    MAX = 4


class VcWorkingMode(IntEnum):
    STANDBY = 0
    RANDOM = 1
    SMART = 2
    WALL_FOLLOW = 3
    MOP = 4
    SPIRAL = 5
    PARTIAL_BOW = 6
    SROOM = 7
    CHARGE_GO = 8
