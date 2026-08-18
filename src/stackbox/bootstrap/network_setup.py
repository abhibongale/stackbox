from __future__ import annotations

import ipaddress
import logging

from stackbox.config_gen.ports import PortManager
from stackbox.containers.backend import ContainerBackend
from stackbox.containers.manifest import SessionManifest
from stackbox.exceptions import BootstrapError
from stackbox.models.network import NetworkConfig

log = logging.getLogger(__name__)

CONTAINER = "stackbox-neutron-server"
OVS_CONTAINER = "stackbox-openvswitch-db-server"


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


def _ovs_vsctl(backend: ContainerBackend, args: list[str]) -> None:
    exit_code, output = backend.exec(
        OVS_CONTAINER, ["ovs-vsctl"] + args, timeout=30,
    )
    if exit_code != 0:
        if "already exists" in output.lower():
            return
        raise BootstrapError(
            f"ovs-vsctl {' '.join(args)} failed: {output}"
        )


def _ovs_exec(backend: ContainerBackend, cmd: list[str], check: bool = True) -> str:
    exit_code, output = backend.exec(OVS_CONTAINER, cmd, timeout=30)
    if check and exit_code != 0:
        raise BootstrapError(f"{' '.join(cmd)} failed: {output}")
    return output


def setup_ovs_bridges(backend: ContainerBackend, manifest: SessionManifest) -> None:
    for bridge in ("brbm", "br-int", "br-ex"):
        log.info("Creating OVS bridge: %s", bridge)
        _ovs_vsctl(backend, ["--may-exist", "add-br", bridge])
        manifest.record_bridge(bridge)

    setup_vm_bridge(backend)
    _assign_provisioning_ip(backend)
    log.info("OVS bridges configured")


def _assign_provisioning_ip(
    backend: ContainerBackend,
    bridge: str = "brbm-link",
    ip: str = "192.168.24.1/24",
) -> None:
    _ovs_exec(backend, ["ip", "addr", "add", ip, "dev", bridge], check=False)
    _ovs_exec(backend, ["ip", "link", "set", bridge, "up"])
    _pin_local_route(backend, ip)
    log.info("Assigned %s to bridge %s", ip, bridge)


def _pin_local_route(backend: ContainerBackend, cidr: str) -> None:
    """Ensure provisioning subnet is routed locally, not via VPN or other policy routes."""
    network = str(ipaddress.ip_interface(cidr).network)
    _ovs_exec(
        backend,
        ["ip", "rule", "add", "to", network, "lookup", "main", "priority", "100"],
        check=False,
    )


def _ensure_iptables(backend: ContainerBackend) -> bool:
    ec, _ = backend.exec(OVS_CONTAINER, ["which", "iptables"], timeout=10)
    if ec == 0:
        return True

    log.info("Installing iptables in %s", OVS_CONTAINER)
    ec, out = backend.exec(
        OVS_CONTAINER,
        ["bash", "-c", "apt-get update -qq && apt-get install -y -qq iptables"],
        timeout=60,
    )
    if ec != 0:
        log.warning("Failed to install iptables in %s: %s", OVS_CONTAINER, out.strip())
        return False
    return True


def _open_bridge_firewall(backend: ContainerBackend, bridge: str) -> None:
    if not _ensure_iptables(backend):
        log.warning(
            "iptables not available in %s. VM-to-host traffic may be blocked. "
            "Fix with: sudo iptables -I INPUT -i %s -j ACCEPT",
            OVS_CONTAINER, bridge,
        )
        return

    for chain, args in [
        ("INPUT", ["-i", bridge, "-j", "ACCEPT"]),
        ("FORWARD", ["-i", bridge, "-j", "ACCEPT"]),
        ("FORWARD", ["-o", bridge, "-j", "ACCEPT"]),
    ]:
        ec, _ = backend.exec(
            OVS_CONTAINER,
            ["iptables", "-C", chain] + args,
            timeout=10,
        )
        if ec == 0:
            continue
        backend.exec(
            OVS_CONTAINER,
            ["iptables", "-I", chain] + args,
            timeout=10,
        )

    log.info("Opened firewall for bridge %s via iptables", bridge)


def setup_vm_bridge(backend: ContainerBackend, ovs_bridge: str = "brbm", link_bridge: str = "brbm-link") -> None:
    _ovs_exec(backend, ["ip", "link", "add", link_bridge, "type", "bridge"], check=False)
    _ovs_exec(backend, ["ip", "link", "set", "dev", link_bridge, "type", "bridge", "forward_delay", "0"], check=False)
    _ovs_exec(backend, ["ip", "link", "set", link_bridge, "up"])

    _ovs_exec(backend, ["ip", "link", "add", "veth-bm", "type", "veth", "peer", "name", "veth-bm-ovs"], check=False)
    _ovs_exec(backend, ["ip", "link", "set", "veth-bm", "master", link_bridge])
    _ovs_exec(backend, ["ip", "link", "set", "veth-bm", "up"])
    _ovs_exec(backend, ["ip", "link", "set", "veth-bm-ovs", "up"])

    _ovs_vsctl(backend, ["--may-exist", "add-port", ovs_bridge, "veth-bm-ovs"])
    _open_bridge_firewall(backend, link_bridge)
    log.info("Created Linux bridge %s linked to OVS bridge %s", link_bridge, ovs_bridge)


def create_networks(
    backend: ContainerBackend,
    network_config: NetworkConfig,
    port_manager: PortManager,
    admin_pass: str,
) -> None:
    ks_port = port_manager.get("keystone")
    env = _os_env(admin_pass, ks_port)

    subnet = network_config.provisioning_subnet

    exit_code, _ = backend.exec(CONTAINER, env + [
        "openstack", "network", "show", network_config.provisioning_network,
    ])
    if exit_code == 0:
        log.info("Provisioning network already exists, skipping")
        return

    exit_code, output = backend.exec(CONTAINER, env + [
        "openstack", "network", "create",
        "--provider-network-type", "flat",
        "--provider-physical-network", "physnet1",
        "--share",
        network_config.provisioning_network,
    ])
    if exit_code != 0:
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
    if exit_code != 0:
        raise BootstrapError(f"Failed to create provisioning subnet: {output}")

    log.info("Provisioning network created")
