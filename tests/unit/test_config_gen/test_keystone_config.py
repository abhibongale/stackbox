from configparser import ConfigParser

from stackbox.config_gen.keystone import KeystoneConfigGenerator


class TestKeystoneConfigGenerator:
    def test_generates_keystone_conf(self, vmedia_job_config, port_manager):
        gen = KeystoneConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "keystone.conf" in files

    def test_fernet_token_provider(self, vmedia_job_config, port_manager):
        gen = KeystoneConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["keystone.conf"])
        assert config["token"]["provider"] == "fernet"

    def test_fernet_credential_provider(self, vmedia_job_config, port_manager):
        gen = KeystoneConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["keystone.conf"])
        assert config["credential"]["provider"] == "fernet"

    def test_cache_section(self, vmedia_job_config, port_manager):
        gen = KeystoneConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["keystone.conf"])
        assert config["cache"]["enabled"] == "true"
        assert "11211" in config["cache"]["memcache_servers"]

    def test_has_database_section(self, vmedia_job_config, port_manager):
        gen = KeystoneConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["keystone.conf"])
        assert "keystone" in config["database"]["connection"]
