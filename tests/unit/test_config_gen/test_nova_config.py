from configparser import ConfigParser

from stackbox.config_gen.nova import NovaConfigGenerator


class TestNovaConfigGenerator:
    def test_generates_nova_conf(self, vmedia_job_config, port_manager):
        gen = NovaConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "nova.conf" in files

    def test_ironic_compute_driver(self, vmedia_job_config, port_manager):
        gen = NovaConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["nova.conf"])

        assert config["DEFAULT"]["compute_driver"] == "ironic.IronicDriver"

    def test_ironic_section_auth(self, vmedia_job_config, port_manager):
        gen = NovaConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["nova.conf"])

        assert "ironic" in config
        assert config["ironic"]["auth_type"] == "password"
        assert config["ironic"]["username"] == "ironic"
        assert ":6385" in config["ironic"]["endpoint_override"]

    def test_placement_section(self, vmedia_job_config, port_manager):
        gen = NovaConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["nova.conf"])

        assert "placement" in config
        assert config["placement"]["username"] == "placement"

    def test_glance_section(self, vmedia_job_config, port_manager):
        gen = NovaConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["nova.conf"])

        assert "glance" in config
        assert ":9292" in config["glance"]["api_servers"]
