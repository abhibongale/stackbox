from configparser import ConfigParser

from stackbox.config_gen.neutron_agents import NeutronAgentConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class TestNeutronAgentConfigGenerator:

    def test_generates_three_files(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert set(files.keys()) == {"dhcp_agent.ini", "l3_agent.ini", "openvswitch_agent.ini"}

    def test_dhcp_agent_interface_driver(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["dhcp_agent.ini"])
        assert config["DEFAULT"]["interface_driver"] == "openvswitch"

    def test_dhcp_agent_isolated_metadata(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["dhcp_agent.ini"])
        assert config["DEFAULT"]["enable_isolated_metadata"] == "True"

    def test_dhcp_agent_force_metadata(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["dhcp_agent.ini"])
        assert config["DEFAULT"]["force_metadata"] == "True"

    def test_l3_agent_interface_driver(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["l3_agent.ini"])
        assert config["DEFAULT"]["interface_driver"] == "openvswitch"

    def test_l3_agent_external_bridge_empty(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["l3_agent.ini"])
        assert config["DEFAULT"]["external_network_bridge"] == ""

    def test_ovs_agent_bridge_mappings(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.optionxform = str
        config.read_string(gen.generate()["openvswitch_agent.ini"])
        assert config["ovs"]["bridge_mappings"] == "physnet1:brbm"

    def test_ovs_agent_firewall_noop(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.optionxform = str
        config.read_string(gen.generate()["openvswitch_agent.ini"])
        assert config["securitygroup"]["firewall_driver"] == "noop"

    def test_ovs_agent_local_ip(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.optionxform = str
        config.read_string(gen.generate()["openvswitch_agent.ini"])
        assert config["ovs"]["local_ip"] == "127.0.0.1"

    def test_ovs_agent_tunnel_types(self, vmedia_job_config, port_manager):
        gen = NeutronAgentConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.optionxform = str
        config.read_string(gen.generate()["openvswitch_agent.ini"])
        assert config["agent"]["tunnel_types"] == "vxlan"

    def test_custom_bridge_mappings_from_localrc(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={"Q_ML2_OVS_BRIDGE_MAPPINGS": "mynet:br-custom"},
        )
        gen = NeutronAgentConfigGenerator(job, port_manager)
        config = ConfigParser()
        config.optionxform = str
        config.read_string(gen.generate()["openvswitch_agent.ini"])
        assert config["ovs"]["bridge_mappings"] == "mynet:br-custom"
