from __future__ import annotations

import ipaddress

from stackbox.config_gen.base import ServiceConfigGenerator


def _parse_dhcp_range(fixed_range: str) -> tuple[str, str, int]:
    try:
        network = ipaddress.ip_network(fixed_range, strict=False)
    except ValueError:
        return ("10.0.0.50", "10.0.0.150", 29)
    hosts = list(network.hosts())
    if len(hosts) < 4:
        return ("10.0.0.50", "10.0.0.150", 29)
    start = hosts[len(hosts) // 4]
    end = hosts[-2]
    return (str(start), str(end), network.prefixlen)


def _gateway(fixed_range: str) -> str:
    try:
        network = ipaddress.ip_network(fixed_range, strict=False)
    except ValueError:
        return "10.0.0.1"
    hosts = list(network.hosts())
    return str(hosts[0]) if hosts else "10.0.0.1"


class DnsmasqConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        lr = self.job.devstack_localrc
        fixed_range = lr.get("FIXED_RANGE", "10.0.0.0/29")
        gw = lr.get("NETWORK_GATEWAY") or _gateway(fixed_range)
        start, end, prefix = _parse_dhcp_range(fixed_range)

        content = f"""\
port=0
interface=brbm
bind-interfaces
dhcp-range={start},{end},{prefix}
dhcp-sequential-ip
dhcp-option=option:router,{gw}
dhcp-option=option:dns-server,{gw}
enable-tftp
tftp-root=/var/lib/ironic/tftpboot
log-facility=/var/log/dnsmasq.log
log-dhcp
"""
        return {"dnsmasq.conf": content}
