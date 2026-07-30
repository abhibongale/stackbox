from __future__ import annotations

import logging

from stackbox.containers.backend import ContainerBackend
from stackbox.containers.health import wait_tcp
from stackbox.exceptions import BootstrapError

log = logging.getLogger(__name__)

CONTAINER = "stackbox-mariadb"


def init_database(backend: ContainerBackend, port: int) -> None:
    log.info("Waiting for MariaDB...")
    wait_tcp("localhost", port, timeout=60)

    exit_code, output = backend.exec(
        CONTAINER,
        ["mysql", "-u", "root", "-pstackbox", "-e", "SELECT 1"],
    )
    if exit_code != 0:
        raise BootstrapError(f"MariaDB not responding: {output}")

    log.info("MariaDB ready, init.sql applied via entrypoint initdb")
