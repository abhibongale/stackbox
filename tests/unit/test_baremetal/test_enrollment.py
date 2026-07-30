from unittest.mock import MagicMock, call, patch

import pytest

from stackbox.baremetal.enrollment import enroll_nodes, _os_env, _wait_for_state
from stackbox.config_gen.ports import PortManager
from stackbox.exceptions import BootstrapError
from stackbox.models.baremetal import BMCConfig, BMCType, VirtualBMNode


@pytest.fixture
def mock_backend():
    backend = MagicMock()

    def smart_exec(container, cmd):
        cmd_str = " ".join(cmd)
        if "provision_state" in cmd_str:
            if "manageable" in cmd_str or any("manage" in c for c in cmd):
                pass
            return (0, "available")
        return (0, "OK")

    backend.exec.return_value = (0, "OK")
    return backend


@pytest.fixture
def redfish_node():
    return VirtualBMNode(
        name="stackbox-bm-0",
        ram_mb=4096,
        vcpus=2,
        disk_gb=20,
        mac_address="52:54:00:aa:bb:cc",
        bmc=BMCConfig(type=BMCType.REDFISH, port=9132),
    )


@pytest.fixture
def ipmi_node():
    return VirtualBMNode(
        name="stackbox-bm-1",
        ram_mb=4096,
        vcpus=2,
        disk_gb=20,
        mac_address="52:54:00:dd:ee:ff",
        bmc=BMCConfig(type=BMCType.IPMI, port=6230),
    )


class TestOsEnv:
    def test_builds_correct_env(self):
        env = _os_env("secret", 5000)
        assert "env" in env
        assert "OS_AUTH_URL=http://localhost:5000/v3" in env
        assert "OS_PASSWORD=secret" in env


class TestWaitForState:
    def test_returns_when_state_matches(self):
        backend = MagicMock()
        backend.exec.return_value = (0, "manageable")
        env = _os_env("pass", 5000)
        _wait_for_state(backend, env, "node-1", "manageable", timeout=5)

    def test_raises_on_timeout(self):
        backend = MagicMock()
        backend.exec.return_value = (0, "enroll")
        env = _os_env("pass", 5000)
        with pytest.raises(BootstrapError, match="did not reach"):
            _wait_for_state(backend, env, "node-1", "manageable", timeout=0.1)


class TestEnrollNodes:

    @patch("stackbox.baremetal.enrollment._wait_for_state")
    def test_redfish_enrollment(self, mock_wait, mock_backend, redfish_node):
        pm = PortManager()
        enroll_nodes(mock_backend, [redfish_node], pm, "admin_pass")

        calls = mock_backend.exec.call_args_list
        create_call = calls[0]
        cmd = create_call[0][1]
        cmd_str = " ".join(cmd)
        assert "--driver" in cmd
        assert "redfish" in cmd_str
        assert "redfish_address" in cmd_str
        assert "redfish_system_id" in cmd_str

    @patch("stackbox.baremetal.enrollment._wait_for_state")
    def test_ipmi_enrollment(self, mock_wait, mock_backend, ipmi_node):
        pm = PortManager()
        enroll_nodes(mock_backend, [ipmi_node], pm, "admin_pass")

        calls = mock_backend.exec.call_args_list
        cmd = calls[0][0][1]
        cmd_str = " ".join(cmd)
        assert "ipmi" in cmd_str
        assert "ipmi_address" in cmd_str

    @patch("stackbox.baremetal.enrollment._wait_for_state")
    def test_creates_port(self, mock_wait, mock_backend, redfish_node):
        pm = PortManager()
        enroll_nodes(mock_backend, [redfish_node], pm, "admin_pass")

        calls = mock_backend.exec.call_args_list
        port_calls = [c for c in calls if "port" in " ".join(c[0][1]) and "create" in " ".join(c[0][1])]
        assert len(port_calls) == 1
        assert "52:54:00:aa:bb:cc" in " ".join(port_calls[0][0][1])

    @patch("stackbox.baremetal.enrollment._wait_for_state")
    def test_manage_and_provide(self, mock_wait, mock_backend, redfish_node):
        pm = PortManager()
        enroll_nodes(mock_backend, [redfish_node], pm, "admin_pass")

        calls = mock_backend.exec.call_args_list
        all_cmds = [" ".join(c[0][1]) for c in calls]
        assert any("node manage" in cmd for cmd in all_cmds)
        assert any("node provide" in cmd for cmd in all_cmds)
        assert mock_wait.call_count == 2

    def test_raises_on_create_failure(self, mock_backend, redfish_node):
        pm = PortManager()
        mock_backend.exec.return_value = (1, "create failed")
        with pytest.raises(BootstrapError, match="create node"):
            enroll_nodes(mock_backend, [redfish_node], pm, "admin_pass")

    @patch("stackbox.baremetal.enrollment._wait_for_state")
    def test_multiple_nodes(self, mock_wait, mock_backend):
        pm = PortManager()
        nodes = [
            VirtualBMNode(name=f"stackbox-bm-{i}", mac_address=f"52:54:00:aa:bb:{i:02x}")
            for i in range(3)
        ]
        enroll_nodes(mock_backend, nodes, pm, "admin_pass")
        create_calls = [
            c for c in mock_backend.exec.call_args_list
            if "node create" in " ".join(c[0][1])
        ]
        assert len(create_calls) == 3
