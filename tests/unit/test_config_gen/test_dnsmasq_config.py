from stackbox.config_gen.dnsmasq_conf import DnsmasqConfigGenerator, _parse_dhcp_range, _gateway
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class TestDnsmasqHelpers:
    def test_parse_dhcp_range_default(self):
        start, end, netmask = _parse_dhcp_range("10.0.0.0/29")
        assert netmask == "255.255.255.248"

    def test_parse_dhcp_range_larger_network(self):
        start, end, netmask = _parse_dhcp_range("10.1.0.0/20")
        assert netmask == "255.255.240.0"
        assert start.startswith("10.1.")
        assert end.startswith("10.1.")

    def test_parse_dhcp_range_invalid_falls_back(self):
        start, end, netmask = _parse_dhcp_range("not-a-cidr")
        assert start == "10.0.0.50"
        assert end == "10.0.0.150"
        assert netmask == "255.255.255.248"

    def test_gateway_from_network(self):
        gw = _gateway("10.1.0.0/20")
        assert gw == "10.1.0.1"

    def test_gateway_invalid_falls_back(self):
        gw = _gateway("invalid")
        assert gw == "10.0.0.1"


class TestDnsmasqConfigGenerator:
    def test_generates_dnsmasq_conf(self, vmedia_job_config, port_manager):
        gen = DnsmasqConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "dnsmasq.conf" in files

    def test_uses_fixed_range_from_localrc(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={"FIXED_RANGE": "10.1.0.0/20"},
        )
        gen = DnsmasqConfigGenerator(job, port_manager)
        content = gen.generate()["dnsmasq.conf"]
        assert "10.1." in content
        assert "255.255.240.0" in content

    def test_uses_network_gateway_from_localrc(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={
                "FIXED_RANGE": "10.1.0.0/20",
                "NETWORK_GATEWAY": "10.1.0.254",
            },
        )
        gen = DnsmasqConfigGenerator(job, port_manager)
        content = gen.generate()["dnsmasq.conf"]
        assert "option:router,10.1.0.254" in content

    def test_has_tftp_root(self, vmedia_job_config, port_manager):
        gen = DnsmasqConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["dnsmasq.conf"]
        assert "tftp-root=/var/lib/ironic/tftpboot" in content
