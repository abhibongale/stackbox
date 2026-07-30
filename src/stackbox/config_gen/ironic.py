from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator
from stackbox.config_gen.translator import DevStackTranslator


class IronicConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = self._base_config("ironic")
        lr = self.job.devstack_localrc

        config["DEFAULT"].update({
            "enabled_hardware_types": lr.get(
                "IRONIC_ENABLED_HARDWARE_TYPES", "redfish"),
            "enabled_boot_interfaces": lr.get(
                "IRONIC_ENABLED_BOOT_INTERFACES", "redfish-virtual-media"),
            "enabled_deploy_interfaces": lr.get(
                "IRONIC_ENABLED_DEPLOY_INTERFACES", "direct"),
            "enabled_management_interfaces": lr.get(
                "IRONIC_ENABLED_MANAGEMENT_INTERFACES", "redfish"),
            "enabled_power_interfaces": lr.get(
                "IRONIC_ENABLED_POWER_INTERFACES", "redfish"),
            "auth_strategy": "keystone",
            "my_ip": "0.0.0.0",
        })

        config["conductor"] = {
            "automated_clean": lr.get("IRONIC_AUTOMATED_CLEAN_ENABLED", "true"),
            "deploy_callback_timeout": lr.get("IRONIC_CALLBACK_TIMEOUT", "600"),
        }

        config["deploy"] = {
            "http_url": f"http://localhost:{self.ports.get('ironic-http')}",
            "http_root": "/var/lib/ironic/httpboot",
        }

        config["service_catalog"] = {
            "endpoint_override": f"http://localhost:{self.ports.get('ironic-api')}",
        }

        config["pxe"] = {
            "tftp_server": "localhost",
            "tftp_root": "/var/lib/ironic/tftpboot",
        }

        config["api"] = {
            "host_ip": "0.0.0.0",
            "port": str(self.ports.get("ironic-api")),
        }

        translated = DevStackTranslator().translate(self.job.devstack_localrc)
        if "ironic" in translated:
            for section, opts in translated["ironic"].items():
                if section not in config:
                    config[section] = {}
                config[section].update(opts)

        return {"ironic.conf": self._render(config)}
