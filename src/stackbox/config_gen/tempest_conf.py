from __future__ import annotations

from configparser import ConfigParser

from stackbox.config_gen.base import ServiceConfigGenerator


class TempestConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = ConfigParser()
        config.optionxform = str
        svc = self.job.devstack_services

        # Absent toggle == devstack default (enabled) for these services, so
        # full deploy jobs keep advertising them while API-only jobs that set
        # them False (e.g. ironic-tempest-functional-python3) don't.
        nova_enabled = svc.get("n-api", True)
        glance_enabled = svc.get("g-api", True)
        neutron_enabled = svc.get("q-svc", True)

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
            # ironic-tempest-plugin's API test base class checks CONF.baremetal.driver
            # against SUPPORTED_DRIVERS = ['fake', 'fake-hardware'] and skips all tests
            # if it doesn't match. Devstack always hard-codes this to 'fake-hardware'
            # regardless of the actual provisioning hardware type (see devstack/lib/ironic:
            # "# Driver for API tests").
            "driver": "fake-hardware",
            "enabled_hardware_types": ",".join(self.job.hardware_types),
            "catalog_type": "baremetal",
            "endpoint_type": "internal",
            "min_microversion": "1.1",
            "max_microversion": "latest",
        }
        # These refs are resolved from glance/nova at bootstrap; only emit them
        # when those services exist, otherwise the placeholders never resolve and
        # leak literal "{{...}}" into tempest.conf.
        if glance_enabled:
            config["baremetal"]["whole_disk_image_ref"] = "{{test_image_uuid}}"
            config["baremetal"]["whole_disk_image_url"] = (
                "http://download.cirros-cloud.net/0.6.2/cirros-0.6.2-x86_64-disk.img"
            )

        if nova_enabled:
            config["compute"] = {
                "flavor_ref": "{{baremetal_flavor_uuid}}",
                "image_ref": "{{test_image_uuid}}",
                "fixed_network_name": "provisioning",
                "min_compute_nodes": str(self.job.vm_specs.count),
            }

            config["compute-feature-enabled"] = {
                "vnc_console": "false",
                "resize": "false",
                "console_output": "false",
            }

        config["service_available"] = {
            "ironic": "true",
            "nova": str(nova_enabled).lower(),
            "glance": str(glance_enabled).lower(),
            "neutron": str(neutron_enabled).lower(),
            "swift": str(svc.get("s-proxy", False)).lower(),
            "cinder": str(svc.get("c-api", False)).lower(),
        }

        config["network"] = {
            "shared_physical_network": "true",
        }

        config["image"] = {
            "http_image": "http://download.cirros-cloud.net/0.6.2/cirros-0.6.2-x86_64-disk.img",
        }

        config["validation"] = {
            "run_validation": "true",
            "connect_method": "fixed",
            "network_for_ssh": "provisioning",
            "ping_timeout": "120",
            "ssh_timeout": "120",
        }

        return {"tempest.conf": self._render(config)}
