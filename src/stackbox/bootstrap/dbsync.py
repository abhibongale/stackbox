from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from stackbox.containers.backend import ContainerBackend
from stackbox.exceptions import BootstrapError
from stackbox.models.job_config import ResolvedJobConfig

log = logging.getLogger(__name__)

DBSYNC_COMMANDS: dict[str, tuple[str, list[list[str]]]] = {
    "glance": ("stackbox-glance-api", [["glance-manage", "db_sync"]]),
    "neutron": ("stackbox-neutron-server", [["neutron-db-manage", "upgrade", "heads"]]),
    "placement": ("stackbox-placement-api", [["placement-manage", "db", "sync"]]),
    "ironic": ("stackbox-ironic-api", [["ironic-dbsync", "upgrade"]]),
}

NOVA_DBSYNC_COMMANDS: list[list[str]] = [
    ["nova-manage", "api_db", "sync"],
    ["nova-manage", "cell_v2", "map_cell0"],
    ["nova-manage", "cell_v2", "create_cell", "--name", "cell1", "--verbose"],
    ["nova-manage", "db", "sync"],
]


def _run_dbsync(backend: ContainerBackend, container: str, commands: list[list[str]], service: str) -> None:
    for cmd in commands:
        exit_code, output = backend.exec(container, cmd)
        if exit_code != 0:
            if "already exists" in output.lower() or "already mapped" in output.lower():
                log.info("%s: %s (already done, skipping)", service, " ".join(cmd))
                continue
            raise BootstrapError(f"{service} db_sync failed: {' '.join(cmd)}\n{output}")
        log.info("%s db_sync: OK (%s)", service, " ".join(cmd[:2]))


def run_dbsync(backend: ContainerBackend, job: ResolvedJobConfig) -> None:
    tasks = dict(DBSYNC_COMMANDS)

    tasks["nova"] = ("stackbox-nova-api", NOVA_DBSYNC_COMMANDS)

    if job.devstack_services.get("c-api", False):
        tasks["cinder"] = ("stackbox-cinder-api", [["cinder-manage", "db", "sync"]])

    errors = []

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(_run_dbsync, backend, container, commands, service): service
            for service, (container, commands) in tasks.items()
        }
        for future in as_completed(futures):
            service = futures[future]
            try:
                future.result()
            except Exception as exc:
                log.error("%s db_sync failed: %s", service, exc)
                errors.append(str(exc))

    if errors:
        raise BootstrapError(f"DB sync failures:\n" + "\n".join(errors))

    log.info("All database syncs complete")
