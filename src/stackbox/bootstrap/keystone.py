from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from stackbox.config_gen.ports import PortManager
from stackbox.containers.backend import ContainerBackend
from stackbox.containers.health import wait_http
from stackbox.exceptions import BootstrapError

if TYPE_CHECKING:
    from stackbox.models.container import ContainerSpec

log = logging.getLogger(__name__)

CONTAINER = "stackbox-keystone"


def _exec_or_fail(backend: ContainerBackend, cmd: list[str], desc: str) -> str:
    exit_code, output = backend.exec(CONTAINER, cmd)
    if exit_code != 0:
        raise BootstrapError(f"{desc} failed (exit {exit_code}): {output}")
    log.info("%s: OK", desc)
    return output


def _openstack(backend: ContainerBackend, args: list[str], port: int, admin_pass: str) -> str:
    env_prefix = [
        "env",
        f"OS_AUTH_URL=http://localhost:{port}/v3",
        f"OS_PASSWORD={admin_pass}",
        "OS_USERNAME=admin",
        "OS_PROJECT_NAME=admin",
        "OS_USER_DOMAIN_NAME=Default",
        "OS_PROJECT_DOMAIN_NAME=Default",
        "OS_IDENTITY_API_VERSION=3",
    ]
    return _exec_or_fail(
        backend,
        env_prefix + ["openstack"] + args,
        f"openstack {' '.join(args[:3])}",
    )


def bootstrap_keystone(
    backend: ContainerBackend,
    port_manager: PortManager,
    admin_pass: str,
    spec: ContainerSpec | None = None,
) -> None:
    port = port_manager.get("keystone")

    _exec_or_fail(backend, ["keystone-manage", "db_sync"], "keystone db_sync")

    _exec_or_fail(
        backend,
        ["chown", "-R", "keystone:keystone", "/etc/keystone/fernet-keys/", "/etc/keystone/credential-keys/"],
        "chown keystone key dirs",
    )

    _exec_or_fail(
        backend,
        ["keystone-manage", "fernet_setup", "--keystone-user", "keystone", "--keystone-group", "keystone"],
        "fernet_setup",
    )

    _exec_or_fail(
        backend,
        ["keystone-manage", "credential_setup", "--keystone-user", "keystone", "--keystone-group", "keystone"],
        "credential_setup",
    )

    _exec_or_fail(
        backend,
        [
            "keystone-manage", "bootstrap",
            "--bootstrap-password", admin_pass,
            "--bootstrap-admin-url", f"http://localhost:{port}/v3/",
            "--bootstrap-internal-url", f"http://localhost:{port}/v3/",
            "--bootstrap-public-url", f"http://localhost:{port}/v3/",
            "--bootstrap-region-id", "RegionOne",
        ],
        "keystone bootstrap",
    )

    if spec is not None:
        log.info("Restarting keystone with uwsgi...")
        backend.run(spec)

    log.info("Waiting for Keystone HTTP...")
    wait_http(f"http://localhost:{port}/v3", timeout=120)

    _openstack(backend, ["project", "create", "--or-show", "service"], port, admin_pass)

    service_users = ["ironic", "nova", "glance", "neutron", "placement", "cinder", "swift"]

    for user in service_users:
        _openstack(backend, ["user", "create", "--or-show", "--password", "secretservice", "--project", "service", user], port, admin_pass)
        _openstack(backend, ["role", "add", "--user", user, "--project", "service", "admin"], port, admin_pass)

    log.info("Keystone bootstrap complete")
