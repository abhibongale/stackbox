from __future__ import annotations

import logging

from stackbox.containers.backend import ContainerBackend
from stackbox.containers.health import wait_exec, wait_tcp
from stackbox.exceptions import BootstrapError

log = logging.getLogger(__name__)

CONTAINER = "stackbox-mariadb"


def init_database(backend: ContainerBackend, port: int) -> None:
    log.info("Waiting for MariaDB...")
    wait_tcp("localhost", port, timeout=60)

    wait_exec(
        backend,
        CONTAINER,
        ["mysqladmin", "-u", "root", "-pstackbox", "status"],
        timeout=120,
    )

    exit_code, output = backend.exec(
        CONTAINER,
        ["mysql", "-u", "root", "-pstackbox", "-e",
         "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='keystone'"],
    )
    if exit_code == 0 and "keystone" in output:
        log.info("Databases already initialized, skipping init.sql")
        return

    log.info("Running init.sql...")
    exit_code, output = backend.exec(
        CONTAINER,
        ["bash", "-c", "mysql -u root -pstackbox < /opt/stackbox/init.sql"],
        timeout=600,
    )
    if exit_code != 0:
        raise BootstrapError(f"init.sql failed: {output}")

    log.info("Database initialization complete")
