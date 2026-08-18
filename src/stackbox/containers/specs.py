from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

from stackbox.config_gen.ports import PortManager
from stackbox.baremetal.libvirt import VMEDIA_DIR, default_image_dir
from stackbox.constants import (
    CONTAINER_PREFIX, KOLLA_IMAGES, KOLLA_REGISTRY, KOLLA_RELEASE_OVERRIDES,
    KOLLA_SERVICE_COMMANDS, METAL3_REGISTRY,
)
from stackbox.models.container import ContainerSpec, HealthCheck, VolumeMount
from stackbox.models.job_config import ResolvedJobConfig

SHARED_VOLUMES = {
    "stackbox-mariadb-data": "/var/lib/mysql/",
    "stackbox-keystone-fernet": "/etc/keystone/fernet-keys/",
    "stackbox-keystone-credential": "/etc/keystone/credential-keys/",
    "stackbox-libvirt-sock": "/var/run/libvirt/",
    "stackbox-libvirt-images": "/var/lib/libvirt/images/",
    "stackbox-ironic-httpboot": "/var/lib/ironic/httpboot/",
    "stackbox-glance-images": "/var/lib/glance/images/",
    "stackbox-ovs-run": "/var/run/openvswitch/",
}


def _name(service: str) -> str:
    return f"{CONTAINER_PREFIX}-{service}"


def _kolla(service: str, release: str) -> str:
    image_name = KOLLA_IMAGES.get(service, service)
    tag = KOLLA_RELEASE_OVERRIDES.get(service, release)
    return f"{KOLLA_REGISTRY}/{image_name}:{tag}"


def _image_for(
    service: str, release: str, overrides: dict[str, str] | None,
) -> str:
    if overrides and service in overrides:
        return overrides[service]
    return _kolla(service, release)


def _vol(source: str, target: str, options: str = "z") -> VolumeMount:
    return VolumeMount(source=source, target=target, options=options)


def _config_vol(configs_dir: Path, filename: str, target: str) -> VolumeMount:
    return _vol(str(configs_dir / filename), target, "ro,z")


def _shared_vol(vol_name: str) -> VolumeMount:
    return _vol(vol_name, SHARED_VOLUMES[vol_name])


def _kolla_config_vol(
    configs_dir: Path,
    service: str,
    command: str,
    permissions: list[dict] | None = None,
    config_files: list[dict] | None = None,
) -> VolumeMount:
    kolla_dir = configs_dir / "kolla"
    kolla_dir.mkdir(parents=True, exist_ok=True)
    config_path = kolla_dir / f"{service}.json"
    config: dict = {"command": command, "config_files": config_files or []}
    if permissions:
        config["permissions"] = permissions
    config_path.write_text(json.dumps(config))
    return VolumeMount(
        source=str(config_path),
        target="/var/lib/kolla/config_files/config.json",
        options="ro,z",
    )


def required_containers(job: ResolvedJobConfig) -> set[str]:
    containers = {
        "mariadb", "rabbitmq", "memcached",
        "keystone",
        "glance-api",
        "placement-api",
        "neutron-server", "neutron-dhcp-agent", "neutron-openvswitch-agent", "neutron-l3-agent",
        "nova-api", "nova-scheduler", "nova-conductor", "nova-compute",
        "ironic-api", "ironic-conductor", "ironic-http",
        "openvswitch-db-server", "openvswitch-vswitchd",
        "nova-libvirt",
    }

    if job.bmc_driver == "redfish":
        containers.add("sushy-tools")
    elif job.bmc_driver == "ipmi":
        containers.add("vbmc")

    # swift-proxy-server requires a full swift stack (account, container,
    # object servers + ring files) — not yet implemented; glance uses the
    # file backend instead.

    if job.devstack_services.get("c-api", False):
        containers.update({"cinder-api", "cinder-scheduler", "cinder-volume", "tgtd"})

    if job.boot_interface in ("pxe", "ipxe"):
        containers.add("dnsmasq")
        containers.add("ironic-pxe")

    return containers


