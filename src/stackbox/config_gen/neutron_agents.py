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

        ovs_agent = ConfigParser()
        ovs_agent.optionxform = str
        # Single-host flat networking: no overlay tunnels. STACKBOX provisions a
        # flat provider network (physnet1:brbm), so VXLAN is unnecessary. It was
        # also actively harmful: configuring tunnel_types=vxlan with a loopback
        # local_ip=127.0.0.1 made the agent build a br-tun that flapped rapidly
        # ("ioctl(SIOCSIFHWADDR) on br-tun failed: No such device") and segfaulted
        # ovs-vswitchd, taking down the entire dataplane and wedging deploys in
        # "clean wait" (no DHCP -> no PXE boot). Empty tunnel_types skips br-tun.
        ovs_agent["ovs"] = {
            "bridge_mappings": bridge_mappings,
        }
        ovs_agent["agent"] = {
            "tunnel_types": "",
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
