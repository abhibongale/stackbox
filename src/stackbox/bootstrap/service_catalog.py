from __future__ import annotations

import logging

from stackbox.config_gen.ports import PortManager
from stackbox.containers.backend import ContainerBackend
from stackbox.exceptions import BootstrapError
from stackbox.models.job_config import ResolvedJobConfig

log = logging.getLogger(__name__)

CONTAINER = "stackbox-keystone"

CORE_SERVICES = [
    ("nova", "compute", "nova-api"),
    ("glance", "image", "glance"),
    ("neutron", "network", "neutron"),
    ("placement", "placement", "placement"),
    ("ironic", "baremetal", "ironic-api"),
]

CONDITIONAL_SERVICES = {
    "s-proxy": ("swift", "object-store", "swift"),
    "c-api": ("cinder", "volumev3", "cinder"),
}


def _exec_or_fail(backend: ContainerBackend, cmd: list[str], desc: str) -> None:
    exit_code, output = backend.exec(CONTAINER, cmd)
    if exit_code != 0:
        raise BootstrapError(f"{desc} failed: {output}")



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


def register_services(
    backend: ContainerBackend,
    job: ResolvedJobConfig,
    port_manager: PortManager,
    admin_pass: str,
) -> None:
    ks_port = port_manager.get("keystone")
    env = _os_env(admin_pass, ks_port)

    services = list(CORE_SERVICES)
    for ds_key, svc_info in CONDITIONAL_SERVICES.items():
        if job.devstack_services.get(ds_key, False):
            services.append(svc_info)

    for name, svc_type, port_key in services:
        port = port_manager.get(port_key)
        url = f"http://localhost:{port}"

        if svc_type == "identity":
            url = f"http://localhost:{port}/v3/"
        elif svc_type == "compute":
            url = f"http://localhost:{port}/v2.1"

        _exec_or_fail(
            backend,
            env + ["openstack", "service", "create", "--name", name, svc_type],
            f"create service {name}",
        )

        for interface in ("public", "internal", "admin"):
            _exec_or_fail(
                backend,
                env + [
                    "openstack", "endpoint", "create", "--region", "RegionOne",
                    svc_type, interface, url,
                ],
                f"create {interface} endpoint for {name}",
            )

    log.info("Service catalog registration complete (%d services)", len(services))
