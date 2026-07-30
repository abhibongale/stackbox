from stackbox.config_gen.mariadb import MariaDBConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class TestMariaDBConfigGenerator:
    def test_generates_init_sql(self, vmedia_job_config, port_manager):
        gen = MariaDBConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "init.sql" in files

    def test_creates_core_databases(self, vmedia_job_config, port_manager):
        gen = MariaDBConfigGenerator(vmedia_job_config, port_manager)
        sql = gen.generate()["init.sql"]
        for db in ["keystone", "glance", "nova", "neutron", "ironic", "placement"]:
            assert f"CREATE DATABASE IF NOT EXISTS `{db}`" in sql

    def test_cinder_db_when_enabled(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_services={"c-api": True},
        )
        gen = MariaDBConfigGenerator(job, port_manager)
        sql = gen.generate()["init.sql"]
        assert "CREATE DATABASE IF NOT EXISTS `cinder`" in sql

    def test_no_cinder_db_when_disabled(self, vmedia_job_config, port_manager):
        gen = MariaDBConfigGenerator(vmedia_job_config, port_manager)
        sql = gen.generate()["init.sql"]
        assert "cinder" not in sql

    def test_grants_privileges(self, vmedia_job_config, port_manager):
        gen = MariaDBConfigGenerator(vmedia_job_config, port_manager)
        sql = gen.generate()["init.sql"]
        assert "GRANT ALL PRIVILEGES" in sql

    def test_flush_privileges(self, vmedia_job_config, port_manager):
        gen = MariaDBConfigGenerator(vmedia_job_config, port_manager)
        sql = gen.generate()["init.sql"]
        assert "FLUSH PRIVILEGES;" in sql

    def test_escapes_single_quotes_in_password(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={"DATABASE_PASSWORD": "pass'word"},
        )
        gen = MariaDBConfigGenerator(job, port_manager)
        sql = gen.generate()["init.sql"]
        assert "pass\\'word" in sql
        assert "pass'word" not in sql
