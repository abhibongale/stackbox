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
        "OS_USER_DOMAIN_NAME=Default",
        "OS_SYSTEM_SCOPE=all",
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
    last_state = None
    while time.monotonic() < deadline:
        exit_code, output = backend.exec(
            CONTAINER,
            env + ["openstack", "baremetal", "node", "show", node_name, "-f", "value", "-c", "provision_state"],
        )
        if exit_code == 0:
            current = output.strip().lower()
            if current == target_state:
                return
            if current != last_state:
                log.info("Node %s: %s (waiting for %s)", node_name, current, target_state)
                last_state = current
        time.sleep(5)
    raise BootstrapError(
        f"Node {node_name} did not reach {target_state} within {timeout}s"
        f" (last state: {last_state})"
    )


def _wait_for_ironic(backend: ContainerBackend, env: list[str], timeout: int = 120) -> None:
    log.info("Waiting for Ironic API and conductor to be ready...")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        exit_code, output = backend.exec(
            CONTAINER,
            env + ["openstack", "baremetal", "driver", "list", "-f", "value", "-c", "Name"],
        )
        if exit_code == 0 and output.strip():
            log.info("Ironic conductor ready, drivers: %s", output.strip())
            return
        time.sleep(5)
    raise BootstrapError(f"Ironic conductor not ready after {timeout}s")


def _build_driver_info_args(
    node: VirtualBMNode,
    bmc_port: int,
    deploy_images: dict[str, str] | None = None,
) -> list[str]:
    driver = node.bmc.type.value
    args = []
    if driver == "redfish":
        system_id = node.uuid or node.name
        args = [
            "--driver-info", f"redfish_address=http://localhost:{bmc_port}",
            "--driver-info", f"redfish_system_id=/redfish/v1/Systems/{system_id}",
            "--driver-info", f"redfish_username={node.bmc.username}",
            "--driver-info", f"redfish_password={node.bmc.password}",
        ]
    elif driver == "ipmi":
        args = [
            "--driver-info", f"ipmi_address={node.bmc.address}",
            "--driver-info", f"ipmi_port={node.bmc.port}",
            "--driver-info", f"ipmi_username={node.bmc.username}",
            "--driver-info", f"ipmi_password={node.bmc.password}",
        ]
    if deploy_images:
        if "deploy_kernel" in deploy_images:
            args += ["--driver-info", f"deploy_kernel={deploy_images['deploy_kernel']}"]
        if "deploy_ramdisk" in deploy_images:
            args += ["--driver-info", f"deploy_ramdisk={deploy_images['deploy_ramdisk']}"]
    return args


def _update_existing_node(
    backend: ContainerBackend,
    env: list[str],
    node: VirtualBMNode,
    bmc_port: int,
    deploy_images: dict[str, str] | None = None,
) -> None:
    set_cmd = env + [
        "openstack", "baremetal", "node", "set", node.name,
        "--boot-interface", node.boot_interface,
        "--property", f"memory_mb={node.ram_mb}",
        "--property", f"cpus={node.vcpus}",
        "--property", f"local_gb={node.disk_gb}",
        "--property", "cpu_arch=x86_64",
        "--property", f"capabilities=boot_mode:{node.firmware}",
    ]
    for arg in _build_driver_info_args(node, bmc_port, deploy_images):
        set_cmd.append(arg)
    backend.exec(CONTAINER, set_cmd)

    if node.mac_address:
        ec, out = backend.exec(
            CONTAINER,
            env + ["openstack", "baremetal", "port", "list",
                   "--node", node.name, "-f", "value", "-c", "UUID", "-c", "Address"],
        )
        if ec == 0 and out.strip():
            has_correct_port = False
            for line in out.strip().splitlines():
                parts = line.strip().split()
                if len(parts) == 2:
                    port_uuid, mac = parts
                    if mac == node.mac_address:
                        has_correct_port = True
                    else:
                        log.info("Deleting stale port %s (MAC %s)", port_uuid, mac)
                        _exec_or_fail(backend, env + [
                            "openstack", "baremetal", "port", "delete", port_uuid,
                        ], f"delete stale port {port_uuid}")

            if not has_correct_port and node.mac_address:
                node_uuid = _exec_or_fail(
                    backend,
                    env + ["openstack", "baremetal", "node", "show", node.name,
                           "-f", "value", "-c", "uuid"],
                    f"get uuid for {node.name}",
                ).strip()
                log.info("Creating port for %s with MAC %s", node.name, node.mac_address)
                _exec_or_fail(backend, env + [
                    "openstack", "baremetal", "port", "create",
                    "--node", node_uuid, node.mac_address,
                ], f"create port for {node.name}")

    ec, out = backend.exec(
        CONTAINER,
        env + ["openstack", "baremetal", "node", "show", node.name,
               "-f", "value", "-c", "maintenance"],
    )
    if ec == 0 and out.strip().lower() == "true":
        log.info("Clearing maintenance mode on %s", node.name)
        backend.exec(CONTAINER, env + [
            "openstack", "baremetal", "node", "maintenance", "unset", node.name,
        ])


