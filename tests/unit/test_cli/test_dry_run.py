from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from stackbox.cli.main import _print_dry_run
from stackbox.models.job_config import ResolvedJobConfig


@pytest.fixture
def vmedia_config():
    return ResolvedJobConfig(
        job_name="ironic-tempest-uefi-redfish-vmedia",
        boot_interface="redfish-virtual-media",
        bmc_driver="redfish",
        devstack_localrc={"ADMIN_PASSWORD": "secret"},
        devstack_services={"s-proxy": True},
        tempest_test_regex="ironic_tempest_plugin.tests.scenario",
    )


@pytest.fixture
def pxe_config():
    return ResolvedJobConfig(
        job_name="ironic-tempest-pxe-ipmi",
        boot_interface="pxe",
        bmc_driver="ipmi",
        devstack_localrc={"ADMIN_PASSWORD": "secret"},
    )


def _capture_output(config, release="2025.1-ubuntu-noble", local_repos=None):
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=200)
    _print_dry_run(console, config, release, local_repos=local_repos)
    return buf.getvalue()


class TestPrintDryRun:

    def test_shows_job_name(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "ironic-tempest-uefi-redfish-vmedia" in output

    def test_shows_boot_interface(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "redfish-virtual-media" in output

    def test_shows_bmc_driver(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "redfish" in output

    def test_shows_port_assignments(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "3306" in output
        assert "6385" in output

    def test_shows_config_files(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "ironic.conf" in output
        assert "neutron.conf" in output
        assert "keystone.conf" in output

    def test_shows_containers(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "stackbox-mariadb" in output
        assert "stackbox-keystone" in output
        assert "stackbox-ironic-api" in output

    def test_shows_shared_volumes(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "stackbox-libvirt-sock" in output
        assert "stackbox-ironic-shared" in output

    def test_shows_bootstrap_phases(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "Infrastructure" in output
        assert "Keystone" in output
        assert "Tempest" in output

    def test_shows_tempest_regex(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "ironic_tempest_plugin" in output

    def test_port_offset_applied(self):
        config = ResolvedJobConfig(
            job_name="test",
            port_offset=10000,
        )
        output = _capture_output(config)
        assert "13306" in output
        assert "16385" in output

    def test_pxe_job_shows_dnsmasq_config(self, pxe_config):
        output = _capture_output(pxe_config)
        assert "dnsmasq.conf" in output

    def test_no_temp_files_left(self, vmedia_config):
        import os
        import tempfile

        before = set(os.listdir(tempfile.gettempdir()))
        _capture_output(vmedia_config)
        after = set(os.listdir(tempfile.gettempdir()))
        new_dirs = after - before
        stackbox_dirs = [d for d in new_dirs if "stackbox" in d.lower()]
        assert len(stackbox_dirs) == 0

    def test_shows_local_repos(self, vmedia_config):
        local_repos = {"ironic-api": "/home/user/ironic"}
        output = _capture_output(vmedia_config, local_repos=local_repos)
        assert "Local Dev Builds" in output
        assert "ironic-api <-" in output
        assert "stackbox-ironic-api:local" in output

    def test_no_local_repos_section_when_empty(self, vmedia_config):
        output = _capture_output(vmedia_config)
        assert "Local Dev Builds" not in output
