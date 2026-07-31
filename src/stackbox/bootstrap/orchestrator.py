from __future__ import annotations

import logging
import time
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
from stackbox.exceptions import BootstrapError
from stackbox.models.baremetal import BMCType
from stackbox.models.container import ContainerSpec
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
        release: str = "2025.1-ubuntu-noble",
        image_overrides: dict[str, str] | None = None,
    ):
        self.backend = backend
        self.job = job
        self.configs_dir = configs_dir
        self.manifest = manifest
        self.release = release
        self.port_manager = PortManager(offset=job.port_offset)
        self.admin_pass = job.devstack_localrc.get("ADMIN_PASSWORD", "secretadmin")
        self.specs = build_container_specs(
            job, configs_dir, self.port_manager, release, image_overrides=image_overrides,
        )

    def _specs_by_name(self) -> dict[str, object]:
        return {s.name: s for s in self.specs}

    def _run_dbsync_phase(self) -> None:
        self._start_dbsync_containers()
        run_dbsync(self.backend, self.job)
        self._stop_dbsync_containers()

    def _run_network_phase(self) -> None:
        setup_ovs_bridges(self.manifest)
        create_networks(
            self.backend, NetworkConfig(), self.port_manager, self.admin_pass,
        )
        setup_resources(self.backend, self.job, self.port_manager, self.admin_pass)

    def run(self) -> None:
        phases = [
            ("Create shared volumes", self._create_volumes),
            ("Start infrastructure", self._start_infrastructure),
            ("Bootstrap Keystone", lambda: bootstrap_keystone(
                self.backend, self.port_manager, self.admin_pass,
                spec=self._specs_by_name().get("stackbox-keystone"),
            )),
            ("Register service catalog", lambda: register_services(self.backend, self.job, self.port_manager, self.admin_pass)),
            ("Database sync", self._run_dbsync_phase),
            ("Start services", lambda: start_services(self.backend, self.job, self.specs, self.manifest)),
            ("Network and resource setup", self._run_network_phase),
            ("Baremetal VMs and enrollment", self._setup_baremetal),
        ]

        total_start = time.monotonic()
        for i, (name, func) in enumerate(phases, 1):
            log.info("=== Phase %d: %s ===", i, name)
            phase_start = time.monotonic()
            func()
            elapsed = time.monotonic() - phase_start
            log.info("Phase %d (%s) completed in %.1fs", i, name, elapsed)

        self.manifest.save(Path(self.manifest.configs_dir).parent)
        total = time.monotonic() - total_start
        log.info("Bootstrap complete in %.1fs", total)

    def _create_volumes(self) -> None:
        for vol_name in SHARED_VOLUMES:
            self.backend.create_volume(vol_name)
            self.manifest.record_volume(vol_name)

    def _bootstrap_mariadb(self, spec: ContainerSpec) -> None:
        self.backend.run(spec)
        time.sleep(3)
        if self.backend.is_running(spec.name):
            log.info("MariaDB data volume already initialized, skipping bootstrap")
            return

        log.info("Bootstrapping MariaDB (initializing system tables)...")
        bootstrap_spec = spec.model_copy(deep=True)
        bootstrap_spec.environment["KOLLA_BOOTSTRAP"] = ""
        self.backend.run(bootstrap_spec)
        timeout = 120
        for _ in range(timeout):
            if not self.backend.is_running(spec.name):
                break
            time.sleep(1)
        else:
            raise BootstrapError(
                f"MariaDB bootstrap did not complete within {timeout}s"
            )
        info = self.backend.inspect(spec.name)
        exit_code = info.get("State", {}).get("ExitCode", -1)
        if exit_code != 0:
            logs = self.backend.logs(spec.name, tail=20)
            raise BootstrapError(
                f"MariaDB bootstrap failed (exit {exit_code}):\n{logs}"
            )
        log.info("MariaDB bootstrap complete")

    def _start_infrastructure(self) -> None:
        by_name = self._specs_by_name()
        infra = ["stackbox-mariadb", "stackbox-rabbitmq", "stackbox-memcached"]

        mariadb_spec = by_name.get("stackbox-mariadb")
        if mariadb_spec:
            self._bootstrap_mariadb(mariadb_spec)
            if not self.backend.is_running(mariadb_spec.name):
                log.info("Starting stackbox-mariadb")
                self.backend.run(mariadb_spec)
            self.manifest.record_container("stackbox-mariadb")

        for name in infra:
            if name == "stackbox-mariadb":
                continue
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
            log.info("Starting stackbox-keystone (init mode)")
            init_spec = spec.model_copy(deep=True)
            init_spec.command = ["sleep", "infinity"]
            init_spec.health_check = None
            self.backend.run(init_spec)
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

    _DBSYNC_CONTAINERS = [
        "stackbox-glance-api",
        "stackbox-neutron-server",
        "stackbox-placement-api",
        "stackbox-ironic-api",
        "stackbox-nova-api",
    ]

    def _start_dbsync_containers(self) -> None:
        by_name = self._specs_by_name()
        containers = list(self._DBSYNC_CONTAINERS)
        if self.job.devstack_services.get("c-api", False):
            containers.append("stackbox-cinder-api")

        for name in containers:
            spec = by_name.get(name)
            if spec is None:
                continue
            log.info("Starting %s (init mode) for db_sync", name)
            init_spec = spec.model_copy(deep=True)
            init_spec.command = ["sleep", "infinity"]
            init_spec.health_check = None
            self.backend.run(init_spec)
            self.manifest.record_container(name)

    def _stop_dbsync_containers(self) -> None:
        containers = list(self._DBSYNC_CONTAINERS)
        if self.job.devstack_services.get("c-api", False):
            containers.append("stackbox-cinder-api")

        for name in containers:
            if self.backend.is_running(name):
                log.info("Stopping %s (init mode done)", name)
                self.backend.stop(name)
                self.backend.remove(name, force=True)
