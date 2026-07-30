from __future__ import annotations

import logging
from pathlib import Path

from stackbox.config_gen.cinder import CinderConfigGenerator
from stackbox.config_gen.dnsmasq_conf import DnsmasqConfigGenerator
from stackbox.config_gen.glance import GlanceConfigGenerator
from stackbox.config_gen.ironic import IronicConfigGenerator
from stackbox.config_gen.keystone import KeystoneConfigGenerator
from stackbox.config_gen.mariadb import MariaDBConfigGenerator
from stackbox.config_gen.neutron import NeutronConfigGenerator
from stackbox.config_gen.nova import NovaConfigGenerator
from stackbox.config_gen.placement import PlacementConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.config_gen.rabbitmq import RabbitMQConfigGenerator
from stackbox.config_gen.sushy import SushyConfigGenerator
from stackbox.config_gen.swift import SwiftConfigGenerator
from stackbox.config_gen.tempest_conf import TempestConfigGenerator
from stackbox.config_gen.translator import DevStackTranslator
from stackbox.models.job_config import ResolvedJobConfig

log = logging.getLogger(__name__)

GENERATORS = {
    "keystone": KeystoneConfigGenerator,
    "ironic": IronicConfigGenerator,
    "nova": NovaConfigGenerator,
    "glance": GlanceConfigGenerator,
    "neutron": NeutronConfigGenerator,
    "placement": PlacementConfigGenerator,
    "mariadb": MariaDBConfigGenerator,
    "rabbitmq": RabbitMQConfigGenerator,
    "sushy": SushyConfigGenerator,
    "tempest": TempestConfigGenerator,
}

CONDITIONAL_GENERATORS = {
    "swift": (SwiftConfigGenerator, lambda job: job.devstack_services.get("s-proxy", False)),
    "cinder": (CinderConfigGenerator, lambda job: job.devstack_services.get("c-api", False)),
    "dnsmasq": (DnsmasqConfigGenerator, lambda job: job.boot_interface in ("pxe", "ipxe")),
}


class ConfigPipeline:

    def generate_all(self, job: ResolvedJobConfig, output_dir: Path) -> list[str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        port_manager = PortManager(offset=job.port_offset)
        generated: list[str] = []

        for name, gen_class in GENERATORS.items():
            gen = gen_class(job, port_manager)
            for filename, content in gen.generate().items():
                (output_dir / filename).write_text(content)
                generated.append(filename)

        for name, (gen_class, condition) in CONDITIONAL_GENERATORS.items():
            if condition(job):
                gen = gen_class(job, port_manager)
                for filename, content in gen.generate().items():
                    (output_dir / filename).write_text(content)
                    generated.append(filename)

        unmapped = DevStackTranslator().unmapped_keys(job.devstack_localrc)
        if unmapped:
            log.warning("Unmapped devstack_localrc keys: %s", ", ".join(sorted(unmapped)))

        return sorted(generated)
