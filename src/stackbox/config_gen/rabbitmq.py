from __future__ import annotations

import json

from stackbox.config_gen.base import ServiceConfigGenerator


class RabbitMQConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        rabbit_pass = self._rabbit_pass()

        conf = (
            "loopback_users.guest = false\n"
            f"listeners.tcp.default = {self.ports.get('rabbitmq')}\n"
            "management.tcp.port = 15672\n"
        )

        definitions = {
            "users": [
                {
                    "name": "stackbox",
                    "password": rabbit_pass,
                    "tags": "administrator",
                },
                {
                    "name": "guest",
                    "password": "guest",
                    "tags": "administrator",
                },
            ],
            "vhosts": [
                {"name": "/"},
            ],
            "permissions": [
                {
                    "user": "stackbox",
                    "vhost": "/",
                    "configure": ".*",
                    "write": ".*",
                    "read": ".*",
                },
                {
                    "user": "guest",
                    "vhost": "/",
                    "configure": ".*",
                    "write": ".*",
                    "read": ".*",
                },
            ],
        }

        return {
            "rabbitmq.conf": conf,
            "definitions.json": json.dumps(definitions, indent=2) + "\n",
        }
