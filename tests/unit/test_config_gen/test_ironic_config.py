from configparser import ConfigParser

from stackbox.config_gen.ironic import IronicConfigGenerator
from stackbox.models.job_config import ResolvedJobConfig
from stackbox.zuul.freeze import build_resolved_config


class TestIronicConfigGenerator:
    def test_generates_ironic_conf(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "ironic.conf" in files

    def test_hardware_types_from_localrc(self, vmedia_job_config, port_manager):
        # fake-hardware is always appended so ironic-tempest-plugin API tests
        # can create nodes (tempest.conf hardcodes baremetal.driver=fake-hardware).
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        hw_types = config["DEFAULT"]["enabled_hardware_types"].split(",")
        assert "redfish" in hw_types
        assert "fake-hardware" in hw_types

    def test_fake_hardware_not_duplicated(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={"IRONIC_ENABLED_HARDWARE_TYPES": "redfish,fake-hardware"},
        )
        gen = IronicConfigGenerator(job, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        hw_types = config["DEFAULT"]["enabled_hardware_types"].split(",")
        assert hw_types.count("fake-hardware") == 1

    def test_fake_interfaces_always_enabled(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        for iface in ("boot", "deploy", "management", "power",
                      "bios", "console", "inspect", "raid", "rescue", "vendor"):
            key = f"enabled_{iface}_interfaces"
            assert "fake" in config["DEFAULT"][key].split(","), (
                f"'fake' missing from {key}"
            )

    def test_ipmi_job_derives_ipmi_interfaces(self, port_manager):
        # IPMI jobs typically omit the enabled_*_interfaces keys and only set
        # IRONIC_DEPLOY_DRIVER, relying on devstack to derive the rest. The
        # generator must not fall back to redfish for these, or ironic would try
        # to talk redfish to vbmc/IPMI-only nodes. Uses the resolved job fields
        # (bmc_driver/boot_interface/hardware_types) which honor the driver.
        job = build_resolved_config(
            job_name="ironic-tempest-bios-ipmi-autodetect",
            localrc={"IRONIC_DEPLOY_DRIVER": "ipmi"},
            services={},
            local_conf={},
            tempest_regex="",
        )
        config = ConfigParser()
        config.read_string(IronicConfigGenerator(job, port_manager).generate()["ironic.conf"])
        d = config["DEFAULT"]

        assert "ipmi" in d["enabled_hardware_types"].split(",")
        assert "redfish" not in d["enabled_hardware_types"].split(",")
        assert "ipxe" in d["enabled_boot_interfaces"].split(",")
        assert "ipmitool" in d["enabled_management_interfaces"].split(",")
        assert "ipmitool" in d["enabled_power_interfaces"].split(",")
        # redfish must not leak into the management/power interfaces either.
        assert "redfish" not in d["enabled_management_interfaces"].split(",")
        assert "redfish" not in d["enabled_power_interfaces"].split(",")

    def test_autodetect_deploy_interfaces_constrained_to_enabled(self, port_manager):
        # The autodetect deploy interface refuses to load unless every entry in
        # autodetect_deploy_interfaces is also enabled. Ironic's default includes
        # 'ramdisk', which these jobs don't enable, crashing the conductor with
        # DriverLoadError. We must emit a constrained list (enabled, non-fake,
        # non-autodetect) when the job doesn't pin IRONIC_AUTODETECT_DEPLOY_INTERFACES.
        job = build_resolved_config(
            job_name="ironic-tempest-bios-ipmi-autodetect",
            localrc={
                "IRONIC_DEPLOY_DRIVER": "ipmi",
                "IRONIC_ENABLED_DEPLOY_INTERFACES": "direct,bootc,autodetect",
            },
            services={},
            local_conf={},
            tempest_regex="",
        )
        config = ConfigParser()
        config.read_string(IronicConfigGenerator(job, port_manager).generate()["ironic.conf"])
        d = config["DEFAULT"]

        autodetect = d["autodetect_deploy_interfaces"].split(",")
        enabled = d["enabled_deploy_interfaces"].split(",")
        assert "ramdisk" not in autodetect
        assert "autodetect" not in autodetect
        assert "fake" not in autodetect
        # every autodetect entry must be enabled, or ironic-conductor won't load.
        for entry in autodetect:
            assert entry in enabled, f"{entry} in autodetect but not enabled"
        assert set(autodetect) == {"direct", "bootc"}

    def test_autodetect_deploy_interfaces_honors_explicit_localrc(self, port_manager):
        job = build_resolved_config(
            job_name="ironic-autodetect",
            localrc={
                "IRONIC_DEPLOY_DRIVER": "ipmi",
                "IRONIC_ENABLED_DEPLOY_INTERFACES": "direct,bootc,autodetect",
                "IRONIC_AUTODETECT_DEPLOY_INTERFACES": "direct",
            },
            services={},
            local_conf={},
            tempest_regex="",
        )
        config = ConfigParser()
        config.read_string(IronicConfigGenerator(job, port_manager).generate()["ironic.conf"])
        assert config["DEFAULT"]["autodetect_deploy_interfaces"] == "direct"

    def test_boot_interfaces_from_localrc(self, vmedia_job_config, port_manager):
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])

        boot_ifaces = config["DEFAULT"]["enabled_boot_interfaces"].split(",")
        assert "redfish-virtual-media" in boot_ifaces
        # fake must be first so fake-hardware nodes default to fake boot;
        # real hardware (redfish) skips fake since it's not in its supported list.
        assert boot_ifaces[0] == "fake"

    def test_default_boot_interface_not_set_without_localrc(self, vmedia_job_config, port_manager):
        # Without IRONIC_DEFAULT_BOOT_INTERFACE in localrc, we must NOT set a
        # global default_boot_interface. A global value forces it onto fake-hardware
        # nodes too, making test_reset_interfaces fail (value never changes).
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])
        assert "default_boot_interface" not in config["DEFAULT"]

    def test_default_boot_interface_from_localrc(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={"IRONIC_DEFAULT_BOOT_INTERFACE": "pxe"},
        )
        gen = IronicConfigGenerator(job, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])
        assert config["DEFAULT"]["default_boot_interface"] == "pxe"

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

    def test_oslo_policy_keeps_new_defaults(self, vmedia_job_config, port_manager):
        # oslo.policy >= 6.0 removed enforce_scope (scope is always enforced) and
        # defaults enforce_new_defaults to True. Forcing new defaults off pushed
        # allocation creation onto the legacy create_pre_rbac rule, which is
        # project-scoped only and rejected tempest's system-scoped admin token
        # with a 500 ServerFault. Keep new defaults on and drop the dead
        # enforce_scope option.
        gen = IronicConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["ironic.conf"])
        assert config["oslo_policy"]["enforce_new_defaults"] == "true"
        assert "enforce_scope" not in config["oslo_policy"]

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
