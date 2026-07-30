from __future__ import annotations

import logging

from stackbox.containers.backend import ContainerBackend
from stackbox.containers.health import wait_tcp
from stackbox.exceptions import BootstrapError
from stackbox.models.baremetal import BMCType, VirtualBMNode

log = logging.getLogger(__name__)


def wait_for_bmc(bmc_type: BMCType, port: int) -> None:
    if bmc_type == BMCType.REDFISH:
        log.info("Waiting for sushy-tools on port %d...", port)
        wait_tcp("localhost", port, timeout=60)
    elif bmc_type == BMCType.IPMI:
        log.info("IPMI BMC (vbmc) uses UDP, skipping TCP health check")


def setup_vbmc(
    backend: ContainerBackend,
    nodes: list[VirtualBMNode],
    base_port: int,
) -> None:
    container = "stackbox-vbmc"

    for i, node in enumerate(nodes):
        port = base_port + i
        exit_code, output = backend.exec(container, [
            "vbmc", "add", node.name,
            "--port", str(port),
            "--username", node.bmc.username,
            "--password", node.bmc.password,
        ])
        if exit_code != 0:
            raise BootstrapError(f"vbmc add {node.name} failed: {output}")

        exit_code, output = backend.exec(container, ["vbmc", "start", node.name])
        if exit_code != 0:
            raise BootstrapError(f"vbmc start {node.name} failed: {output}")

        node.bmc.port = port
        log.info("vBMC started for %s on UDP port %d", node.name, port)
