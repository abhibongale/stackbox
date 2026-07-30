from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator


class PlacementConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = self._base_config("placement")

        config.remove_section("database")

        config["placement_database"] = {
            "connection": (
                f"mysql+pymysql://placement:{self._db_pass()}"
                f"@localhost:{self.ports.get('mariadb')}/placement"
            ),
        }

        config["api"] = {
            "auth_strategy": "keystone",
        }

        return {"placement.conf": self._render(config)}
