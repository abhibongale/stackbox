from __future__ import annotations

from abc import ABC, abstractmethod

from stackbox.models.container import ContainerSpec


class ContainerBackend(ABC):

    @abstractmethod
    def run(self, spec: ContainerSpec) -> str:
        """Start a container from spec, return container ID."""

    @abstractmethod
    def stop(self, name: str, timeout: int = 10) -> None:
        """Stop a running container."""

    @abstractmethod
    def remove(self, name: str, force: bool = False) -> None:
        """Remove a container."""

    @abstractmethod
    def exec(self, name: str, cmd: list[str], timeout: int = 300) -> tuple[int, str]:
        """Exec a command in a running container. Returns (exit_code, output)."""

    @abstractmethod
    def logs(self, name: str, follow: bool = False, tail: int | None = None) -> str:
        """Get container logs. With follow=True, streams to stdout and returns empty string."""

    @abstractmethod
    def inspect(self, name: str) -> dict:
        """Inspect container state."""

    @abstractmethod
    def is_running(self, name: str) -> bool:
        """Check if a container is running."""

    @abstractmethod
    def list_containers(self, prefix: str = "") -> list[dict]:
        """List containers, optionally filtered by name prefix."""

    @abstractmethod
    def pull_image(self, image: str) -> None:
        """Pull a container image."""

    @abstractmethod
    def build_image(
        self,
        tag: str,
        context: str,
        containerfile: str,
        build_args: dict[str, str] | None = None,
    ) -> None:
        """Build a container image."""

    @abstractmethod
    def create_volume(self, name: str) -> None:
        """Create a named volume."""

    @abstractmethod
    def remove_volume(self, name: str) -> None:
        """Remove a named volume."""
