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


def check_podman() -> None:
    if not _cmd_exists("podman"):
        raise PreflightError("podman is not installed or not in PATH")
    log.info("podman: OK")


def check_libvirt() -> None:
    if not _cmd_exists("virsh", ["version"]):
        raise PreflightError("libvirt (virsh) is not installed or not in PATH")
    log.info("libvirt: OK")


def check_ovs() -> None:
    if not _cmd_exists("ovs-vsctl", ["--version"]):
        raise PreflightError("Open vSwitch (ovs-vsctl) is not installed or not in PATH")
    log.info("ovs: OK")


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


def check_all(job: ResolvedJobConfig, port_manager: PortManager) -> None:
    from stackbox.containers.specs import required_containers

    check_podman()
    check_libvirt()
    check_ovs()
    check_kvm()

    needed = required_containers(job)
    port_keys = set()
    for svc in needed:
        for key in BASE_PORTS:
            if key in svc or svc.replace("-", "_") in key:
                port_keys.add(key)
    port_keys.update({"mariadb", "rabbitmq", "memcached", "keystone"})
    check_ports(port_manager, services=port_keys)
    log.info("All preflight checks passed")
