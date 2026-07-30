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
        tenant_type = lr.get("Q_ML2_TENANT_NETWORK_TYPE", "vxlan")

        ml2_config["ml2"] = {
            "type_drivers": f"flat,vlan,vxlan,{tenant_type}" if tenant_type not in ("flat", "vlan", "vxlan") else "flat,vlan,vxlan",
            "tenant_network_types": tenant_type,
            "mechanism_drivers": mechanism,
        }

        ml2_config["ml2_type_flat"] = {
            "flat_networks": "physnet1",
        }

        ml2_config["ml2_type_vxlan"] = {
            "vni_ranges": "1:1000",
        }

        if "openvswitch" in mechanism:
            ml2_config["ovs"] = {
                "bridge_mappings": "physnet1:brbm",
            }

        ml2_config["securitygroup"] = {
            "firewall_driver": "noop",
        }

        return {
            "neutron.conf": self._render(server_config),
            "ml2_conf.ini": self._render(ml2_config),
        }
