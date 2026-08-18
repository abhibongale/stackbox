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


def _os_env_system(admin_pass: str, port: int) -> list[str]:
    return [
        "env",
        f"OS_AUTH_URL=http://localhost:{port}/v3",
        f"OS_PASSWORD={admin_pass}",
        "OS_USERNAME=admin",
        "OS_USER_DOMAIN_NAME=Default",
        "OS_SYSTEM_SCOPE=all",
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

    for key, value in props.items():
        _exec_or_warn(backend, env + [
            "openstack", "flavor", "set", "--property", f"{key}={value}", "baremetal",
        ], f"set flavor property {key}")


IPA_BASE_URL = (
    "https://tarballs.opendev.org/openstack/ironic-python-agent/dib/files"
)
IPA_KERNEL = "ipa-centos9-master.kernel"
IPA_RAMDISK = "ipa-centos9-master.initramfs"


def _image_has_data(
    backend: ContainerBackend,
    env: list[str],
    image_id: str,
) -> bool:
    ec, out = backend.exec(
        CONTAINER,
        env + ["openstack", "image", "save", "--file", "/dev/null", image_id],
    )
    return ec == 0


def _delete_image(
    backend: ContainerBackend,
    env: list[str],
    name: str,
) -> None:
    backend.exec(CONTAINER, env + ["openstack", "image", "delete", name])


def _get_or_create_deploy_image(
    backend: ContainerBackend,
    port_manager: PortManager,
    admin_pass: str,
    name: str,
    url: str,
    disk_format: str,
) -> str | None:
    env = _os_env_system(admin_pass, port_manager.get("keystone"))

    ec, out = backend.exec(
        CONTAINER,
        env + ["openstack", "image", "show", "-f", "value", "-c", "id", name],
    )
    if ec == 0 and out.strip():
        image_id = out.strip()
        if _image_has_data(backend, env, image_id):
            log.info("Deploy image %s already exists: %s", name, image_id)
            return image_id
        log.info("Deploy image %s exists but has no data, recreating", name)
        _delete_image(backend, env, name)

    img_path = f"/tmp/{name}"
    ec, out = backend.exec(
        CONTAINER,
        ["python3", "-c",
         f"import urllib.request; urllib.request.urlretrieve('{url}', '{img_path}')"],
        timeout=300,
    )
    if ec != 0:
        log.warning("Failed to download %s: %s", name, out)
        return None

    ec, out = backend.exec(
        CONTAINER,
        env + [
            "openstack", "image", "create",
            "--disk-format", disk_format,
            "--container-format", disk_format,
            "--public",
            "--file", img_path,
            "-f", "value", "-c", "id",
            name,
        ],
    )
    if ec != 0:
        log.warning("Failed to upload %s: %s", name, out)
        return None

    image_id = out.strip()
    log.info("Uploaded deploy image %s: %s", name, image_id)
    return image_id


def upload_deploy_images(
    backend: ContainerBackend,
    port_manager: PortManager,
    admin_pass: str,
) -> dict[str, str]:
    result = {}
    kernel_id = _get_or_create_deploy_image(
        backend, port_manager, admin_pass,
        "deploy-kernel", f"{IPA_BASE_URL}/{IPA_KERNEL}", "aki",
    )
    if kernel_id:
        result["deploy_kernel"] = kernel_id

    ramdisk_id = _get_or_create_deploy_image(
        backend, port_manager, admin_pass,
        "deploy-ramdisk", f"{IPA_BASE_URL}/{IPA_RAMDISK}", "ari",
    )
    if ramdisk_id:
        result["deploy_ramdisk"] = ramdisk_id

    return result


def _get_or_create_test_image(
    backend: ContainerBackend,
    port_manager: PortManager,
    admin_pass: str,
) -> str | None:
    env = _os_env_system(admin_pass, port_manager.get("keystone"))

    ec, out = backend.exec(
        CONTAINER,
        env + ["openstack", "image", "show", "-f", "value", "-c", "id", "cirros-test"],
    )
    if ec == 0 and out.strip():
        image_id = out.strip()
        if _image_has_data(backend, env, image_id):
            log.info("Test image cirros-test already exists: %s", image_id)
            return image_id
        log.info("Test image cirros-test exists but has no data, recreating")
        _delete_image(backend, env, "cirros-test")

    img_url = "http://download.cirros-cloud.net/0.6.2/cirros-0.6.2-x86_64-disk.img"
    img_path = "/tmp/cirros-test.img"

    ec, out = backend.exec(
        CONTAINER,
        ["python3", "-c",
         f"import urllib.request; urllib.request.urlretrieve('{img_url}', '{img_path}')"],
        timeout=120,
    )
    if ec != 0:
        log.warning("Failed to download test image: %s", out)
        return None

    ec, out = backend.exec(
        CONTAINER,
        env + [
            "openstack", "image", "create",
            "--disk-format", "qcow2",
            "--container-format", "bare",
            "--public",
            "--file", img_path,
            "-f", "value", "-c", "id",
            "cirros-test",
        ],
    )
    if ec != 0:
        log.warning("Failed to upload test image: %s", out)
        return None

    image_id = out.strip()
    log.info("Uploaded test image cirros-test: %s", image_id)
    return image_id


def _get_flavor_uuid(
    backend: ContainerBackend,
    port_manager: PortManager,
    admin_pass: str,
) -> str | None:
    env = _os_env(admin_pass, port_manager.get("keystone"))
    ec, out = backend.exec(
        CONTAINER,
        env + ["openstack", "flavor", "show", "-f", "value", "-c", "id", "baremetal"],
    )
    if ec == 0 and out.strip():
        return out.strip()
    log.warning("Failed to get baremetal flavor UUID: %s", out)
    return None


def _get_network_uuid(
    backend: ContainerBackend,
    port_manager: PortManager,
    admin_pass: str,
    network_name: str = "provisioning",
) -> str | None:
    env = _os_env(admin_pass, port_manager.get("keystone"))
    ec, out = backend.exec(
        CONTAINER,
        env + ["openstack", "network", "show", "-f", "value", "-c", "id", network_name],
    )
    if ec == 0 and out.strip():
        return out.strip()
    log.warning("Failed to get network UUID for %s: %s", network_name, out)
    return None


def setup_resources(
    backend: ContainerBackend,
    job: ResolvedJobConfig,
    port_manager: PortManager,
    admin_pass: str,
) -> dict[str, str]:
    create_baremetal_flavor(backend, job, port_manager, admin_pass)
    deploy_images = upload_deploy_images(backend, port_manager, admin_pass)

    resolved = {}
    flavor_id = _get_flavor_uuid(backend, port_manager, admin_pass)
    if flavor_id:
        resolved["{{baremetal_flavor_uuid}}"] = flavor_id

    image_id = _get_or_create_test_image(backend, port_manager, admin_pass)
    if image_id:
        resolved["{{test_image_uuid}}"] = image_id

    network_id = _get_network_uuid(backend, port_manager, admin_pass)
    if network_id:
        resolved["{{provisioning_network_uuid}}"] = network_id

    for key, value in deploy_images.items():
        resolved[key] = value

    log.info("Resource setup complete (resolved %d placeholders)", len(resolved))
    return resolved
