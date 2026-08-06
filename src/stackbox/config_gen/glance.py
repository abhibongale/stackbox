from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator


class GlanceConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = self._base_config("glance")
        lr = self.job.devstack_localrc

        config["glance_store"] = {
            "default_backend": "file",
        }
        config["file"] = {
            "filesystem_store_datadir": "/var/lib/glance/images/",
        }

        size_limit = lr.get("GLANCE_LIMIT_IMAGE_SIZE_TOTAL", "")
        if size_limit:
            config["DEFAULT"]["image_size_total_limit"] = size_limit

        return {"glance-api.conf": self._render(config)}
