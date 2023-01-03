#!/usr/bin/env python3

###################################################################
#
# Interactive Klyqa Control commandline client package
#
# Company: QConnex GmbH / Klyqa
# Author: Frederick Stallmeyer
#
# E-Mail: fraizy@gmx.de
#
###################################################################

__version__: str = "1.0.17"
__author__ : str = "Frederick Stallmeyer <fraizy@gmx.de>"
__license__: str = "MIT"

from klyqa_ctl.klyqa_ctl import *
from klyqa_ctl.general import *
from klyqa_ctl.devices.device import format_uid
