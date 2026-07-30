from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator


class GlanceConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = self._base_config("glance")
        lr = self.job.devstack_localrc

        has_swift = self.job.devstack_services.get("s-proxy", False)

        if has_swift:
            config["glance_store"] = {
                "default_backend": "swift",
            }
            config["swift"] = {
                "swift_store_auth_address": f"http://localhost:{self.ports.get('keystone')}/v3",
                "swift_store_user": "service:glance",
                "swift_store_key": self._service_pass(),
                "swift_store_create_container_on_put": "true",
                "swift_store_auth_version": "3",
            }
        else:
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
