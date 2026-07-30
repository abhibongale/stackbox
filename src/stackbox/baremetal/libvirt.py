from __future__ import annotations

import logging
import random
import subprocess
import tempfile
from pathlib import Path

from stackbox.baremetal.vm_template import render_domain_xml
from stackbox.exceptions import BootstrapError
from stackbox.models.baremetal import VirtualBMNode
from stackbox.models.job_config import VMSpecs

log = logging.getLogger(__name__)


def _virsh(args: list[str], check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["virsh"] + args,
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        raise BootstrapError("virsh not found")
    except subprocess.TimeoutExpired:
        raise BootstrapError(f"virsh {' '.join(args)} timed out")

    if check and result.returncode != 0:
        if "already exists" in result.stderr.lower():
            return result.stdout
        raise BootstrapError(f"virsh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _random_mac() -> str:
    return "52:54:00:{:02x}:{:02x}:{:02x}".format(
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
    )


def _create_disk(path: str, size_gb: int) -> None:
    subprocess.run(
        ["qemu-img", "create", "-f", "qcow2", path, f"{size_gb}G"],
        capture_output=True, check=True, timeout=30,
    )


class LibvirtManager:

    def __init__(self, image_dir: str = "/var/lib/libvirt/images"):
        self.image_dir = Path(image_dir)

    def create_nodes(self, vm_specs: VMSpecs, prefix: str = "stackbox-node") -> list[VirtualBMNode]:
        nodes = []
        for i in range(vm_specs.count):
            name = f"{prefix}-{i}"
            mac = _random_mac()
            node = VirtualBMNode(
                name=name,
                ram_mb=vm_specs.ram_mb,
                vcpus=vm_specs.cpu,
                disk_gb=vm_specs.disk_gb,
                mac_address=mac,
            )

            disk_path = str(self.image_dir / f"{name}.qcow2")
            _create_disk(disk_path, vm_specs.disk_gb)

            if vm_specs.ephemeral_gb > 0:
                eph_path = str(self.image_dir / f"{name}-ephemeral.qcow2")
                _create_disk(eph_path, vm_specs.ephemeral_gb)

            xml = render_domain_xml(node, ephemeral_gb=vm_specs.ephemeral_gb)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
                f.write(xml)
                xml_path = f.name

            try:
                _virsh(["define", xml_path])
            finally:
                import os
                os.unlink(xml_path)
            log.info("Defined VM %s (mac=%s, ram=%dMB, disk=%dGB)", name, mac, node.ram_mb, node.disk_gb)
            nodes.append(node)

        return nodes

    def destroy_node(self, name: str) -> None:
        _virsh(["destroy", name], check=False)
        _virsh(["undefine", name, "--remove-all-storage"], check=False)
        log.info("Destroyed VM %s", name)

    def list_nodes(self, prefix: str = "stackbox-node") -> list[str]:
        output = _virsh(["list", "--all", "--name"])
        return [line.strip() for line in output.splitlines() if line.strip().startswith(prefix)]
