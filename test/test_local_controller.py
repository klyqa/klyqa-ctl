"""Test the LocalController class."""

from __future__ import annotations

import asyncio
import json

from klyqa_ctl.general.general import (  # AES_KEY_DEV,
    TRACE,
    get_asyncio_loop,
    set_debug_logger,
)
from klyqa_ctl.local_controller import LocalController


def main() -> None:
    """Main."""

    set_debug_logger(TRACE)

    loop: asyncio.AbstractEventLoop = get_asyncio_loop()

    lc: LocalController = loop.run_until_complete(
        LocalController.create_standalone()
    )

    unit_id: str = "00ac629de9ad2f4409dc"
    aes_key: str = "e901f036a5a119a91ca1f30ef5c207d6"

    reply: str = lc.send_to_device(
        str(unit_id), aes_key, json.dumps({"type": "request"})
    )

    print(reply)


if __name__ == "__main__":
    main()
