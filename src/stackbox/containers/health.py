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
