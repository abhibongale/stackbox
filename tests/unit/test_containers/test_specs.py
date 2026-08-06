import json
from pathlib import Path

import pytest

from stackbox.config_gen.ports import PortManager
from stackbox.containers.specs import build_container_specs, required_containers
from stackbox.models.job_config import ResolvedJobConfig
from stackbox.zuul.freeze import build_resolved_config, coerce_localrc, coerce_services

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture
def vmedia_job():
    data = json.loads((FIXTURES_DIR / "frozen-job-vmedia.json").read_text())
    job_vars = data["vars"]
    return build_resolved_config(
        job_name="ironic-tempest-uefi-redfish-vmedia",
        localrc=coerce_localrc(job_vars.get("devstack_localrc", {})),
        services=coerce_services(job_vars.get("devstack_services", {})),
        local_conf=job_vars.get("devstack_local_conf", {}),
        tempest_regex=str(job_vars.get("tempest_test_regex", "")),
    )


class TestRequiredContainers:

    def test_vmedia_has_sushy_tools(self, vmedia_job):
        needed = required_containers(vmedia_job)
        assert "sushy-tools" in needed
        assert "vbmc" not in needed

    def test_vmedia_no_swift(self, vmedia_job):
        needed = required_containers(vmedia_job)
        assert "swift-proxy-server" not in needed

    def test_vmedia_no_dnsmasq(self, vmedia_job):
        needed = required_containers(vmedia_job)
        assert "dnsmasq" not in needed
        assert "ironic-pxe" not in needed

    def test_pxe_has_dnsmasq(self):
        job = ResolvedJobConfig(job_name="pxe-test", boot_interface="pxe")
        needed = required_containers(job)
        assert "dnsmasq" in needed
        assert "ironic-pxe" in needed

    def test_ipmi_has_vbmc(self):
        job = ResolvedJobConfig(job_name="ipmi-test", bmc_driver="ipmi")
        needed = required_containers(job)
        assert "vbmc" in needed
        assert "sushy-tools" not in needed

    def test_cinder_when_enabled(self):
        job = ResolvedJobConfig(
            job_name="bfv-test",
            devstack_services={"c-api": True},
        )
        needed = required_containers(job)
        assert "cinder-api" in needed
        assert "cinder-volume" in needed
        assert "tgtd" in needed

    def test_core_always_present(self):
        job = ResolvedJobConfig(job_name="minimal")
        needed = required_containers(job)
        for svc in ("mariadb", "rabbitmq", "memcached", "keystone", "ironic-api", "nova-api"):
            assert svc in needed


