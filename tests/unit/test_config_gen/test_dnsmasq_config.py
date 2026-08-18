from stackbox.config_gen.dnsmasq_conf import DnsmasqConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class TestDnsmasqConfigGenerator:
    def test_generates_dnsmasq_conf(self, vmedia_job_config, port_manager):
        gen = DnsmasqConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "dnsmasq.conf" in files

    def test_uses_provisioning_network_defaults(self, port_manager):
        job = ResolvedJobConfig(job_name="test")
        gen = DnsmasqConfigGenerator(job, port_manager)
        content = gen.generate()["dnsmasq.conf"]
        assert "192.168.24.100,192.168.24.200" in content
        assert "option:router,192.168.24.1" in content

    def test_listens_on_brbm_link(self, port_manager):
        job = ResolvedJobConfig(job_name="test")
        gen = DnsmasqConfigGenerator(job, port_manager)
        content = gen.generate()["dnsmasq.conf"]
        assert "interface=brbm-link" in content

    def test_uses_bind_dynamic(self, port_manager):
        job = ResolvedJobConfig(job_name="test")
        gen = DnsmasqConfigGenerator(job, port_manager)
        content = gen.generate()["dnsmasq.conf"]
        assert "bind-dynamic" in content

    def test_no_tftp_for_vmedia(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            boot_interface="redfish-virtual-media",
        )
        gen = DnsmasqConfigGenerator(job, port_manager)
        content = gen.generate()["dnsmasq.conf"]
        assert "enable-tftp" not in content

    def test_has_tftp_for_pxe(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            boot_interface="pxe",
        )
        gen = DnsmasqConfigGenerator(job, port_manager)
        content = gen.generate()["dnsmasq.conf"]
        assert "enable-tftp" in content
        assert "tftp-root=/var/lib/ironic/tftpboot" in content
