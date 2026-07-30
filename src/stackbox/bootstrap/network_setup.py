from __future__ import annotations

import logging
import subprocess

from stackbox.config_gen.ports import PortManager
from stackbox.containers.backend import ContainerBackend
from stackbox.containers.manifest import SessionManifest
from stackbox.exceptions import BootstrapError
from stackbox.models.network import NetworkConfig

log = logging.getLogger(__name__)

CONTAINER = "stackbox-neutron-server"


def _ovs_vsctl(args: list[str]) -> None:
    try:
        subprocess.run(
            ["sudo", "ovs-vsctl"] + args,
            capture_output=True, text=True, check=True, timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        if "already exists" in (exc.stderr or ""):
            return
        raise BootstrapError(f"ovs-vsctl {' '.join(args)} failed: {exc.stderr}") from exc


def _os_env(admin_pass: str, port: int) -> list[str]:
    return [
        "env",
        f"OS_AUTH_URL=http://localhost:{port}/v3",
        f"OS_PASSWORD={admin_pass}",
        "OS_USERNAME=admin",
        "OS_PROJECT_NAME=admin",
        "OS_USER_DOMAIN_NAME=Default",
        "OS_PROJECT_DOMAIN_NAME=Default",
        "OS_IDENTITY_API_VERSION=3",
    ]


def setup_ovs_bridges(manifest: SessionManifest) -> None:
    for bridge in ("brbm", "br-int", "br-ex"):
        log.info("Creating OVS bridge: %s", bridge)
        _ovs_vsctl(["--may-exist", "add-br", bridge])
        manifest.record_bridge(bridge)

    _ovs_vsctl(["--may-exist", "add-port", "br-int", "int-brbm", "--",
                "set", "interface", "int-brbm", "type=patch", "options:peer=brbm-int"])
    _ovs_vsctl(["--may-exist", "add-port", "brbm", "brbm-int", "--",
                "set", "interface", "brbm-int", "type=patch", "options:peer=int-brbm"])

    log.info("OVS bridges configured")


def create_networks(
    backend: ContainerBackend,
    network_config: NetworkConfig,
    port_manager: PortManager,
    admin_pass: str,
) -> None:
    ks_port = port_manager.get("keystone")
    env = _os_env(admin_pass, ks_port)

    subnet = network_config.provisioning_subnet

    exit_code, output = backend.exec(CONTAINER, env + [
        "openstack", "network", "create",
        "--provider-network-type", "flat",
        "--provider-physical-network", "physnet1",
        "--share",
        network_config.provisioning_network,
    ])
    if exit_code != 0 and "already exists" not in output.lower():
        raise BootstrapError(f"Failed to create provisioning network: {output}")

    subnet_cmd = env + [
        "openstack", "subnet", "create",
        "--network", network_config.provisioning_network,
        "--subnet-range", subnet.cidr,
        subnet.name,
    ]
    if subnet.gateway:
        subnet_cmd.extend(["--gateway", subnet.gateway])
    if subnet.allocation_pool_start and subnet.allocation_pool_end:
        subnet_cmd.extend([
            "--allocation-pool",
            f"start={subnet.allocation_pool_start},end={subnet.allocation_pool_end}",
        ])
    if not subnet.enable_dhcp:
        subnet_cmd.append("--no-dhcp")

    exit_code, output = backend.exec(CONTAINER, subnet_cmd)
    if exit_code != 0 and "already exists" not in output.lower():
        raise BootstrapError(f"Failed to create provisioning subnet: {output}")

    log.info("Provisioning network created")
