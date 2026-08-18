from __future__ import annotations

import logging
import time
from collections.abc import Callable

from stackbox.containers.backend import ContainerBackend
from stackbox.containers.health import check
from stackbox.containers.manifest import SessionManifest
from stackbox.containers.specs import required_containers
from stackbox.exceptions import BootstrapError, ContainerError
from stackbox.models.container import ContainerSpec
from stackbox.models.job_config import ResolvedJobConfig

log = logging.getLogger(__name__)

MAX_START_RETRIES = 3
RETRY_DELAY_SECONDS = 5

START_ORDER = [
    ["placement-api"],
    ["glance-api"],
    ["openvswitch-db-server", "openvswitch-vswitchd"],
    ["neutron-server"],
    ["neutron-dhcp-agent", "neutron-openvswitch-agent", "neutron-l3-agent"],
    ["nova-api", "nova-scheduler", "nova-conductor"],
    ["nova-libvirt"],
    ["swift-proxy-server"],
    ["cinder-api", "cinder-scheduler", "cinder-volume", "tgtd"],
    ["sushy-tools", "vbmc"],
    ["dnsmasq", "ironic-pxe"],
    ["ironic-api", "ironic-conductor", "ironic-http"],
    ["nova-compute"],
]


def start_services(
    backend: ContainerBackend,
    job: ResolvedJobConfig,
    specs: list[ContainerSpec],
    manifest: SessionManifest,
    after_ovs: "Callable[[], None] | None" = None,
) -> None:
    needed = required_containers(job)
    specs_by_name = {s.name: s for s in specs}

    for group in START_ORDER:
        group_specs = []
        for svc in group:
            container_name = f"stackbox-{svc}"
            if svc not in needed:
                continue
            spec = specs_by_name.get(container_name)
            if spec is None:
                continue
            group_specs.append(spec)

        if not group_specs:
            continue

        started = []
        for spec in group_specs:
            log.info("Starting %s", spec.name)
            last_err = None
            for attempt in range(1, MAX_START_RETRIES + 1):
                try:
                    backend.run(spec)
                    last_err = None
                    break
                except ContainerError as exc:
                    last_err = exc
                    if attempt < MAX_START_RETRIES:
                        log.warning(
                            "Failed to start %s (attempt %d/%d), retrying in %ds: %s",
                            spec.name, attempt, MAX_START_RETRIES, RETRY_DELAY_SECONDS, exc,
                        )
                        time.sleep(RETRY_DELAY_SECONDS)
            if last_err is not None:
                raise BootstrapError(f"Failed to start {spec.name} after {MAX_START_RETRIES} attempts: {last_err}")
            manifest.record_container(spec.name)
            started.append(spec)

        for spec in started:
            if spec.health_check:
                log.info("Waiting for %s health check...", spec.name)
                check(backend, spec)

        if after_ovs and "openvswitch-db-server" in group:
            after_ovs()

    if "nova-compute" in needed:
        log.info("Discovering compute hosts...")
        exit_code, output = backend.exec(
            "stackbox-nova-api",
            ["nova-manage", "cell_v2", "discover_hosts", "--verbose"],
        )
        if exit_code != 0:
            log.warning("discover_hosts returned %d: %s", exit_code, output)

    log.info("All services started")
