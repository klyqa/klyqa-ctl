from enum import IntEnum


class VcWorkingStatus(IntEnum):
    SLEEP = 1
    STANDBY = 2
    CLEANING = 3
    CLEANING_AUTO = 4
    CLEANING_RANDOM = 5
    CLEANING_SROOM = 6
    CLEANING_EDGE = 7
    CLEANING_SPOT = 8
    CLEANING_COMP = 9
    DOCKING = 10
    CHARGING = 11
    CHARGING_DC = 12
    CHARGING_COMP = 13
    ERROR = 14


class VcSuctionStrengths(IntEnum):
    NULL = 1
    STRONG = 2
    SMALL = 3
    NORMAL = 4
    MAX = 5


class VcWorkingMode(IntEnum):
    STANDBY = 1
    RANDOM = 2
    SMART = 3
    WALL_FOLLOW = 4
    MOP = 5
    SPIRAL = 6
    PARTIAL_BOW = 7
    SROOM = 8
    CHARGE_GO = 9
