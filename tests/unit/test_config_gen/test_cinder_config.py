from configparser import ConfigParser

from stackbox.config_gen.cinder import CinderConfigGenerator


class TestCinderConfigGenerator:
    def test_generates_cinder_conf(self, vmedia_job_config, port_manager):
        gen = CinderConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "cinder.conf" in files

    def test_lvm_backend(self, vmedia_job_config, port_manager):
        gen = CinderConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["cinder.conf"])
        assert config["DEFAULT"]["enabled_backends"] == "lvm"
        assert config["lvm"]["volume_driver"] == "cinder.volume.drivers.lvm.LVMVolumeDriver"

    def test_iscsi_target_protocol(self, vmedia_job_config, port_manager):
        gen = CinderConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["cinder.conf"])
        assert config["lvm"]["target_protocol"] == "iscsi"

    def test_has_database_section(self, vmedia_job_config, port_manager):
        gen = CinderConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["cinder.conf"])
        assert "cinder" in config["database"]["connection"]
