from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator
from stackbox.models.network import NetworkConfig


class DnsmasqConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        net = NetworkConfig()
        subnet = net.provisioning_subnet

        lines = [
            "port=0",
            "interface=brbm-link",
            "bind-dynamic",
            f"dhcp-range={subnet.allocation_pool_start},{subnet.allocation_pool_end},255.255.255.0,10m",
            "dhcp-sequential-ip",
            f"dhcp-option=option:router,{subnet.gateway}",
            "dhcp-option=option:dns-server",
            "log-facility=/var/log/dnsmasq.log",
            "log-dhcp",
        ]

        if self.job.boot_interface in ("pxe", "ipxe"):
            lines += [
                "enable-tftp",
                "tftp-root=/var/lib/ironic/tftpboot",
            ]

        return {"dnsmasq.conf": "\n".join(lines) + "\n"}
