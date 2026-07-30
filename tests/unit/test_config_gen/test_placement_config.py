from configparser import ConfigParser

from stackbox.config_gen.placement import PlacementConfigGenerator


class TestPlacementConfigGenerator:
    def test_generates_placement_conf(self, vmedia_job_config, port_manager):
        gen = PlacementConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "placement.conf" in files

    def test_uses_placement_database_section(self, vmedia_job_config, port_manager):
        gen = PlacementConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["placement.conf"])
        assert "placement_database" in config.sections()
        assert "placement" in config["placement_database"]["connection"]

    def test_no_database_section(self, vmedia_job_config, port_manager):
        gen = PlacementConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["placement.conf"])
        assert "database" not in config.sections()

    def test_api_auth_strategy(self, vmedia_job_config, port_manager):
        gen = PlacementConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["placement.conf"])
        assert config["api"]["auth_strategy"] == "keystone"