class TestBuildContainerSpecs:

    def test_builds_specs_for_vmedia(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        names = {s.name for s in specs}
        assert "stackbox-mariadb" in names
        assert "stackbox-keystone" in names
        assert "stackbox-ironic-api" in names
        assert "stackbox-sushy-tools" in names

    def test_mariadb_has_init_sql_volume(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        mariadb = next(s for s in specs if s.name == "stackbox-mariadb")
        vol_targets = [v.target for v in mariadb.volumes]
        assert "/opt/stackbox/init.sql" in vol_targets

    def test_keystone_has_health_check(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        ks = next(s for s in specs if s.name == "stackbox-keystone")
        assert ks.health_check is not None
        assert ks.health_check.type == "http"
        assert "/v3" in ks.health_check.target

    def test_ovs_is_privileged(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        ovs = next(s for s in specs if s.name == "stackbox-openvswitch-db-server")
        assert ovs.privileged is True

    def test_port_offset_in_health_checks(self, tmp_path):
        job = ResolvedJobConfig(job_name="test", port_offset=10000)
        pm = PortManager(offset=10000)
        specs = build_container_specs(job, tmp_path, pm, "2025.1-ubuntu-noble")
        mariadb = next(s for s in specs if s.name == "stackbox-mariadb")
        assert mariadb.health_check.target == "13306"

    def test_no_cinder_specs_when_disabled(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        names = {s.name for s in specs}
        assert "stackbox-cinder-api" not in names

    def test_neutron_dhcp_agent_has_agent_config(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        dhcp = next(s for s in specs if s.name == "stackbox-neutron-dhcp-agent")
        vol_targets = [v.target for v in dhcp.volumes]
        assert "/etc/neutron/dhcp_agent.ini" in vol_targets
        assert "/etc/neutron/neutron.conf" in vol_targets

    def test_neutron_l3_agent_has_agent_config(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        l3 = next(s for s in specs if s.name == "stackbox-neutron-l3-agent")
        vol_targets = [v.target for v in l3.volumes]
        assert "/etc/neutron/l3_agent.ini" in vol_targets

    def test_neutron_ovs_agent_has_agent_config(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        ovs = next(s for s in specs if s.name == "stackbox-neutron-openvswitch-agent")
        vol_targets = [v.target for v in ovs.volumes]
        assert "/etc/neutron/plugins/ml2/openvswitch_agent.ini" in vol_targets

    def test_nova_libvirt_has_libvirt_configs(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        libvirt = next(s for s in specs if s.name == "stackbox-nova-libvirt")
        vol_targets = [v.target for v in libvirt.volumes]
        assert "/etc/libvirt/libvirtd.conf" in vol_targets
        assert "/etc/libvirt/qemu.conf" in vol_targets

    def test_nova_compute_has_libvirt_socket(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        compute = next(s for s in specs if s.name == "stackbox-nova-compute")
        vol_targets = [v.target for v in compute.volumes]
        assert "/var/run/libvirt/" in vol_targets

    def test_image_override_replaces_kolla(self, tmp_path):
        job = ResolvedJobConfig(job_name="test")
        pm = PortManager()
        overrides = {"ironic-api": "my-custom-ironic:dev"}
        specs = build_container_specs(
            job, tmp_path, pm, "2025.1-ubuntu-noble", image_overrides=overrides,
        )
        ironic = next(s for s in specs if s.name == "stackbox-ironic-api")
        assert ironic.image == "my-custom-ironic:dev"

    def test_image_override_does_not_affect_others(self, tmp_path):
        job = ResolvedJobConfig(job_name="test")
        pm = PortManager()
        overrides = {"ironic-api": "my-custom-ironic:dev"}
        specs = build_container_specs(
            job, tmp_path, pm, "2025.1-ubuntu-noble", image_overrides=overrides,
        )
        mariadb = next(s for s in specs if s.name == "stackbox-mariadb")
        assert "kolla" in mariadb.image

    def test_image_override_metal3(self, tmp_path):
        job = ResolvedJobConfig(job_name="test", bmc_driver="redfish")
        pm = PortManager()
        overrides = {"sushy-tools": "my-sushy:custom"}
        specs = build_container_specs(
            job, tmp_path, pm, "2025.1-ubuntu-noble", image_overrides=overrides,
        )
        sushy = next(s for s in specs if s.name == "stackbox-sushy-tools")
        assert sushy.image == "my-sushy:custom"

    def test_no_overrides_uses_defaults(self, tmp_path):
        job = ResolvedJobConfig(job_name="test")
        pm = PortManager()
        specs = build_container_specs(job, tmp_path, pm, "2025.1-ubuntu-noble")
        ironic = next(s for s in specs if s.name == "stackbox-ironic-api")
        assert "kolla" in ironic.image

    def test_kolla_config_json_generated(self, tmp_path):
        job = ResolvedJobConfig(job_name="test")
        pm = PortManager()
        build_container_specs(job, tmp_path, pm, "2025.1-ubuntu-noble")
        kolla_dir = tmp_path / "kolla"
        assert kolla_dir.exists()
        mariadb_json = kolla_dir / "mariadb.json"
        assert mariadb_json.exists()
        data = json.loads(mariadb_json.read_text())
        assert data["command"] == "/usr/sbin/mariadbd"
        assert data["config_files"] == []

    def test_all_kolla_containers_have_config_json(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        kolla_config_target = "/var/lib/kolla/config_files/config.json"
        for spec in specs:
            if "sushy-tools" in spec.name or "vbmc" in spec.name:
                continue
            vol_targets = [v.target for v in spec.volumes]
            assert kolla_config_target in vol_targets, (
                f"{spec.name} missing kolla config.json volume"
            )

    def test_mariadb_uses_db_root_password(self, vmedia_job, tmp_path):
        pm = PortManager()
        specs = build_container_specs(vmedia_job, tmp_path, pm, "2025.1-ubuntu-noble")
        mariadb = next(s for s in specs if s.name == "stackbox-mariadb")
        assert "DB_ROOT_PASSWORD" in mariadb.environment
        assert "MARIADB_ROOT_PASSWORD" not in mariadb.environment

    def test_keystone_uwsgi_command_uses_port(self, tmp_path):
        job = ResolvedJobConfig(job_name="test")
        pm = PortManager()
        build_container_specs(job, tmp_path, pm, "2025.1-ubuntu-noble")
        ks_json = tmp_path / "kolla" / "keystone.json"
        data = json.loads(ks_json.read_text())
        assert "uwsgi" in data["command"]
        assert str(pm.get("keystone")) in data["command"]

    def test_placement_uwsgi_command_uses_port(self, tmp_path):
        job = ResolvedJobConfig(job_name="test")
        pm = PortManager()
        build_container_specs(job, tmp_path, pm, "2025.1-ubuntu-noble")
        pl_json = tmp_path / "kolla" / "placement-api.json"
        data = json.loads(pl_json.read_text())
        assert "uwsgi" in data["command"]
        assert str(pm.get("placement")) in data["command"]
