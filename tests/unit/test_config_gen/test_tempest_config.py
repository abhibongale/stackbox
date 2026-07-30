from configparser import ConfigParser

from stackbox.config_gen.tempest_conf import TempestConfigGenerator
from stackbox.models.job_config import ResolvedJobConfig


class TestTempestConfigGenerator:
    def test_generates_tempest_conf(self, vmedia_job_config, port_manager):
        gen = TempestConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "tempest.conf" in files

    def test_identity_section(self, vmedia_job_config, port_manager):
        gen = TempestConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["tempest.conf"])

        assert ":5000/v3" in config["identity"]["uri_v3"]

    def test_baremetal_section(self, vmedia_job_config, port_manager):
        gen = TempestConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["tempest.conf"])

        assert config["baremetal"]["driver"] == "redfish"
        assert "redfish" in config["baremetal"]["enabled_hardware_types"]

    def test_service_available_reflects_devstack_services(self, vmedia_job_config, port_manager):
        gen = TempestConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["tempest.conf"])

        assert config["service_available"]["swift"] == "true"
        assert config["service_available"]["cinder"] == "false"

    def test_swift_disabled_when_not_in_services(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_services={"s-proxy": False},
        )
        gen = TempestConfigGenerator(job, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["tempest.conf"])

        assert config["service_available"]["swift"] == "false"

    def test_compute_min_nodes(self, vmedia_job_config, port_manager):
        gen = TempestConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["tempest.conf"])

        assert config["compute"]["min_compute_nodes"] == str(vmedia_job_config.vm_specs.count)
