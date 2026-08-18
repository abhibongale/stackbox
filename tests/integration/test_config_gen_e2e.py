"""End-to-end test: frozen-job fixture → ConfigPipeline → real config files on disk."""

import json
from configparser import ConfigParser
from pathlib import Path

import pytest

from stackbox.config_gen import ConfigPipeline
from stackbox.zuul.freeze import build_resolved_config, coerce_localrc, coerce_services

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def vmedia_job(tmp_path):
    """Build a ResolvedJobConfig from the real frozen-job fixture and generate all configs."""
    data = json.loads((FIXTURES_DIR / "frozen-job-vmedia.json").read_text())
    job_vars = data["vars"]

    job = build_resolved_config(
        job_name="ironic-tempest-uefi-redfish-vmedia",
        localrc=coerce_localrc(job_vars.get("devstack_localrc", {})),
        services=coerce_services(job_vars.get("devstack_services", {})),
        local_conf=job_vars.get("devstack_local_conf", {}),
        tempest_regex=str(job_vars.get("tempest_test_regex", "")),
    )

    pipeline = ConfigPipeline()
    generated = pipeline.generate_all(job, tmp_path)
    return job, tmp_path, generated


class TestEndToEnd:

    def test_expected_file_count(self, vmedia_job):
        job, out, generated = vmedia_job
        assert len(generated) >= 12

    def test_all_files_non_empty(self, vmedia_job):
        _, out, generated = vmedia_job
        for f in generated:
            path = out / f
            assert path.exists(), f"{f} not created"
            assert path.stat().st_size > 0, f"{f} is empty"

    def test_expected_core_files(self, vmedia_job):
        _, _, generated = vmedia_job
        expected = {
            "ironic.conf", "nova.conf", "keystone.conf", "glance-api.conf",
            "neutron.conf", "ml2_conf.ini", "placement.conf", "init.sql",
            "rabbitmq.conf", "definitions.json", "emulator.conf", "tempest.conf",
        }
        assert expected.issubset(set(generated))

    def test_swift_included_for_vmedia(self, vmedia_job):
        _, _, generated = vmedia_job
        assert "proxy-server.conf" in generated

    def test_dnsmasq_included_for_vmedia(self, vmedia_job):
        _, _, generated = vmedia_job
        assert "dnsmasq.conf" in generated

    def test_cinder_excluded_for_vmedia(self, vmedia_job):
        _, _, generated = vmedia_job
        assert "cinder.conf" not in generated

    # -- ironic.conf --

    def test_ironic_hardware_types(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "ironic.conf")
        hw_types = config["DEFAULT"]["enabled_hardware_types"]
        assert "redfish" in hw_types

    def test_ironic_boot_interfaces(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "ironic.conf")
        boot = config["DEFAULT"]["enabled_boot_interfaces"]
        assert "redfish-virtual-media" in boot

    def test_ironic_database_uses_correct_port(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "ironic.conf")
        assert ":3306/" in config["database"]["connection"]

    # -- nova.conf --

    def test_nova_compute_driver(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "nova.conf")
        assert config["DEFAULT"]["compute_driver"] == "ironic.IronicDriver"

    def test_nova_ironic_auth(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "nova.conf")
        assert config["ironic"]["username"] == "ironic"
        assert config["ironic"]["auth_type"] == "password"

    # -- placement.conf --

    def test_placement_uses_placement_database(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "placement.conf")
        assert "placement_database" in config.sections()
        assert "database" not in config.sections()

    # -- neutron --

    def test_neutron_ml2_core_plugin(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "neutron.conf")
        assert config["DEFAULT"]["core_plugin"] == "ml2"

    def test_ml2_conf_has_securitygroup(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.optionxform = str
        config.read(out / "ml2_conf.ini")
        assert config["securitygroup"]["firewall_driver"] == "noop"

    # -- tempest.conf --

    def test_tempest_baremetal_driver(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "tempest.conf")
        assert config["baremetal"]["driver"] == "redfish"

    def test_tempest_swift_available(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "tempest.conf")
        assert config["service_available"]["swift"] == "true"

    def test_tempest_cinder_not_available(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "tempest.conf")
        assert config["service_available"]["cinder"] == "false"

    # -- init.sql --

    def test_mariadb_creates_all_core_dbs(self, vmedia_job):
        _, out, _ = vmedia_job
        sql = (out / "init.sql").read_text()
        for db in ["keystone", "glance", "nova", "neutron", "ironic", "placement"]:
            assert f"CREATE DATABASE IF NOT EXISTS `{db}`" in sql

    def test_mariadb_uses_fixture_password(self, vmedia_job):
        job, out, _ = vmedia_job
        sql = (out / "init.sql").read_text()
        db_pass = job.devstack_localrc.get("DATABASE_PASSWORD", "secretdatabase")
        assert db_pass in sql

    # -- rabbitmq --

    def test_rabbitmq_definitions_valid_json(self, vmedia_job):
        _, out, _ = vmedia_job
        defs = json.loads((out / "definitions.json").read_text())
        assert "users" in defs
        assert "permissions" in defs

    # -- sushy --

    def test_sushy_emulator_has_vmedia(self, vmedia_job):
        _, out, _ = vmedia_job
        content = (out / "emulator.conf").read_text()
        assert "SUSHY_EMULATOR_LISTEN_PORT" in content

    # -- glance --

    def test_glance_file_backend(self, vmedia_job):
        _, out, _ = vmedia_job
        config = ConfigParser()
        config.read(out / "glance-api.conf")
        assert config["glance_store"]["default_backend"] == "file"
        assert config["DEFAULT"]["enabled_backends"] == "file:file"
        assert config["file"]["filesystem_store_datadir"] == "/var/lib/glance/images/"


class TestWithPortOffset:

    def test_port_offset_shifts_all_ports(self, tmp_path):
        data = json.loads((FIXTURES_DIR / "frozen-job-vmedia.json").read_text())
        job_vars = data["vars"]

        job = build_resolved_config(
            job_name="ironic-tempest-uefi-redfish-vmedia",
            localrc=coerce_localrc(job_vars.get("devstack_localrc", {})),
            services=coerce_services(job_vars.get("devstack_services", {})),
            local_conf=job_vars.get("devstack_local_conf", {}),
            tempest_regex=str(job_vars.get("tempest_test_regex", "")),
        )
        job.port_offset = 10000

        pipeline = ConfigPipeline()
        pipeline.generate_all(job, tmp_path)

        ironic = ConfigParser()
        ironic.read(tmp_path / "ironic.conf")
        assert ":13306/" in ironic["database"]["connection"]

        nova = ConfigParser()
        nova.read(tmp_path / "nova.conf")
        assert ":15000" in nova["ironic"]["auth_url"]

        tempest = ConfigParser()
        tempest.read(tmp_path / "tempest.conf")
        assert ":15000/v3" in tempest["identity"]["uri_v3"]
