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

        assert config["baremetal"]["driver"] == "fake-hardware"
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

    def test_api_only_job_marks_nova_glance_unavailable(self, port_manager):
        # ironic-tempest-functional-python3 disables nova/glance; tempest must
        # not advertise them or emit unresolved image/flavor refs.
        job = ResolvedJobConfig(
            job_name="functional",
            devstack_services={"n-api": False, "g-api": False, "q-svc": True},
        )
        gen = TempestConfigGenerator(job, port_manager)
        conf_text = gen.generate()["tempest.conf"]
        config = ConfigParser()
        config.read_string(conf_text)

        assert config["service_available"]["nova"] == "false"
        assert config["service_available"]["glance"] == "false"
        assert config["service_available"]["neutron"] == "true"
        # No compute section and no leaked "{{...}}" placeholders.
        assert not config.has_section("compute")
        assert "whole_disk_image_ref" not in config["baremetal"]
        assert "{{" not in conf_text
