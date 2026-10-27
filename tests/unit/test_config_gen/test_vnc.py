from configparser import ConfigParser

import pytest

from stackbox.config_gen.ironic import IronicConfigGenerator
from stackbox.config_gen.tempest_conf import TempestConfigGenerator
from stackbox.config_gen.vnc import (
    VNC_CONSOLE_IMAGE,
    enabled_console_interfaces,
    vnc_settings,
)
from stackbox.models.job_config import ResolvedJobConfig


def _vnc_job(localrc=None, **kwargs):
    """Mirrors ironic-tempest-vnc-container's ir-novnc service toggle."""
    return ResolvedJobConfig(
        job_name="ironic-tempest-vnc-container",
        devstack_services={"ir-novnc": True},
        devstack_localrc=localrc or {},
        **kwargs,
    )


def _ironic_conf(job, port_manager):
    config = ConfigParser()
    config.read_string(IronicConfigGenerator(job, port_manager).generate()["ironic.conf"])
    return config


def _tempest_conf(job, port_manager):
    config = ConfigParser()
    config.read_string(TempestConfigGenerator(job, port_manager).generate()["tempest.conf"])
    return config


class TestVncSettings:

    def test_absent_toggle_is_disabled(self):
        # Devstack keeps ir-novnc off unless a job enables it.
        assert vnc_settings(ResolvedJobConfig(job_name="t")) is None

    def test_explicitly_disabled(self):
        job = ResolvedJobConfig(job_name="t", devstack_services={"ir-novnc": False})
        assert vnc_settings(job) is None

    def test_devstack_defaults(self):
        vnc = vnc_settings(_vnc_job())
        assert vnc.console_interfaces == "fake-graphical,fake,no-console"
        assert vnc.default_console_interface == "fake-graphical"
        assert vnc.provider == "systemd"
        assert vnc.port == 6090

    def test_port_follows_offset(self):
        assert vnc_settings(_vnc_job(port_offset=10000)).port == 16090

    def test_localrc_overrides_win(self):
        vnc = vnc_settings(_vnc_job({
            "IRONIC_ENABLED_CONSOLE_INTERFACES": "redfish-graphical,no-console",
            "IRONIC_DEFAULT_CONSOLE_INTERFACE": "redfish-graphical",
            "IRONIC_VNC_CONTAINER_PROVIDER": "container",
            "IRONIC_NOVNCPROXY_PORT": "7000",
        }))
        assert vnc.console_interfaces == "redfish-graphical,no-console"
        assert vnc.default_console_interface == "redfish-graphical"
        assert vnc.effective_provider == "container"
        assert vnc.port == 7000

    @pytest.mark.parametrize("provider", ["systemd", "kubernetes"])
    def test_unrunnable_providers_fall_back_to_container(self, provider):
        vnc = vnc_settings(_vnc_job({"IRONIC_VNC_CONTAINER_PROVIDER": provider}))
        assert vnc.provider == provider
        assert vnc.effective_provider == "container"
        assert vnc.needs_engine

    def test_fake_provider_needs_no_engine(self):
        vnc = vnc_settings(_vnc_job({"IRONIC_VNC_CONTAINER_PROVIDER": "fake"}))
        assert vnc.effective_provider == "fake"
        assert not vnc.needs_engine


class TestEnabledConsoleInterfaces:

    def test_non_vnc_default_unchanged(self):
        assert enabled_console_interfaces(ResolvedJobConfig(job_name="t")) == "no-console,fake"

    def test_non_vnc_localrc_gets_fake(self):
        job = ResolvedJobConfig(
            job_name="t", devstack_localrc={"IRONIC_ENABLED_CONSOLE_INTERFACES": "ipmitool-socat"})
        assert enabled_console_interfaces(job) == "ipmitool-socat,fake"

    def test_vnc_includes_fake_graphical(self):
        assert "fake-graphical" in enabled_console_interfaces(_vnc_job()).split(",")


class TestIronicConfVnc:

    def test_vnc_container_job(self, port_manager):
        job = _vnc_job({"IRONIC_VNC_CONTAINER_PROVIDER": "container"})
        config = _ironic_conf(job, port_manager)

        ifaces = config["DEFAULT"]["enabled_console_interfaces"].split(",")
        assert "fake-graphical" in ifaces
        assert config["DEFAULT"]["default_console_interface"] == "fake-graphical"
        vnc = config["vnc"]
        assert vnc["enabled"] == "True"
        assert vnc["container_provider"] == "container"
        assert vnc["console_image"] == VNC_CONSOLE_IMAGE
        assert vnc["container_executable"] == "docker"
        # novncproxy must be able to reach it, so never an unspecified address
        assert vnc["container_publish_port"] == "127.0.0.1::5900"
        assert vnc["port"] == "6090"

    def test_systemd_job_configured_as_container(self, port_manager, caplog):
        config = _ironic_conf(_vnc_job(), port_manager)
        assert config["vnc"]["container_provider"] == "container"
        assert "can't run under stackbox" in caplog.text

    def test_fake_provider_has_no_engine_settings(self, port_manager):
        job = _vnc_job({"IRONIC_VNC_CONTAINER_PROVIDER": "fake"})
        vnc = _ironic_conf(job, port_manager)["vnc"]
        assert vnc["container_provider"] == "fake"
        assert "container_executable" not in vnc

    def test_explicit_default_console_interface_kept(self, port_manager):
        job = _vnc_job({"IRONIC_DEFAULT_CONSOLE_INTERFACE": "fake"})
        config = _ironic_conf(job, port_manager)
        assert config["DEFAULT"]["default_console_interface"] == "fake"

    @pytest.mark.parametrize("services", [{}, {"ir-novnc": False}])
    def test_non_vnc_job_untouched(self, port_manager, services):
        job = ResolvedJobConfig(job_name="t", devstack_services=services)
        config = _ironic_conf(job, port_manager)
        assert config["DEFAULT"]["enabled_console_interfaces"] == "no-console,fake"
        assert "default_console_interface" not in config["DEFAULT"]
        assert not config.has_section("vnc")


class TestTempestConfVnc:

    @pytest.mark.parametrize("job", [
        ResolvedJobConfig(job_name="t"),
        _vnc_job({"IRONIC_VNC_CONTAINER_PROVIDER": "container"}),
    ])
    def test_matches_ironic_conf(self, port_manager, job):
        ironic = _ironic_conf(job, port_manager)["DEFAULT"]["enabled_console_interfaces"]
        tempest = _tempest_conf(job, port_manager)["baremetal"]["enabled_console_interfaces"]
        assert tempest == ironic

    def test_vnc_job_lets_graphical_tests_run(self, port_manager):
        # TestGraphicalConsole.skip_checks looks for exactly this.
        config = _tempest_conf(_vnc_job(), port_manager)
        assert "fake-graphical" in config["baremetal"]["enabled_console_interfaces"].split(",")
