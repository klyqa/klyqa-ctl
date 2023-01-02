#!/usr/bin/env python3
"""Allow user to run main klyqa ctl script"""

# Execute with:
# $ python -m klyqa_ctl (3.9+)

import asyncio
import klyqa_ctl.klyqa_ctl as klyqa_ctl

if __name__ == "__main__":
    asyncio.run(klyqa_ctl.main())
