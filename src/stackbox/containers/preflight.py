from __future__ import annotations

import logging
import subprocess

from stackbox.config_gen.ports import PortManager
from stackbox.constants import BASE_PORTS
from stackbox.exceptions import PortConflictError, PreflightError
from stackbox.models.job_config import ResolvedJobConfig

log = logging.getLogger(__name__)


def _cmd_exists(cmd: str, args: list[str] | None = None) -> bool:
    try:
        subprocess.run(
            [cmd] + (args or ["--version"]),
            capture_output=True, timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_docker() -> None:
    if not _cmd_exists("docker"):
        raise PreflightError("docker is not installed or not in PATH")
    log.info("docker: OK")


def check_libvirt() -> None:
    if not _cmd_exists("virsh", ["version"]):
        raise PreflightError("libvirt (virsh) is not installed or not in PATH")
    log.info("libvirt: OK")


def check_kvm() -> None:
    from pathlib import Path
    kvm = Path("/dev/kvm")
    if not kvm.exists():
        raise PreflightError("/dev/kvm not found — KVM support required")
    if not kvm.stat().st_mode & 0o006:
        log.warning("/dev/kvm exists but may not be accessible to current user")
    log.info("kvm: OK")


def check_ports(port_manager: PortManager, services: set[str] | None = None) -> None:
    try:
        result = subprocess.run(
            ["ss", "-tlnp"], capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        log.warning("Could not run 'ss' to check ports, skipping port conflict check")
        return

    listening = result.stdout
    ports_to_check = services or set(BASE_PORTS.keys())
    conflicts = []

    for svc in ports_to_check:
        try:
            port = port_manager.get(svc)
        except Exception:
            continue
        if f":{port} " in listening or f":{port}\t" in listening:
            conflicts.append((svc, port))

    if conflicts:
        msg = "Port conflicts detected:\n"
        for svc, port in conflicts:
            msg += f"  {svc}: port {port} is already in use\n"
        msg += "Use --port-offset to shift all ports"
        raise PortConflictError(msg)

    log.info("ports: OK (no conflicts)")


def check_qemu_bridge_acl(bridge: str = "brbm-link") -> None:
    from pathlib import Path

    acl_path = Path("/etc/qemu/bridge.conf")
    if not acl_path.exists():
        raise PreflightError(
            f"{acl_path} not found. Create it with:\n"
            f"  sudo mkdir -p /etc/qemu\n"
            f"  echo 'allow {bridge}' | sudo tee /etc/qemu/bridge.conf"
        )
    content = acl_path.read_text()
    if f"allow {bridge}" not in content and "allow all" not in content:
        raise PreflightError(
            f"QEMU bridge ACL ({acl_path}) does not allow bridge '{bridge}'.\n"
            f"Add it with:\n"
            f"  echo 'allow {bridge}' | sudo tee -a /etc/qemu/bridge.conf"
        )
    log.info("qemu bridge acl: OK (bridge %s allowed)", bridge)


def check_all(job: ResolvedJobConfig, port_manager: PortManager) -> None:
    from stackbox.containers.specs import required_containers

    check_docker()
    check_libvirt()
    check_kvm()
    check_qemu_bridge_acl()

    needed = required_containers(job)
    port_keys = set()
    for svc in needed:
        for key in BASE_PORTS:
            if key in svc or svc.replace("-", "_") in key:
                port_keys.add(key)
    port_keys.update({"mariadb", "rabbitmq", "memcached", "keystone"})
    check_ports(port_manager, services=port_keys)
    log.info("All preflight checks passed")
