from configparser import ConfigParser

from stackbox.config_gen.base import ServiceConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class ConcreteGenerator(ServiceConfigGenerator):
    def generate(self) -> dict[str, str]:
        config = self._base_config("test-service")
        return {"test.conf": self._render(config)}


class TestServiceConfigGenerator:
    def test_base_config_has_database(self, vmedia_job_config, port_manager):
        gen = ConcreteGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        content = files["test.conf"]
        config = ConfigParser()
        config.read_string(content)

        assert "database" in config
        conn = config["database"]["connection"]
        assert "mysql+pymysql://" in conn
        assert ":3306/" in conn

    def test_base_config_has_keystone_authtoken(self, vmedia_job_config, port_manager):
        gen = ConcreteGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        config = ConfigParser()
        config.read_string(files["test.conf"])

        assert "keystone_authtoken" in config
        assert config["keystone_authtoken"]["auth_type"] == "password"
        assert ":5000" in config["keystone_authtoken"]["auth_url"]

    def test_base_config_has_rabbit(self, vmedia_job_config, port_manager):
        gen = ConcreteGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        config = ConfigParser()
        config.read_string(files["test.conf"])

        assert "oslo_messaging_rabbit" in config
        assert config["oslo_messaging_rabbit"]["rabbit_port"] == "5672"

    def test_passwords_from_localrc(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={
                "DATABASE_PASSWORD": "mydbpass",
                "SERVICE_PASSWORD": "mysvcpass",
                "RABBIT_PASSWORD": "myrabbitpass",
            },
        )
        gen = ConcreteGenerator(job, port_manager)
        assert gen._db_pass() == "mydbpass"
        assert gen._service_pass() == "mysvcpass"
        assert gen._rabbit_pass() == "myrabbitpass"

    def test_password_defaults(self, port_manager):
        job = ResolvedJobConfig(job_name="test")
        gen = ConcreteGenerator(job, port_manager)
        assert gen._db_pass() == "secretdatabase"
        assert gen._service_pass() == "secretservice"
        assert gen._rabbit_pass() == "secretrabbit"
        assert gen._admin_pass() == "secretadmin"

    def test_port_offset_in_base_config(self, vmedia_job_config, offset_port_manager):
        gen = ConcreteGenerator(vmedia_job_config, offset_port_manager)
        files = gen.generate()
        config = ConfigParser()
        config.read_string(files["test.conf"])

        assert ":13306/" in config["database"]["connection"]
        assert ":15000" in config["keystone_authtoken"]["auth_url"]
        assert config["oslo_messaging_rabbit"]["rabbit_port"] == "15672"
