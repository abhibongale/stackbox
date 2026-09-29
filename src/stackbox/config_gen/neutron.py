from __future__ import annotations

from configparser import ConfigParser

from stackbox.config_gen.base import ServiceConfigGenerator


class NeutronConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        lr = self.job.devstack_localrc

        server_config = self._base_config("neutron")
        server_config["DEFAULT"].update({
            "core_plugin": "ml2",
            "service_plugins": "router",
            "auth_strategy": "keystone",
            "notify_nova_on_port_status_changes": "true",
            "notify_nova_on_port_data_changes": "true",
        })

        server_config["privsep"] = {
            "user": "root",
            "group": "root",
            "helper_command": (
                "sudo privsep-helper"
                " --config-file /etc/neutron/neutron.conf"
            ),
        }

        server_config["oslo_concurrency"] = {
            "lock_path": "/var/lib/neutron/lock",
        }

        server_config["nova"] = {
            "auth_url": f"http://localhost:{self.ports.get('keystone')}",
            "auth_type": "password",
            "project_domain_name": "Default",
            "user_domain_name": "Default",
            "project_name": "service",
            "username": "nova",
            "password": self._service_pass(),
            "region_name": "RegionOne",
        }

        ml2_config = ConfigParser()
        ml2_config.optionxform = str

        mechanism = lr.get("Q_ML2_PLUGIN_MECHANISM_DRIVERS", "openvswitch")

        # Flat single-host networking (see neutron_agents.py): the OVS agent has
        # no overlay tunnels, so don't advertise vxlan tenant segments it can't
        # bind. The provisioning network is flat on physnet1.
        ml2_config["ml2"] = {
            "type_drivers": "flat,vlan",
            "tenant_network_types": "flat",
            "mechanism_drivers": mechanism,
        }

        ml2_config["ml2_type_flat"] = {
            "flat_networks": "physnet1",
        }

        if "openvswitch" in mechanism:
            ml2_config["ovs"] = {
                "bridge_mappings": lr.get("Q_ML2_OVS_BRIDGE_MAPPINGS", "physnet1:brbm"),
            }

        ml2_config["securitygroup"] = {
            "firewall_driver": "noop",
        }

        return {
            "neutron.conf": self._render(server_config),
            "ml2_conf.ini": self._render(ml2_config),
            "neutron-privsep-sudoers": "neutron ALL=(root) NOPASSWD: ALL\n",
        }