def _wait_for_power_sync(
    backend: ContainerBackend,
    env: list[str],
    node_names: list[str],
    timeout: int = 180,
) -> None:
    deadline = time.monotonic() + timeout
    pending = set(node_names)
    while pending and time.monotonic() < deadline:
        for name in list(pending):
            ec, out = backend.exec(
                CONTAINER,
                env + ["openstack", "baremetal", "node", "show", name,
                       "-f", "value", "-c", "maintenance", "-c", "power_state"],
            )
            if ec != 0:
                continue
            lines = out.strip().splitlines()
            if len(lines) < 2:
                continue
            maintenance = lines[0].strip().lower()
            power_state = lines[1].strip()

            if maintenance == "true":
                log.info("Node %s back in maintenance, clearing again", name)
                backend.exec(CONTAINER, env + [
                    "openstack", "baremetal", "node", "maintenance", "unset", name,
                ])
                continue

            if power_state.lower() not in ("none", ""):
                log.info("Node %s power state synced: %s", name, power_state)
                pending.discard(name)

        if pending:
            time.sleep(10)

    if pending:
        log.warning("Nodes still without power state after %ds: %s", timeout, pending)


def enroll_nodes(
    backend: ContainerBackend,
    nodes: list[VirtualBMNode],
    port_manager: PortManager,
    admin_pass: str,
    deploy_images: dict[str, str] | None = None,
) -> None:
    ks_port = port_manager.get("keystone")
    bmc_port = port_manager.get("sushy-tools")
    env = _os_env(admin_pass, ks_port)

    _wait_for_ironic(backend, env)

    if nodes:
        sample = nodes[0]
        log.info(
            "Enrolling %d node(s): boot_interface=%s firmware=%s driver=%s",
            len(nodes), sample.boot_interface, sample.firmware, sample.bmc.type.value,
        )

    for node in nodes:
        exit_code, output = backend.exec(
            CONTAINER,
            env + ["openstack", "baremetal", "node", "show", node.name,
                   "-f", "value", "-c", "provision_state"],
        )
        if exit_code == 0:
            log.info("Node %s already exists (state=%s), updating", node.name, output.strip())
            _update_existing_node(backend, env, node, bmc_port, deploy_images)
            continue

        driver_info_args = _build_driver_info_args(node, bmc_port, deploy_images)

        create_cmd = env + [
            "openstack", "baremetal", "node", "create",
            "--driver", node.bmc.type.value,
            "--boot-interface", node.boot_interface,
            "--name", node.name,
            "--resource-class", "baremetal",
            "--property", f"memory_mb={node.ram_mb}",
            "--property", f"cpus={node.vcpus}",
            "--property", f"local_gb={node.disk_gb}",
            "--property", "cpu_arch=x86_64",
            "--property", f"capabilities=boot_mode:{node.firmware}",
            "-f", "value", "-c", "uuid",
        ] + driver_info_args

        node_uuid = _exec_or_fail(backend, create_cmd, f"create node {node.name}").strip()

        if node.mac_address:
            _exec_or_fail(backend, env + [
                "openstack", "baremetal", "port", "create",
                "--node", node_uuid,
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

        log.info("Enrolled node %s (driver=%s, mac=%s)", node.name, node.bmc.type.value, node.mac_address)

    _wait_for_power_sync(backend, env, [n.name for n in nodes])
    log.info("All %d nodes enrolled and available", len(nodes))
