from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator


class NovaConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = self._base_config("nova")
        lr = self.job.devstack_localrc

        config["DEFAULT"].update({
            "compute_driver": "ironic.IronicDriver",
            "my_ip": "0.0.0.0",
            "instance_usage_audit": "true",
            "force_config_drive": lr.get("FORCE_CONFIG_DRIVE", "True"),
        })

        config["api_database"] = {
            "connection": (
                f"mysql+pymysql://nova:{self._db_pass()}"
                f"@localhost:{self.ports.get('mariadb')}/nova_api"
            ),
        }

        config["api"] = {
            "auth_strategy": "keystone",
        }

        config["ironic"] = {
            "auth_url": f"http://localhost:{self.ports.get('keystone')}",
            "auth_type": "password",
            "project_domain_name": "Default",
            "user_domain_name": "Default",
            "project_name": "service",
            "username": "ironic",
            "password": self._service_pass(),
            "endpoint_override": f"http://localhost:{self.ports.get('ironic-api')}",
        }

        config["scheduler"] = {
            "discover_hosts_in_cells_interval": "2",
        }

        config["filter_scheduler"] = {
            "enabled_filters": "ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter",
            "available_filters": "nova.scheduler.filters.all_filters",
            "track_instance_changes": "false",
        }

        config["placement"] = {
            "auth_url": f"http://localhost:{self.ports.get('keystone')}",
            "auth_type": "password",
            "project_domain_name": "Default",
            "user_domain_name": "Default",
            "project_name": "service",
            "username": "placement",
            "password": self._service_pass(),
            "region_name": "RegionOne",
        }

        config["glance"] = {
            "api_servers": f"http://localhost:{self.ports.get('glance')}",
        }

        config["neutron"] = {
            "auth_url": f"http://localhost:{self.ports.get('keystone')}",
            "auth_type": "password",
            "project_domain_name": "Default",
            "user_domain_name": "Default",
            "project_name": "service",
            "username": "neutron",
            "password": self._service_pass(),
            "region_name": "RegionOne",
        }

        vnc_enabled = lr.get("NOVA_VNC_ENABLED", "True").lower()
        config["vnc"] = {
            "enabled": vnc_enabled,
        }

        api_workers = lr.get("API_WORKERS", "1")
        config["DEFAULT"]["osapi_compute_workers"] = api_workers

        config["conductor"] = {
            "workers": api_workers,
        }

        return {"nova.conf": self._render(config)}
