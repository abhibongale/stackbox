from stackbox.config_gen.sushy import SushyConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class TestSushyConfigGenerator:
    def test_generates_emulator_conf(self, vmedia_job_config, port_manager):
        gen = SushyConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "emulator.conf" in files

    def test_listen_port(self, vmedia_job_config, port_manager):
        gen = SushyConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["emulator.conf"]
        assert f"SUSHY_EMULATOR_LISTEN_PORT = {port_manager.get('sushy-tools')}" in content

    def test_feature_set_from_localrc(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={"IRONIC_REDFISH_EMULATOR_FEATURE_SET": "minimum"},
        )
        gen = SushyConfigGenerator(job, port_manager)
        content = gen.generate()["emulator.conf"]
        assert '"minimum"' in content

    def test_boot_loader_map(self, vmedia_job_config, port_manager):
        gen = SushyConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["emulator.conf"]
        assert "SUSHY_EMULATOR_BOOT_LOADER_MAP" in content
        assert "OVMF_CODE.fd" in content

    def test_vmedia_verify_ssl_false(self, vmedia_job_config, port_manager):
        gen = SushyConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["emulator.conf"]
        assert "SUSHY_EMULATOR_VMEDIA_VERIFY_SSL = False" in content
