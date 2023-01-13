"""Controller data."""

class ControllerData:
    """Controller data."""

    def __init__(self, interactive_prompts: bool, offline: bool, ) -> None:
        self.aes_keys: dict[str, bytes] = {}
        self.interactive_prompts: bool = interactive_prompts
        self.offline: bool = offline
        
    