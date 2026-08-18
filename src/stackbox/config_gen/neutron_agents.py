from __future__ import annotations

from configparser import ConfigParser

from stackbox.config_gen.base import ServiceConfigGenerator


class NeutronAgentConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        lr = self.job.devstack_localrc
        bridge_mappings = lr.get("Q_ML2_OVS_BRIDGE_MAPPINGS", "physnet1:brbm")

        l3 = ConfigParser()
        l3.optionxform = str
        l3["DEFAULT"] = {
            "interface_driver": "openvswitch",
            "external_network_bridge": "",
        }

        tenant_type = lr.get("Q_ML2_TENANT_NETWORK_TYPE", "vxlan")

        ovs_agent = ConfigParser()
        ovs_agent.optionxform = str
        ovs_agent["ovs"] = {
            "bridge_mappings": bridge_mappings,
            "local_ip": "127.0.0.1",
        }
        ovs_agent["agent"] = {
            "tunnel_types": tenant_type,
        }
        ovs_agent["securitygroup"] = {
            "firewall_driver": "noop",
        }

        dhcp = ConfigParser()
        dhcp.optionxform = str
        dhcp["DEFAULT"] = {
            "interface_driver": "openvswitch",
            "dhcp_driver": "neutron.agent.linux.dhcp.Dnsmasq",
            "enable_isolated_metadata": "True",
        }

        return {
            "l3_agent.ini": self._render(l3),
            "openvswitch_agent.ini": self._render(ovs_agent),
            "dhcp_agent.ini": self._render(dhcp),
        }
