from __future__ import annotations

from configparser import ConfigParser

from stackbox.config_gen.base import ServiceConfigGenerator


class KeystoneConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = self._base_config("keystone")

        config["token"] = {
            "provider": "fernet",
        }

        config["credential"] = {
            "provider": "fernet",
        }

        config["cache"] = {
            "backend": "dogpile.cache.memcached",
            "memcache_servers": f"localhost:{self.ports.get('memcached')}",
            "enabled": "true",
        }

        return {"keystone.conf": self._render(config)}
