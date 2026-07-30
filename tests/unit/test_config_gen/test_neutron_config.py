from configparser import ConfigParser

from stackbox.config_gen.neutron import NeutronConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class TestNeutronConfigGenerator:
    def test_generates_two_files(self, vmedia_job_config, port_manager):
        gen = NeutronConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "neutron.conf" in files
        assert "ml2_conf.ini" in files

    def test_core_plugin_ml2(self, vmedia_job_config, port_manager):
        gen = NeutronConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["neutron.conf"])
        assert config["DEFAULT"]["core_plugin"] == "ml2"

    def test_nova_auth_section(self, vmedia_job_config, port_manager):
        gen = NeutronConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["neutron.conf"])
        assert config["nova"]["username"] == "nova"
        assert config["nova"]["auth_type"] == "password"

    def test_ml2_mechanism_drivers_from_localrc(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={"Q_ML2_PLUGIN_MECHANISM_DRIVERS": "openvswitch,linuxbridge"},
        )
        gen = NeutronConfigGenerator(job, port_manager)
        config = ConfigParser()
        config.optionxform = str
        config.read_string(gen.generate()["ml2_conf.ini"])
        assert config["ml2"]["mechanism_drivers"] == "openvswitch,linuxbridge"

    def test_ovs_bridge_mappings_when_openvswitch(self, vmedia_job_config, port_manager):
        gen = NeutronConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.optionxform = str
        config.read_string(gen.generate()["ml2_conf.ini"])
        assert config["ovs"]["bridge_mappings"] == "physnet1:brbm"

    def test_securitygroup_noop(self, vmedia_job_config, port_manager):
        gen = NeutronConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.optionxform = str
        config.read_string(gen.generate()["ml2_conf.ini"])
        assert config["securitygroup"]["firewall_driver"] == "noop"
