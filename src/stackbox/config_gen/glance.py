from __future__ import annotations

import yaml

from stackbox.config_gen.base import ServiceConfigGenerator

GLANCE_POLICY = {
    "publicize_image": "",
    "communitize_image": "",
    "add_image": "",
    "delete_image": "",
    "get_image": "",
    "modify_image": "",
}


class GlanceConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = self._base_config("glance")
        lr = self.job.devstack_localrc

        config["DEFAULT"]["enabled_backends"] = "file:file"

        config["glance_store"] = {
            "default_backend": "file",
        }
        config["file"] = {
            "filesystem_store_datadir": "/var/lib/glance/images/",
        }

        config["oslo_policy"]["policy_file"] = "/etc/glance/policy.yaml"

        size_limit = lr.get("GLANCE_LIMIT_IMAGE_SIZE_TOTAL", "")
        if size_limit:
            config["DEFAULT"]["image_size_total_limit"] = size_limit

        return {
            "glance-api.conf": self._render(config),
            "glance-policy.yaml": yaml.dump(GLANCE_POLICY, default_flow_style=False),
        }
