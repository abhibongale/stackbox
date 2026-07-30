from stackbox.config_gen import ConfigPipeline
from stackbox.models.job_config import ResolvedJobConfig


class TestConfigPipeline:
    def test_generate_all_creates_files(self, vmedia_job_config, tmp_path):
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(vmedia_job_config, tmp_path)

        assert len(generated) > 0
        for filename in generated:
            assert (tmp_path / filename).exists()
            assert (tmp_path / filename).stat().st_size > 0

    def test_always_generates_core_configs(self, vmedia_job_config, tmp_path):
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(vmedia_job_config, tmp_path)

        expected = {
            "ironic.conf",
            "nova.conf",
            "keystone.conf",
            "glance-api.conf",
            "neutron.conf",
            "ml2_conf.ini",
            "placement.conf",
            "init.sql",
            "rabbitmq.conf",
            "definitions.json",
            "emulator.conf",
            "tempest.conf",
            "dhcp_agent.ini",
            "l3_agent.ini",
            "openvswitch_agent.ini",
            "libvirtd.conf",
            "qemu.conf",
        }
        assert expected.issubset(set(generated))

    def test_swift_generated_when_enabled(self, vmedia_job_config, tmp_path):
        assert vmedia_job_config.devstack_services.get("s-proxy", False) is True
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(vmedia_job_config, tmp_path)

        assert "proxy-server.conf" in generated

    def test_swift_not_generated_when_disabled(self, tmp_path):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_services={"s-proxy": False},
        )
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(job, tmp_path)

        assert "proxy-server.conf" not in generated

    def test_cinder_generated_when_enabled(self, tmp_path):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_services={"c-api": True},
        )
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(job, tmp_path)

        assert "cinder.conf" in generated

    def test_cinder_not_generated_when_disabled(self, vmedia_job_config, tmp_path):
        assert vmedia_job_config.devstack_services.get("c-api", False) is False
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(vmedia_job_config, tmp_path)

        assert "cinder.conf" not in generated

    def test_dnsmasq_generated_for_pxe(self, tmp_path):
        job = ResolvedJobConfig(
            job_name="test",
            boot_interface="pxe",
        )
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(job, tmp_path)

        assert "dnsmasq.conf" in generated

    def test_dnsmasq_not_generated_for_vmedia(self, vmedia_job_config, tmp_path):
        assert vmedia_job_config.boot_interface == "redfish-virtual-media"
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(vmedia_job_config, tmp_path)

        assert "dnsmasq.conf" not in generated

    def test_port_offset_applied(self, tmp_path):
        job = ResolvedJobConfig(
            job_name="test",
            port_offset=10000,
        )
        pipeline = ConfigPipeline()
        pipeline.generate_all(job, tmp_path)

        ironic_conf = (tmp_path / "ironic.conf").read_text()
        assert ":13306/" in ironic_conf
        assert ":16385" in ironic_conf

    def test_mariadb_init_sql_has_databases(self, vmedia_job_config, tmp_path):
        pipeline = ConfigPipeline()
        pipeline.generate_all(vmedia_job_config, tmp_path)

        sql = (tmp_path / "init.sql").read_text()
        for db in ["keystone", "glance", "nova", "neutron", "ironic", "placement"]:
            assert f"CREATE DATABASE IF NOT EXISTS `{db}`" in sql
