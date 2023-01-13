"""Controller data."""

class ControllerData:
    """Controller data."""

    def __init__(self, interactive_prompts: bool = False, offline: bool = False) -> None:
        self._attr_aes_keys: dict[str, bytes] = {}
        self._attr_interactive_prompts: bool = interactive_prompts
        self._attr_offline: bool = offline
    
    @property
    def aes_keys(self) -> dict[str, bytes]:
        """Return or set the devices dictionary."""
        return self._attr_aes_keys
    
    @property
    def interactive_prompts(self) -> bool:
        """Return or set the devices dictionary."""
        return self._attr_interactive_prompts
    
    @property
    def offline(self) -> bool:
        """Return or set the devices dictionary."""
        return self._attr_offline
    