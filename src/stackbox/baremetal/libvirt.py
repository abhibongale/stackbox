from __future__ import annotations

import logging
import os
import random
import subprocess
import tempfile
from pathlib import Path

from stackbox.baremetal.vm_template import render_domain_xml
from stackbox.containers.backend import ContainerBackend
from stackbox.exceptions import BootstrapError
from stackbox.models.baremetal import VirtualBMNode
from stackbox.models.job_config import VMSpecs

log = logging.getLogger(__name__)

SYSTEM_IMAGE_DIR = "/var/lib/libvirt/images"
SESSION_IMAGE_DIR = str(Path.home() / ".local/share/stackbox/libvirt/images")
VMEDIA_DIR = str(Path.home() / ".local/share/stackbox/vmedia")


def default_image_dir() -> str:
    if os.access(SYSTEM_IMAGE_DIR, os.W_OK):
        return SYSTEM_IMAGE_DIR
    return SESSION_IMAGE_DIR


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
    if Path(path).exists():
        log.debug("Disk %s already exists, reusing", path)
        return
    result = subprocess.run(
        ["qemu-img", "create", "-f", "qcow2", path, f"{size_gb}G"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise BootstrapError(
            f"Failed to create disk {path}: {result.stderr.strip()}"
        )


class LibvirtManager:

    def __init__(self, image_dir: str | None = None, backend: ContainerBackend | None = None):
        self.backend = backend
        self.image_dir = Path(image_dir or default_image_dir())
        self.image_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def ensure_running() -> None:
        _virsh(["uri"])
        result = subprocess.run(
            ["virsh", "pool-info", "default"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            pool_dir = str(Path(SESSION_IMAGE_DIR).parent / "default-pool")
            Path(pool_dir).mkdir(parents=True, exist_ok=True)
            _virsh(["pool-define-as", "default", "dir", "--target", pool_dir])
            _virsh(["pool-start", "default"])
            _virsh(["pool-autostart", "default"])
            log.info("Created default libvirt storage pool at %s", pool_dir)
        elif "inactive" in result.stdout.lower():
            _virsh(["pool-start", "default"])
            log.info("Started inactive default libvirt storage pool")

    @staticmethod
    def _get_existing_mac(name: str) -> str | None:
        result = subprocess.run(
            ["virsh", "domiflist", name],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            parts = line.split()
            for part in parts:
                if part.startswith("52:54:00:"):
                    return part
        return None

    def create_nodes(
        self,
        vm_specs: VMSpecs,
        prefix: str = "stackbox-node",
        boot_interface: str = "redfish-virtual-media",
        firmware: str = "uefi",
    ) -> list[VirtualBMNode]:
        self.ensure_running()
        nodes = []
        for i in range(vm_specs.count):
            name = f"{prefix}-{i}"

            existing_mac = self._get_existing_mac(name)
            mac = existing_mac or _random_mac()

            node = VirtualBMNode(
                name=name,
                ram_mb=vm_specs.ram_mb,
                vcpus=vm_specs.cpu,
                disk_gb=vm_specs.disk_gb,
                mac_address=mac,
                boot_interface=boot_interface,
                firmware=firmware,
            )

            disk_path = str(self.image_dir / f"{name}.qcow2")
            _create_disk(disk_path, vm_specs.disk_gb)

            if vm_specs.ephemeral_gb > 0:
                eph_path = str(self.image_dir / f"{name}-ephemeral.qcow2")
                _create_disk(eph_path, vm_specs.ephemeral_gb)

            xml = render_domain_xml(node, ephemeral_gb=vm_specs.ephemeral_gb, image_dir=str(self.image_dir))
            with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
                f.write(xml)
                xml_path = f.name

            try:
                result = subprocess.run(
                    ["virsh", "list", "--all", "--name"],
                    capture_output=True, text=True, timeout=10,
                )
                if name in result.stdout.splitlines():
                    if not existing_mac:
                        _virsh(["destroy", name], check=False)
                        _virsh(["undefine", name, "--nvram"], check=False)
                        _virsh(["undefine", name], check=False)
                        _virsh(["define", xml_path])
                    else:
                        log.info("VM %s already exists with mac=%s, keeping", name, existing_mac)
                else:
                    _virsh(["define", xml_path])
            finally:
                import os
                os.unlink(xml_path)
            node.uuid = _virsh(["domuuid", name]).strip()
            log.info("Defined VM %s uuid=%s (mac=%s, ram=%dMB, disk=%dGB)", name, node.uuid, mac, node.ram_mb, node.disk_gb)
            nodes.append(node)

        return nodes

    def destroy_node(self, name: str) -> None:
        _virsh(["destroy", name], check=False)
        _virsh(["undefine", name, "--nvram", "--remove-all-storage"], check=False)
        _virsh(["undefine", name, "--remove-all-storage"], check=False)
        log.info("Destroyed VM %s", name)

    def list_nodes(self, prefix: str = "stackbox-node") -> list[str]:
        output = _virsh(["list", "--all", "--name"])
        return [line.strip() for line in output.splitlines() if line.strip().startswith(prefix)]
