from __future__ import annotations

import logging
import time

from stackbox.config_gen.ports import PortManager
from stackbox.containers.backend import ContainerBackend
from stackbox.exceptions import BootstrapError
from stackbox.models.baremetal import VirtualBMNode

log = logging.getLogger(__name__)

CONTAINER = "stackbox-ironic-api"


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


def _exec_or_fail(backend: ContainerBackend, cmd: list[str], desc: str) -> str:
    exit_code, output = backend.exec(CONTAINER, cmd)
    if exit_code != 0:
        raise BootstrapError(f"{desc} failed: {output}")
    return output


def _wait_for_state(
    backend: ContainerBackend,
    env: list[str],
    node_name: str,
    target_state: str,
    timeout: int = 120,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        exit_code, output = backend.exec(
            CONTAINER,
            env + ["openstack", "baremetal", "node", "show", node_name, "-f", "value", "-c", "provision_state"],
        )
        if exit_code == 0 and output.strip().lower() == target_state:
            return
        time.sleep(5)
    raise BootstrapError(f"Node {node_name} did not reach {target_state} within {timeout}s")


def enroll_nodes(
    backend: ContainerBackend,
    nodes: list[VirtualBMNode],
    port_manager: PortManager,
    admin_pass: str,
) -> None:
    ks_port = port_manager.get("keystone")
    bmc_port = port_manager.get("sushy-tools")
    env = _os_env(admin_pass, ks_port)

    for node in nodes:
        driver = node.bmc.type.value
        redfish_addr = f"http://localhost:{bmc_port}"

        driver_info_args = []
        if driver == "redfish":
            driver_info_args = [
                "--driver-info", f"redfish_address={redfish_addr}",
                "--driver-info", f"redfish_system_id=/redfish/v1/Systems/{node.name}",
                "--driver-info", f"redfish_username={node.bmc.username}",
                "--driver-info", f"redfish_password={node.bmc.password}",
            ]
        elif driver == "ipmi":
            driver_info_args = [
                "--driver-info", f"ipmi_address={node.bmc.address}",
                "--driver-info", f"ipmi_port={node.bmc.port}",
                "--driver-info", f"ipmi_username={node.bmc.username}",
                "--driver-info", f"ipmi_password={node.bmc.password}",
            ]

        create_cmd = env + [
            "openstack", "baremetal", "node", "create",
            "--driver", driver,
            "--name", node.name,
            "--resource-class", "baremetal",
            "--property", f"memory_mb={node.ram_mb}",
            "--property", f"cpus={node.vcpus}",
            "--property", f"local_gb={node.disk_gb}",
        ] + driver_info_args

        _exec_or_fail(backend, create_cmd, f"create node {node.name}")

        if node.mac_address:
            _exec_or_fail(backend, env + [
                "openstack", "baremetal", "port", "create",
                "--node", node.name,
                node.mac_address,
            ], f"create port for {node.name}")

        _exec_or_fail(backend, env + [
            "openstack", "baremetal", "node", "manage", node.name,
        ], f"manage {node.name}")

        _wait_for_state(backend, env, node.name, "manageable")

        _exec_or_fail(backend, env + [
            "openstack", "baremetal", "node", "provide", node.name,
        ], f"provide {node.name}")

        _wait_for_state(backend, env, node.name, "available")

        log.info("Enrolled node %s (driver=%s, mac=%s)", node.name, driver, node.mac_address)

    log.info("All %d nodes enrolled and available", len(nodes))
