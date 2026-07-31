from __future__ import annotations

from pathlib import Path

from stackbox.config_gen.ports import PortManager
from stackbox.constants import CONTAINER_PREFIX, KOLLA_IMAGES, KOLLA_REGISTRY, METAL3_REGISTRY
from stackbox.models.container import ContainerSpec, HealthCheck, VolumeMount
from stackbox.models.job_config import ResolvedJobConfig

SHARED_VOLUMES = {
    "stackbox-libvirt-sock": "/var/run/libvirt/",
    "stackbox-libvirt-images": "/var/lib/libvirt/images/",
    "stackbox-ovs-run": "/var/run/openvswitch/",
    "stackbox-ironic-httpboot": "/var/lib/ironic/httpboot/",
}


def _name(service: str) -> str:
    return f"{CONTAINER_PREFIX}-{service}"


def _kolla(service: str, release: str) -> str:
    image_name = KOLLA_IMAGES.get(service, service)
    return f"{KOLLA_REGISTRY}/{image_name}:{release}"


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


def required_containers(job: ResolvedJobConfig) -> set[str]:
    containers = {
        "mariadb", "rabbitmq", "memcached",
        "keystone",
        "glance-api",
        "placement-api",
        "neutron-server", "neutron-dhcp-agent", "neutron-openvswitch-agent", "neutron-l3-agent",
        "nova-api", "nova-scheduler", "nova-conductor", "nova-compute",
        "ironic-api", "ironic-conductor",
        "openvswitch-db-server", "openvswitch-vswitchd",
        "nova-libvirt",
    }

    if job.bmc_driver == "redfish":
        containers.add("sushy-tools")
    elif job.bmc_driver == "ipmi":
        containers.add("vbmc")

    if job.devstack_services.get("s-proxy", False):
        containers.add("swift-proxy-server")

    if job.devstack_services.get("c-api", False):
        containers.update({"cinder-api", "cinder-scheduler", "cinder-volume", "tgtd"})

    if job.boot_interface in ("pxe", "ipxe"):
        containers.update({"ironic-pxe", "dnsmasq"})

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
                _config_vol(configs_dir, "init.sql", "/docker-entrypoint-initdb.d/init.sql"),
            ],
            environment={"MARIADB_ROOT_PASSWORD": "stackbox"},
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
            ],
            health_check=HealthCheck(
                type="tcp", target=str(port_manager.get("rabbitmq")), timeout_seconds=60,
            ),
        ))

    if "memcached" in needed:
        specs.append(ContainerSpec(
            name=_name("memcached"),
            image=_image_for("memcached", release, image_overrides),
            health_check=HealthCheck(
                type="tcp", target=str(port_manager.get("memcached")), timeout_seconds=30,
            ),
        ))

    if "keystone" in needed:
        specs.append(ContainerSpec(
            name=_name("keystone"),
            image=_image_for("keystone", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "keystone.conf", "/etc/keystone/keystone.conf"),
            ],
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
                _shared_vol("stackbox-ironic-httpboot"),
            ],
            health_check=HealthCheck(
                type="http",
                target=f"http://localhost:{port_manager.get('glance')}/healthcheck",
                timeout_seconds=60,
            ),
        ))

    if "placement-api" in needed:
        specs.append(ContainerSpec(
            name=_name("placement-api"),
            image=_image_for("placement-api", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "placement.conf", "/etc/placement/placement.conf"),
            ],
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

    for agent in ("neutron-dhcp-agent", "neutron-openvswitch-agent", "neutron-l3-agent"):
        if agent in needed:
            vols = [
                _config_vol(configs_dir, "neutron.conf", "/etc/neutron/neutron.conf"),
                _config_vol(configs_dir, "ml2_conf.ini", "/etc/neutron/plugins/ml2/ml2_conf.ini"),
                _shared_vol("stackbox-ovs-run"),
            ] + _neutron_agent_configs.get(agent, [])
            specs.append(ContainerSpec(
                name=_name(agent),
                image=_image_for(agent, release, image_overrides),
                privileged=True,
                volumes=vols,
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
            ],
        ))

    if "ironic-api" in needed:
        specs.append(ContainerSpec(
            name=_name("ironic-api"),
            image=_image_for("ironic-api", release, image_overrides),
            volumes=[
                _config_vol(configs_dir, "ironic.conf", "/etc/ironic/ironic.conf"),
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
            ],
        ))

    if "openvswitch-db-server" in needed:
        specs.append(ContainerSpec(
            name=_name("openvswitch-db-server"),
            image=_image_for("openvswitch-db-server", release, image_overrides),
            privileged=True,
            volumes=[_shared_vol("stackbox-ovs-run")],
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
                _vol("/dev/kvm", "/dev/kvm"),
            ],
        ))

    if "sushy-tools" in needed:
        sushy_image = (image_overrides or {}).get(
            "sushy-tools", f"{METAL3_REGISTRY}/sushy-tools:latest",
        )
        specs.append(ContainerSpec(
            name=_name("sushy-tools"),
            image=sushy_image,
            volumes=[
                _config_vol(configs_dir, "emulator.conf", "/etc/sushy/emulator.conf"),
                _shared_vol("stackbox-libvirt-sock"),
                _shared_vol("stackbox-libvirt-images"),
                _shared_vol("stackbox-ironic-httpboot"),
            ],
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
            ],
            health_check=HealthCheck(
                type="http",
                target=f"http://localhost:{port_manager.get('swift')}",
                timeout_seconds=60,
            ),
        ))

    for cinder_svc in ("cinder-api", "cinder-scheduler", "cinder-volume"):
        if cinder_svc in needed:
            vols = [_config_vol(configs_dir, "cinder.conf", "/etc/cinder/cinder.conf")]
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
        ))

    if "ironic-pxe" in needed:
        specs.append(ContainerSpec(
            name=_name("ironic-pxe"),
            image=_image_for("ironic-pxe", release, image_overrides),
            volumes=[_shared_vol("stackbox-ironic-httpboot")],
        ))

    if "dnsmasq" in needed:
        specs.append(ContainerSpec(
            name=_name("dnsmasq"),
            image=_image_for("dnsmasq", release, image_overrides),
            privileged=True,
            volumes=[
                _config_vol(configs_dir, "dnsmasq.conf", "/etc/dnsmasq.conf"),
            ],
        ))

    return specs
