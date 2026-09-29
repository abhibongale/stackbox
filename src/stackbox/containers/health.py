from __future__ import annotations

import logging
import socket
import time

import requests

from stackbox.containers.backend import ContainerBackend
from stackbox.exceptions import BootstrapError
from stackbox.models.container import ContainerSpec

log = logging.getLogger(__name__)


def wait_tcp(host: str, port: int, timeout: int = 60, interval: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                log.info("TCP port %s:%d is ready", host, port)
                return
        except OSError:
            time.sleep(interval)
    raise BootstrapError(f"Timed out waiting for TCP {host}:{port} after {timeout}s")


def wait_http(
    url: str,
    timeout: int = 60,
    expected_status: int = 200,
    interval: float = 2.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == expected_status:
                log.info("HTTP %s returned %d", url, expected_status)
                return
        except requests.RequestException:
            pass
        time.sleep(interval)
    raise BootstrapError(f"Timed out waiting for HTTP {url} after {timeout}s")


def wait_exec(
    backend: ContainerBackend,
    container: str,
    cmd: list[str],
    timeout: int = 60,
    interval: float = 2.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            exit_code, _ = backend.exec(container, cmd)
            if exit_code == 0:
                log.info("Exec check passed in %s: %s", container, " ".join(cmd))
                return
        except Exception:
            pass
        time.sleep(interval)
    raise BootstrapError(
        f"Timed out waiting for exec '{' '.join(cmd)}' in {container} after {timeout}s"
    )


# Container states that mean the process is gone for good. "restarting" and
# "created" are transient (e.g. on-failure restart backoff) and tolerated so a
# self-healing container doesn't trip a false hardfail.
_DEAD_STATES = ("exited", "dead", "paused", "removing")


def dead_container_status(backend: ContainerBackend, name: str) -> str | None:
    """Return the container's state ("exited"/"dead"/...) if it has died, else None.

    Returns None when the container is running, restarting, or cannot be
    inspected (missing container) so callers never hardfail on transient or
    absent state.
    """
    try:
        data = backend.inspect(name)
    except Exception:
        return None
    status = (data.get("State") or {}).get("Status")
    return status if status in _DEAD_STATES else None


def assert_containers_alive(backend: ContainerBackend, names: list[str]) -> None:
    """Hardfail immediately if any named container has died.

    Long deploy waits (node cleaning, power sync) poll for a state change that
    can never happen once a service underneath crashes. Rather than block until
    the timeout, surface the dead container and its recent logs right away.
    """
    for name in names:
        status = dead_container_status(backend, name)
        if status is not None:
            logs = backend.logs(name, tail=40)
            raise BootstrapError(
                f"Critical container {name} is {status}; aborting deploy.\n"
                f"Recent logs:\n{logs}"
            )


def check(backend: ContainerBackend, spec: ContainerSpec) -> None:
    hc = spec.health_check
    if hc is None:
        return

    if hc.type == "tcp":
        port = int(hc.target)
        wait_tcp("localhost", port, timeout=hc.timeout_seconds, interval=hc.interval_seconds)
    elif hc.type == "http":
        wait_http(hc.target, timeout=hc.timeout_seconds, interval=hc.interval_seconds)
    elif hc.type == "exec":
        wait_exec(
            backend, spec.name, hc.target.split(),
            timeout=hc.timeout_seconds, interval=hc.interval_seconds,
        )
    else:
        raise BootstrapError(f"Unknown health check type: {hc.type}")
