from unittest.mock import MagicMock, patch

import pytest

from stackbox.config_gen.ports import PortManager
from stackbox.exceptions import PortConflictError, PreflightError
from stackbox.containers.preflight import (
    check_kvm,
    check_libvirt,
    check_ovs,
    check_podman,
    check_ports,
)


class TestCheckPodman:
    def test_succeeds_when_installed(self):
        with patch("stackbox.containers.preflight._cmd_exists", return_value=True):
            check_podman()

    def test_raises_when_missing(self):
        with patch("stackbox.containers.preflight._cmd_exists", return_value=False):
            with pytest.raises(PreflightError, match="podman"):
                check_podman()


class TestCheckLibvirt:
    def test_succeeds_when_installed(self):
        with patch("stackbox.containers.preflight._cmd_exists", return_value=True):
            check_libvirt()

    def test_raises_when_missing(self):
        with patch("stackbox.containers.preflight._cmd_exists", return_value=False):
            with pytest.raises(PreflightError, match="virsh"):
                check_libvirt()


class TestCheckOvs:
    def test_succeeds_when_installed(self):
        with patch("stackbox.containers.preflight._cmd_exists", return_value=True):
            check_ovs()

    def test_raises_when_missing(self):
        with patch("stackbox.containers.preflight._cmd_exists", return_value=False):
            with pytest.raises(PreflightError, match="ovs-vsctl"):
                check_ovs()


class TestCheckKvm:
    def test_succeeds_when_kvm_exists(self, tmp_path):
        kvm_path = tmp_path / "kvm"
        kvm_path.touch(mode=0o666)
        with patch("pathlib.Path", return_value=kvm_path):
            check_kvm()

    def test_raises_when_kvm_missing(self, tmp_path):
        kvm_path = tmp_path / "kvm"
        with patch("pathlib.Path", return_value=kvm_path):
            with pytest.raises(PreflightError, match="/dev/kvm"):
                check_kvm()


class TestCheckPorts:
    def test_no_conflicts(self):
        pm = PortManager()
        result = MagicMock(stdout="State  Recv-Q  Send-Q  Local Address:Port\nLISTEN 0      128     0.0.0.0:22\n")
        with patch("subprocess.run", return_value=result):
            check_ports(pm)

    def test_detects_conflict(self):
        pm = PortManager()
        result = MagicMock(stdout=f"LISTEN 0 128 0.0.0.0:3306 0.0.0.0:*\n")
        with patch("subprocess.run", return_value=result):
            with pytest.raises(PortConflictError, match="3306"):
                check_ports(pm)

    def test_skips_when_ss_unavailable(self):
        pm = PortManager()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            check_ports(pm)
