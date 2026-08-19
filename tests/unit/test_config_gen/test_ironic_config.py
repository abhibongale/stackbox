from configparser import ConfigParser

from stackbox.config_gen.ironic import IronicConfigGenerator
from stackbox.models.job_config import ResolvedJobConfig


class TestIronicConfigGenerator:
    def test_generates_ironic_conf(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "ironic.conf" in files

    def test_hardware_types_from_localrc(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        assert config["DEFAULT"]["enabled_hardware_types"] == "redfish"

    def test_boot_interfaces_from_localrc(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        assert config["DEFAULT"]["enabled_boot_interfaces"] == "redfish-virtual-media"

    def test_conductor_section(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        assert "conductor" in config
        assert config["conductor"]["automated_clean"] == "False"

    def test_deploy_section_has_http_url(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        assert "deploy" in config
        assert ":3928" in config["deploy"]["http_url"]

    def test_default_boot_mode_uefi(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        assert config["deploy"]["default_boot_mode"] == "uefi"

    def test_default_boot_mode_bios(self, port_manager):
        # A bios job must make Ironic hand out the bios PXE bootfile instead of
        # the uefi default (snponly.efi), which a legacy-BIOS VM cannot boot.
        job = ResolvedJobConfig(job_name="bios-pxe", boot_mode="bios")
        gen = IronicConfigGenerator(job, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        assert config["deploy"]["default_boot_mode"] == "bios"

    def test_api_port(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        assert config["api"]["port"] == "6385"

    def test_port_offset(self, vmedia_job_config, offset_port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, offset_port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        assert ":13928" in config["deploy"]["http_url"]
        assert config["api"]["port"] == "16385"