def build_container_specs(
    job: ResolvedJobConfig,
    configs_dir: Path,
    port_manager: PortManager,
    release: str,
    image_overrides: dict[str, str] | None = None,
) -> list[ContainerSpec]:
    specs: list[ContainerSpec] = []
    needed = required_containers(job)

    if "mariadb" in needed:
        specs.append(ContainerSpec(
            name=_name("mariadb"),
            image=_image_for("mariadb", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "init.sql", "/opt/stackbox/init.sql"),
                _kolla_config_vol(configs_dir, "mariadb", KOLLA_SERVICE_COMMANDS["mariadb"]),
                _vol("stackbox-mariadb-data", "/var/lib/mysql"),
            ],
            environment={"DB_ROOT_PASSWORD": "stackbox"},
            health_check=HealthCheck(
                type="tcp", target=str(port_manager.get("mariadb")), timeout_seconds=60,
            ),
        ))

    if "rabbitmq" in needed:
        specs.append(ContainerSpec(
            name=_name("rabbitmq"),
            image=_image_for("rabbitmq", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "rabbitmq.conf", "/etc/rabbitmq/rabbitmq.conf"),
                _config_vol(configs_dir, "definitions.json", "/etc/rabbitmq/definitions.json"),
                _kolla_config_vol(configs_dir, "rabbitmq", KOLLA_SERVICE_COMMANDS["rabbitmq"]),
            ],
            health_check=HealthCheck(
                type="tcp", target=str(port_manager.get("rabbitmq")), timeout_seconds=60,
            ),
        ))

    if "memcached" in needed:
        specs.append(ContainerSpec(
            name=_name("memcached"),
            image=_image_for("memcached", release, image_overrides),
            volumes=[
                _kolla_config_vol(configs_dir, "memcached", KOLLA_SERVICE_COMMANDS["memcached"]),
            ],
            health_check=HealthCheck(
                type="tcp", target=str(port_manager.get("memcached")), timeout_seconds=30,
            ),
        ))

    if "keystone" in needed:
        ks_port = port_manager.get("keystone")
        ks_cmd = f"uwsgi --http :{ks_port} --wsgi-file /var/lib/kolla/venv/bin/keystone-wsgi-public --master --processes 2"
        specs.append(ContainerSpec(
            name=_name("keystone"),
            image=_image_for("keystone", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "keystone.conf", "/etc/keystone/keystone.conf"),
                _kolla_config_vol(configs_dir, "keystone", ks_cmd),
                _vol("stackbox-keystone-fernet", "/etc/keystone/fernet-keys/"),
                _vol("stackbox-keystone-credential", "/etc/keystone/credential-keys/"),
            ],
            environment={"KOLLA_SKIP_EXTEND_START": ""},
            health_check=HealthCheck(
                type="http",
                target=f"http://localhost:{port_manager.get('keystone')}/v3",
                timeout_seconds=120,
            ),
        ))

    if "glance-api" in needed:
        specs.append(ContainerSpec(
            name=_name("glance-api"),
            image=_image_for("glance-api", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "glance-api.conf", "/etc/glance/glance-api.conf"),
                _config_vol(configs_dir, "glance-policy.yaml", "/etc/glance/policy.yaml"),
                _shared_vol("stackbox-ironic-httpboot"),
                _shared_vol("stackbox-glance-images"),
                _kolla_config_vol(configs_dir, "glance-api", KOLLA_SERVICE_COMMANDS["glance-api"], permissions=[
                    {"path": "/var/lib/glance", "owner": "glance:glance", "recurse": True},
                ]),
            ],
            health_check=HealthCheck(
                type="http",
                target=f"http://localhost:{port_manager.get('glance')}/healthcheck",
                timeout_seconds=60,
            ),
        ))

    if "placement-api" in needed:
        pl_port = port_manager.get("placement")
        pl_cmd = f"uwsgi --http :{pl_port} --wsgi-file /var/lib/kolla/venv/bin/placement-api --master --processes 2"
        specs.append(ContainerSpec(
            name=_name("placement-api"),
            image=_image_for("placement-api", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "placement.conf", "/etc/placement/placement.conf"),
                _kolla_config_vol(configs_dir, "placement-api", pl_cmd),
            ],
            environment={"KOLLA_SKIP_EXTEND_START": ""},
            health_check=HealthCheck(
                type="http",
                target=f"http://localhost:{port_manager.get('placement')}",
                timeout_seconds=60,
            ),
        ))

    if "neutron-server" in needed:
        specs.append(ContainerSpec(
            name=_name("neutron-server"),
            image=_image_for("neutron-server", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "neutron.conf", "/etc/neutron/neutron.conf"),
                _config_vol(configs_dir, "ml2_conf.ini", "/etc/neutron/plugins/ml2/ml2_conf.ini"),
                _kolla_config_vol(configs_dir, "neutron-server", KOLLA_SERVICE_COMMANDS["neutron-server"]),
            ],
            health_check=HealthCheck(
                type="http",
                target=f"http://localhost:{port_manager.get('neutron')}",
                timeout_seconds=60,
            ),
        ))

    _neutron_agent_configs = {
        "neutron-dhcp-agent": [
            _config_vol(configs_dir, "dhcp_agent.ini", "/etc/neutron/dhcp_agent.ini"),
        ],
        "neutron-l3-agent": [
            _config_vol(configs_dir, "l3_agent.ini", "/etc/neutron/l3_agent.ini"),
        ],
        "neutron-openvswitch-agent": [
            _config_vol(configs_dir, "openvswitch_agent.ini", "/etc/neutron/plugins/ml2/openvswitch_agent.ini"),
        ],
    }

    _sudoers_config_files = [{
        "source": "/var/lib/kolla/config_files/neutron-privsep-sudoers",
        "dest": "/etc/sudoers.d/neutron-privsep",
        "owner": "root",
        "perm": "0440",
    }]

    for agent in ("neutron-dhcp-agent", "neutron-openvswitch-agent", "neutron-l3-agent"):
        if agent in needed:
            vols = [
                _config_vol(configs_dir, "neutron.conf", "/etc/neutron/neutron.conf"),
                _config_vol(configs_dir, "ml2_conf.ini", "/etc/neutron/plugins/ml2/ml2_conf.ini"),
                _config_vol(
                    configs_dir, "neutron-privsep-sudoers",
                    "/var/lib/kolla/config_files/neutron-privsep-sudoers",
                ),
                _shared_vol("stackbox-ovs-run"),
                _kolla_config_vol(
                    configs_dir, agent, KOLLA_SERVICE_COMMANDS[agent],
                    config_files=_sudoers_config_files,
                ),
            ] + _neutron_agent_configs.get(agent, [])
            extra_opts: dict = {}
            if agent == "neutron-dhcp-agent":
                vols.append(_vol("/var/run/netns", "/var/run/netns", "shared"))
                extra_opts["pid_mode"] = "host"
            specs.append(ContainerSpec(
                name=_name(agent),
                image=_image_for(agent, release, image_overrides),
                privileged=True,
                volumes=vols,
                **extra_opts,
            ))

    for svc in ("nova-api", "nova-scheduler", "nova-conductor"):
        if svc in needed:
            hc = None
            if svc == "nova-api":
                hc = HealthCheck(
                    type="http",
                    target=f"http://localhost:{port_manager.get('nova-api')}",
                    timeout_seconds=60,
                )
            specs.append(ContainerSpec(
                name=_name(svc),
                image=_image_for(svc, release, image_overrides),
                volumes=[
                    _config_vol(configs_dir, "nova.conf", "/etc/nova/nova.conf"),
                    _kolla_config_vol(configs_dir, svc, KOLLA_SERVICE_COMMANDS[svc]),
                ],
                health_check=hc,
            ))

    if "nova-compute" in needed:
        specs.append(ContainerSpec(
            name=_name("nova-compute"),
            image=_image_for("nova-compute", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "nova.conf", "/etc/nova/nova.conf"),
                _shared_vol("stackbox-libvirt-sock"),
                _kolla_config_vol(configs_dir, "nova-compute", KOLLA_SERVICE_COMMANDS["nova-compute"]),
            ],
        ))

    if "ironic-api" in needed:
        specs.append(ContainerSpec(
            name=_name("ironic-api"),
            image=_image_for("ironic-api", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "ironic.conf", "/etc/ironic/ironic.conf"),
                _kolla_config_vol(configs_dir, "ironic-api", KOLLA_SERVICE_COMMANDS["ironic-api"]),
            ],
            health_check=HealthCheck(
                type="http",
                target=f"http://localhost:{port_manager.get('ironic-api')}",
                timeout_seconds=60,
            ),
        ))

    if "ironic-conductor" in needed:
        specs.append(ContainerSpec(
            name=_name("ironic-conductor"),
            image=_image_for("ironic-conductor", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "ironic.conf", "/etc/ironic/ironic.conf"),
                _shared_vol("stackbox-ironic-httpboot"),
                _kolla_config_vol(configs_dir, "ironic-conductor", KOLLA_SERVICE_COMMANDS["ironic-conductor"]),
            ],
        ))

        http_port = port_manager.get("ironic-http")
        specs.append(ContainerSpec(
            name=_name("ironic-http"),
            image=_image_for("ironic-conductor", release, image_overrides),
            command=["python3", "-m", "http.server", str(http_port),
                     "--directory", "/var/lib/ironic/httpboot"],
            volumes=[
                _shared_vol("stackbox-ironic-httpboot"),
            ],
            health_check=HealthCheck(
                type="http",
                target=f"http://localhost:{http_port}/",
                timeout_seconds=30,
            ),
        ))

    if "openvswitch-db-server" in needed:
        specs.append(ContainerSpec(
            name=_name("openvswitch-db-server"),
            image=_image_for("openvswitch-db-server", release, image_overrides),
            privileged=True,
            volumes=[
                _shared_vol("stackbox-ovs-run"),
                _kolla_config_vol(configs_dir, "openvswitch-db-server", KOLLA_SERVICE_COMMANDS["openvswitch-db-server"]),
            ],
            health_check=HealthCheck(
                type="tcp", target=str(port_manager.get("ovs")), timeout_seconds=30,
            ),
        ))

    if "openvswitch-vswitchd" in needed:
        specs.append(ContainerSpec(
            name=_name("openvswitch-vswitchd"),
            image=_image_for("openvswitch-vswitchd", release, image_overrides),
            privileged=True,
            volumes=[
                _shared_vol("stackbox-ovs-run"),
                _vol("/lib/modules", "/lib/modules", "ro"),
                _kolla_config_vol(configs_dir, "openvswitch-vswitchd", KOLLA_SERVICE_COMMANDS["openvswitch-vswitchd"]),
            ],
        ))

    if "nova-libvirt" in needed:
        specs.append(ContainerSpec(
            name=_name("nova-libvirt"),
            image=_image_for("nova-libvirt", release, image_overrides),
            privileged=True,
            volumes=[
                _config_vol(configs_dir, "libvirtd.conf", "/etc/libvirt/libvirtd.conf"),
                _config_vol(configs_dir, "qemu.conf", "/etc/libvirt/qemu.conf"),
                _shared_vol("stackbox-libvirt-sock"),
                _shared_vol("stackbox-libvirt-images"),
                _vol("/dev/kvm", "/dev/kvm", ""),
                _kolla_config_vol(configs_dir, "nova-libvirt", KOLLA_SERVICE_COMMANDS["nova-libvirt"]),
            ],
        ))

    if "sushy-tools" in needed:
        sushy_image = (image_overrides or {}).get(
            "sushy-tools", f"{METAL3_REGISTRY}/sushy-tools:latest",
        )
        libvirt_run_dir = f"/run/user/{os.getuid()}/libvirt"
        image_dir = default_image_dir()
        vmedia_dir = VMEDIA_DIR
        Path(vmedia_dir).mkdir(parents=True, exist_ok=True)
        specs.append(ContainerSpec(
            name=_name("sushy-tools"),
            image=sushy_image,
            user=f"{os.getuid()}:{os.getgid()}",
            volumes=[
                _config_vol(configs_dir, "emulator.conf", "/etc/sushy/emulator.conf"),
                _vol(libvirt_run_dir, libvirt_run_dir, ""),
                _vol(image_dir, image_dir, ""),
                _vol(vmedia_dir, vmedia_dir, ""),
                _shared_vol("stackbox-ironic-httpboot"),
            ],
            environment={
                "SUSHY_TOOLS_CONFIG": "/etc/sushy/emulator.conf",
                "TMPDIR": vmedia_dir,
            },
            security_opts=["label=disable"],
            health_check=HealthCheck(
                type="tcp", target=str(port_manager.get("sushy-tools")), timeout_seconds=60,
            ),
        ))

    if "vbmc" in needed:
        vbmc_image = (image_overrides or {}).get(
            "vbmc", f"{METAL3_REGISTRY}/vbmc:latest",
        )
        specs.append(ContainerSpec(
            name=_name("vbmc"),
            image=vbmc_image,
            volumes=[_shared_vol("stackbox-libvirt-sock")],
        ))

    if "swift-proxy-server" in needed:
        specs.append(ContainerSpec(
            name=_name("swift-proxy-server"),
            image=_image_for("swift-proxy-server", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "proxy-server.conf", "/etc/swift/proxy-server.conf"),
                _config_vol(configs_dir, "swift.conf", "/etc/swift/swift.conf"),
                _kolla_config_vol(configs_dir, "swift-proxy-server", KOLLA_SERVICE_COMMANDS["swift-proxy-server"]),
            ],
            health_check=HealthCheck(
                type="http",
                target=f"http://localhost:{port_manager.get('swift')}",
                timeout_seconds=60,
            ),
        ))

    for cinder_svc in ("cinder-api", "cinder-scheduler", "cinder-volume"):
        if cinder_svc in needed:
            vols = [
                _config_vol(configs_dir, "cinder.conf", "/etc/cinder/cinder.conf"),
                _kolla_config_vol(configs_dir, cinder_svc, KOLLA_SERVICE_COMMANDS[cinder_svc]),
            ]
            priv = cinder_svc == "cinder-volume"
            if priv:
                vols.extend([
                    _vol("/dev/", "/dev/"),
                    _vol("/lib/modules", "/lib/modules", "ro"),
                    _vol("/run", "/run", "shared"),
                ])
            hc = None
            if cinder_svc == "cinder-api":
                hc = HealthCheck(
                    type="http",
                    target=f"http://localhost:{port_manager.get('cinder')}",
                    timeout_seconds=60,
                )
            specs.append(ContainerSpec(
                name=_name(cinder_svc),
                image=_image_for(cinder_svc, release, image_overrides),
                privileged=priv,
                volumes=vols,
                health_check=hc,
            ))

    if "tgtd" in needed:
        specs.append(ContainerSpec(
            name=_name("tgtd"),
            image=_image_for("tgtd", release, image_overrides),
            privileged=True,
            volumes=[
                _kolla_config_vol(configs_dir, "tgtd", KOLLA_SERVICE_COMMANDS["tgtd"]),
            ],
        ))

    if "ironic-pxe" in needed:
        specs.append(ContainerSpec(
            name=_name("ironic-pxe"),
            image=_image_for("ironic-pxe", release, image_overrides),
            volumes=[
                _shared_vol("stackbox-ironic-httpboot"),
                _kolla_config_vol(configs_dir, "ironic-pxe", KOLLA_SERVICE_COMMANDS["ironic-pxe"]),
            ],
        ))

    if "dnsmasq" in needed:
        specs.append(ContainerSpec(
            name=_name("dnsmasq"),
            image=_image_for("dnsmasq", release, image_overrides),
            privileged=True,
            volumes=[
                _config_vol(configs_dir, "dnsmasq.conf", "/etc/dnsmasq.conf"),
                _kolla_config_vol(configs_dir, "dnsmasq", KOLLA_SERVICE_COMMANDS["dnsmasq"]),
            ],
        ))

    kolla_config_target = "/var/lib/kolla/config_files/config.json"
    for spec in specs:
        if any(v.target == kolla_config_target for v in spec.volumes):
            spec.environment.setdefault("KOLLA_CONFIG_STRATEGY", "COPY_ALWAYS")

    if image_overrides:
        kolla_dir = configs_dir / "kolla"
        for spec in specs:
            service = spec.name.removeprefix(f"{CONTAINER_PREFIX}-")
            if service in image_overrides and spec.command is None:
                config_path = kolla_dir / f"{service}.json"
                if config_path.exists():
                    cmd = json.loads(config_path.read_text())["command"]
                    spec.command = shlex.split(cmd)

    return specs
