from __future__ import annotations

import io
from abc import ABC, abstractmethod
from configparser import ConfigParser

from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class ServiceConfigGenerator(ABC):

    def __init__(self, job: ResolvedJobConfig, port_manager: PortManager):
        self.job = job
        self.ports = port_manager

    def _base_config(self, service_name: str, db_name: str | None = None) -> ConfigParser:
        config = ConfigParser()
        config.optionxform = str

        db = db_name or service_name
        config["database"] = {
            "connection": (
                f"mysql+pymysql://{db}:{self._db_pass()}"
                f"@localhost:{self.ports.get('mariadb')}/{db}"
            ),
        }

        config["keystone_authtoken"] = {
            "auth_url": f"http://localhost:{self.ports.get('keystone')}",
            "auth_type": "password",
            "project_domain_name": "Default",
            "user_domain_name": "Default",
            "project_name": "service",
            "username": service_name,
            "password": self._service_pass(),
            "memcached_servers": f"localhost:{self.ports.get('memcached')}",
        }

        config["oslo_messaging_rabbit"] = {
            "rabbit_host": "localhost",
            "rabbit_port": str(self.ports.get("rabbitmq")),
            "rabbit_userid": "stackbox",
            "rabbit_password": self._rabbit_pass(),
        }

        config["oslo_policy"] = {
            "enforce_scope": "false",
            "enforce_new_defaults": "false",
        }

        return config

    def _render(self, config: ConfigParser) -> str:
        buf = io.StringIO()
        config.write(buf)
        return buf.getvalue()

    @abstractmethod
    def generate(self) -> dict[str, str]:
        """Return {filename: content} for all config files this service needs."""

    def _db_pass(self) -> str:
        return self.job.devstack_localrc.get("DATABASE_PASSWORD", "secretdatabase")

    def _service_pass(self) -> str:
        return self.job.devstack_localrc.get("SERVICE_PASSWORD", "secretservice")

    def _rabbit_pass(self) -> str:
        return self.job.devstack_localrc.get("RABBIT_PASSWORD", "secretrabbit")

    def _admin_pass(self) -> str:
        return self.job.devstack_localrc.get("ADMIN_PASSWORD", "secretadmin")
