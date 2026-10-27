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
    description: str | None = None,
) -> None:
    what = description or f"exec '{' '.join(cmd)}'"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            exit_code, _ = backend.exec(container, cmd)
            if exit_code == 0:
                log.info("Exec check passed in %s: %s", container, what)
                return
        except Exception:
            pass
        time.sleep(interval)
    raise BootstrapError(f"Timed out waiting for {what} in {container} after {timeout}s")


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


# ironic-conductor has no port to probe, and its container stays "Up" even when
# every worker dies (cotyledon keeps respawning them, e.g. on a DriverLoadError).
# It is only usable once it has registered itself online in the database, which
# happens after all drivers loaded. Runs inside the conductor with its config.
_CONDUCTOR_ONLINE_SCRIPT = """
import configparser, sys, urllib.parse
import pymysql
conf = configparser.ConfigParser(interpolation=None)
conf.read("/etc/ironic/ironic.conf")
url = urllib.parse.urlparse(conf["database"]["connection"])
db = pymysql.connect(
    host=url.hostname, port=url.port or 3306,
    user=urllib.parse.unquote(url.username),
    password=urllib.parse.unquote(url.password or ""),
    database=url.path.lstrip("/"))
cur = db.cursor()
cur.execute("SELECT COUNT(*) FROM conductors WHERE online = 1")
sys.exit(0 if cur.fetchone()[0] else 1)
"""


def check(backend: ContainerBackend, spec: ContainerSpec) -> None:
    hc = spec.health_check
    if hc is None:
        return

    if hc.type == "tcp":
        port = int(hc.target)
        wait = lambda: wait_tcp(
            "localhost", port, timeout=hc.timeout_seconds, interval=hc.interval_seconds)
    elif hc.type == "http":
        wait = lambda: wait_http(
            hc.target, timeout=hc.timeout_seconds, interval=hc.interval_seconds)
    elif hc.type == "exec":
        wait = lambda: wait_exec(
            backend, spec.name, hc.target.split(),
            timeout=hc.timeout_seconds, interval=hc.interval_seconds,
        )
    elif hc.type == "ironic-conductor":
        wait = lambda: wait_exec(
            backend, spec.name, ["python3", "-c", _CONDUCTOR_ONLINE_SCRIPT],
            timeout=hc.timeout_seconds, interval=hc.interval_seconds,
            description="the conductor to register online (did its drivers load?)",
        )
    else:
        raise BootstrapError(f"Unknown health check type: {hc.type}")

    try:
        wait()
    except BootstrapError as exc:
        # A bare timeout says nothing about why; the service's own last words
        # (e.g. a traceback) usually do.
        try:
            logs = backend.logs(spec.name, tail=40)
        except Exception:
            raise exc from None
        raise BootstrapError(f"{exc}\nRecent logs from {spec.name}:\n{logs}") from exc
