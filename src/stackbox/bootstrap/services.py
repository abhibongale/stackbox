from __future__ import annotations

import logging

from stackbox.containers.backend import ContainerBackend
from stackbox.containers.health import check
from stackbox.containers.manifest import SessionManifest
from stackbox.containers.specs import required_containers
from stackbox.models.container import ContainerSpec
from stackbox.models.job_config import ResolvedJobConfig

log = logging.getLogger(__name__)

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
    ["ironic-api", "ironic-conductor"],
    ["nova-compute"],
]


def start_services(
    backend: ContainerBackend,
    job: ResolvedJobConfig,
    specs: list[ContainerSpec],
    manifest: SessionManifest,
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

        for spec in group_specs:
            if backend.is_running(spec.name):
                log.info("Skipping %s (already running)", spec.name)
                continue
            try:
                backend.remove(spec.name, force=True)
            except Exception:
                pass
            log.info("Starting %s", spec.name)
            backend.run(spec)
            manifest.record_container(spec.name)

        for spec in group_specs:
            if spec.health_check:
                log.info("Waiting for %s health check...", spec.name)
                check(backend, spec)

    if "nova-compute" in needed:
        log.info("Discovering compute hosts...")
        exit_code, output = backend.exec(
            "stackbox-nova-api",
            ["nova-manage", "cell_v2", "discover_hosts", "--verbose"],
        )
        if exit_code != 0:
            log.warning("discover_hosts returned %d: %s", exit_code, output)

    log.info("All services started")
