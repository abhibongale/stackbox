from __future__ import annotations

import logging

from stackbox.config_gen.ports import PortManager
from stackbox.containers.backend import ContainerBackend
from stackbox.exceptions import BootstrapError
from stackbox.models.job_config import ResolvedJobConfig

log = logging.getLogger(__name__)

CONTAINER = "stackbox-keystone"


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


def _exec_or_warn(backend: ContainerBackend, cmd: list[str], desc: str) -> bool:
    exit_code, output = backend.exec(CONTAINER, cmd)
    if exit_code != 0:
        if "already exists" in output.lower() or "conflict" in output.lower():
            log.info("%s: already exists, skipping", desc)
            return True
        log.warning("%s failed: %s", desc, output)
        return False
    log.info("%s: OK", desc)
    return True


def create_baremetal_flavor(
    backend: ContainerBackend,
    job: ResolvedJobConfig,
    port_manager: PortManager,
    admin_pass: str,
) -> None:
    env = _os_env(admin_pass, port_manager.get("keystone"))
    vm = job.vm_specs

    _exec_or_warn(backend, env + [
        "openstack", "flavor", "create",
        "--ram", str(vm.ram_mb),
        "--vcpus", str(vm.cpu),
        "--disk", str(vm.disk_gb),
        "--public",
        "baremetal",
    ], "create baremetal flavor")

    props = {
        "resources:CUSTOM_BAREMETAL": "1",
        "resources:VCPU": "0",
        "resources:MEMORY_MB": "0",
        "resources:DISK_GB": "0",
    }
    if vm.ephemeral_gb > 0:
        props["resources:CUSTOM_BAREMETAL_EPHEMERAL"] = "1"

    for key, value in props.items():
        _exec_or_warn(backend, env + [
            "openstack", "flavor", "set", "--property", f"{key}={value}", "baremetal",
        ], f"set flavor property {key}")


def upload_deploy_images(
    backend: ContainerBackend,
    port_manager: PortManager,
    admin_pass: str,
) -> None:
    env = _os_env(admin_pass, port_manager.get("keystone"))

    exit_code, _ = backend.exec(
        "stackbox-ironic-conductor",
        ["ls", "/var/lib/ironic/httpboot/deploy-kernel"],
    )
    if exit_code != 0:
        log.warning("Deploy images not found in ironic httpboot volume, skipping upload")
        return

    ironic_ctr = "stackbox-ironic-conductor"
    ironic_env = _os_env(admin_pass, port_manager.get("keystone"))

    for name, disk_format in [("deploy-kernel", "aki"), ("deploy-ramdisk", "ari")]:
        ec, out = backend.exec(ironic_ctr, ironic_env + [
            "openstack", "image", "create",
            "--disk-format", disk_format,
            "--container-format", disk_format,
            "--public",
            "--file", f"/var/lib/ironic/httpboot/{name}",
            name,
        ])
        if ec != 0:
            if "already exists" in out.lower():
                log.info("upload %s: already exists, skipping", name)
            else:
                log.warning("upload %s failed: %s", name, out)
        else:
            log.info("upload %s: OK", name)

    log.info("Deploy images uploaded")


def setup_resources(
    backend: ContainerBackend,
    job: ResolvedJobConfig,
    port_manager: PortManager,
    admin_pass: str,
) -> None:
    create_baremetal_flavor(backend, job, port_manager, admin_pass)
    upload_deploy_images(backend, port_manager, admin_pass)
    log.info("Resource setup complete")
