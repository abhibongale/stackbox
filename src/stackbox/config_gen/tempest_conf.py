from __future__ import annotations

from configparser import ConfigParser

from stackbox.config_gen.base import ServiceConfigGenerator


class TempestConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = ConfigParser()
        config.optionxform = str
        svc = self.job.devstack_services

        config["identity"] = {
            "uri_v3": f"http://localhost:{self.ports.get('keystone')}/v3",
            "admin_domain_name": "Default",
        }

        config["auth"] = {
            "admin_username": "admin",
            "admin_password": self._admin_pass(),
            "admin_project_name": "admin",
            "admin_domain_name": "Default",
            "use_dynamic_credentials": "true",
        }

        config["baremetal"] = {
            "driver": self.job.bmc_driver,
            "enabled_hardware_types": ",".join(self.job.hardware_types),
            "catalog_type": "baremetal",
            "endpoint_type": "internal",
            "min_microversion": "1.1",
            "max_microversion": "latest",
        }

        config["compute"] = {
            "flavor_ref": "{{baremetal_flavor_uuid}}",
            "image_ref": "{{test_image_uuid}}",
            "min_compute_nodes": str(self.job.vm_specs.count),
        }

        config["compute-feature-enabled"] = {
            "vnc_console": "false",
            "resize": "false",
        }

        config["service_available"] = {
            "ironic": "true",
            "nova": "true",
            "glance": "true",
            "neutron": "true",
            "swift": str(svc.get("s-proxy", False)).lower(),
            "cinder": str(svc.get("c-api", False)).lower(),
        }

        config["network"] = {
            "shared_physical_network": "mynet",
        }

        config["image"] = {
            "http_image": "http://download.cirros-cloud.net/0.6.2/cirros-0.6.2-x86_64-disk.img",
        }

        config["validation"] = {
            "run_validation": "false",
        }

        return {"tempest.conf": self._render(config)}
