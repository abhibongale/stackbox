from __future__ import annotations

from stackbox.constants import BASE_PORTS
from stackbox.exceptions import ConfigGenerationError


class PortManager:
    def __init__(self, offset: int = 0):
        self.offset = offset

    def get(self, service: str) -> int:
        base = BASE_PORTS.get(service)
        if base is None:
            raise ConfigGenerationError(f"Unknown service port: {service}")
        return base + self.offset
