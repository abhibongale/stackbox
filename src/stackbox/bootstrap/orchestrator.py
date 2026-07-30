from __future__ import annotations

import logging
from pathlib import Path

from stackbox.baremetal.bmc import setup_vbmc, wait_for_bmc
from stackbox.baremetal.enrollment import enroll_nodes
from stackbox.baremetal.libvirt import LibvirtManager
from stackbox.bootstrap.database import init_database
from stackbox.bootstrap.dbsync import run_dbsync
from stackbox.bootstrap.keystone import bootstrap_keystone
from stackbox.bootstrap.network_setup import create_networks, setup_ovs_bridges
from stackbox.bootstrap.resources import setup_resources
from stackbox.bootstrap.service_catalog import register_services
from stackbox.bootstrap.services import start_services
from stackbox.config_gen.ports import PortManager
from stackbox.containers.backend import ContainerBackend
from stackbox.containers.health import check
from stackbox.containers.manifest import SessionManifest
from stackbox.containers.specs import SHARED_VOLUMES, build_container_specs
from stackbox.models.baremetal import BMCType
from stackbox.models.job_config import ResolvedJobConfig
from stackbox.models.network import NetworkConfig

log = logging.getLogger(__name__)


class BootstrapOrchestrator:

    def __init__(
        self,
        backend: ContainerBackend,
        job: ResolvedJobConfig,
        configs_dir: Path,
        manifest: SessionManifest,
        release: str = "master-ubuntu-noble",
    ):
        self.backend = backend
        self.job = job
        self.configs_dir = configs_dir
        self.manifest = manifest
        self.release = release
        self.port_manager = PortManager(offset=job.port_offset)
        self.admin_pass = job.devstack_localrc.get("ADMIN_PASSWORD", "secretadmin")
        self.specs = build_container_specs(job, configs_dir, self.port_manager, release)

    def _specs_by_name(self) -> dict[str, object]:
        return {s.name: s for s in self.specs}

    def run(self) -> None:
        log.info("=== Phase 1: Create shared volumes ===")
        self._create_volumes()

        log.info("=== Phase 2: Start infrastructure ===")
        self._start_infrastructure()

        log.info("=== Phase 3: Bootstrap Keystone ===")
        bootstrap_keystone(self.backend, self.port_manager, self.admin_pass)

        log.info("=== Phase 4: Register service catalog ===")
        register_services(self.backend, self.job, self.port_manager, self.admin_pass)

        log.info("=== Phase 5: Database sync (parallel) ===")
        self._start_dbsync_containers()
        run_dbsync(self.backend, self.job)

        log.info("=== Phase 6: Start services ===")
        start_services(self.backend, self.job, self.specs, self.manifest)

        log.info("=== Phase 7: Network and resource setup ===")
        setup_ovs_bridges(self.manifest)
        create_networks(
            self.backend, NetworkConfig(), self.port_manager, self.admin_pass,
        )
        setup_resources(self.backend, self.job, self.port_manager, self.admin_pass)

        log.info("=== Phase 8: Baremetal VMs and enrollment ===")
        self._setup_baremetal()

        self.manifest.save(Path(self.manifest.configs_dir).parent)
        log.info("Bootstrap complete")

    def _create_volumes(self) -> None:
        for vol_name in SHARED_VOLUMES:
            self.backend.create_volume(vol_name)
            self.manifest.record_volume(vol_name)

    def _start_infrastructure(self) -> None:
        by_name = self._specs_by_name()
        infra = ["stackbox-mariadb", "stackbox-rabbitmq", "stackbox-memcached"]

        for name in infra:
            spec = by_name.get(name)
            if spec is None:
                continue
            log.info("Starting %s", name)
            self.backend.run(spec)
            self.manifest.record_container(name)

        for name in infra:
            spec = by_name.get(name)
            if spec and spec.health_check:
                log.info("Waiting for %s...", name)
                check(self.backend, spec)

        init_database(self.backend, self.port_manager.get("mariadb"))

        spec = by_name.get("stackbox-keystone")
        if spec:
            log.info("Starting stackbox-keystone")
            self.backend.run(spec)
            self.manifest.record_container("stackbox-keystone")

    def _setup_baremetal(self) -> None:
        libvirt = LibvirtManager()
        nodes = libvirt.create_nodes(self.job.vm_specs)
        for node in nodes:
            self.manifest.record_domain(node.name)

        bmc_type = BMCType.REDFISH if self.job.bmc_driver == "redfish" else BMCType.IPMI

        if bmc_type == BMCType.IPMI:
            base_port = self.port_manager.get("vbmc-base")
            setup_vbmc(self.backend, nodes, base_port)

        bmc_port = self.port_manager.get("sushy-tools") if bmc_type == BMCType.REDFISH else 0
        wait_for_bmc(bmc_type, bmc_port)

        enroll_nodes(self.backend, nodes, self.port_manager, self.admin_pass)
        log.info("Baremetal setup complete: %d nodes enrolled", len(nodes))

    def _start_dbsync_containers(self) -> None:
        by_name = self._specs_by_name()
        dbsync_containers = [
            "stackbox-glance-api",
            "stackbox-neutron-server",
            "stackbox-placement-api",
            "stackbox-ironic-api",
            "stackbox-nova-api",
        ]
        if self.job.devstack_services.get("c-api", False):
            dbsync_containers.append("stackbox-cinder-api")

        for name in dbsync_containers:
            spec = by_name.get(name)
            if spec is None:
                continue
            if self.backend.is_running(name):
                continue
            log.info("Starting %s for db_sync", name)
            self.backend.run(spec)
            self.manifest.record_container(name)
