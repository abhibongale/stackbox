import socket
from unittest.mock import MagicMock, patch

import pytest

from stackbox.containers.health import (
    assert_containers_alive,
    check,
    dead_container_status,
    wait_tcp,
)
from stackbox.exceptions import BootstrapError
from stackbox.models.container import ContainerSpec, HealthCheck


class TestWaitTcp:
    def test_succeeds_immediately(self):
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            wait_tcp("localhost", 3306, timeout=5)

    def test_timeout_raises(self):
        with patch("socket.create_connection", side_effect=OSError):
            with pytest.raises(BootstrapError, match="Timed out"):
                wait_tcp("localhost", 3306, timeout=0.1, interval=0.05)


class TestCheck:
    def test_no_health_check_is_noop(self):
        spec = ContainerSpec(name="test", image="img:1", health_check=None)
        check(MagicMock(), spec)

    def test_tcp_health_check(self):
        spec = ContainerSpec(
            name="test", image="img:1",
            health_check=HealthCheck(type="tcp", target="3306", timeout_seconds=1),
        )
        with patch("stackbox.containers.health.wait_tcp") as mock_wait:
            check(MagicMock(), spec)
            mock_wait.assert_called_once()

    def test_http_health_check(self):
        spec = ContainerSpec(
            name="test", image="img:1",
            health_check=HealthCheck(type="http", target="http://localhost:5000/v3", timeout_seconds=1),
        )
        with patch("stackbox.containers.health.wait_http") as mock_wait:
            check(MagicMock(), spec)
            mock_wait.assert_called_once()

    def test_exec_health_check(self):
        spec = ContainerSpec(
            name="test", image="img:1",
            health_check=HealthCheck(type="exec", target="mysql -e SELECT 1", timeout_seconds=1),
        )
        with patch("stackbox.containers.health.wait_exec") as mock_wait:
            check(MagicMock(), spec)
            mock_wait.assert_called_once()

    def test_unknown_type_raises(self):
        spec = ContainerSpec(
            name="test", image="img:1",
            health_check=HealthCheck(type="invalid", target="x", timeout_seconds=1),
        )
        with pytest.raises(BootstrapError, match="Unknown health check"):
            check(MagicMock(), spec)


class TestDeadContainerStatus:
    def test_running_is_alive(self):
        backend = MagicMock()
        backend.inspect.return_value = {"State": {"Status": "running"}}
        assert dead_container_status(backend, "c") is None

    def test_restarting_is_tolerated(self):
        # on-failure restart backoff must not be treated as dead.
        backend = MagicMock()
        backend.inspect.return_value = {"State": {"Status": "restarting"}}
        assert dead_container_status(backend, "c") is None

    def test_exited_is_dead(self):
        backend = MagicMock()
        backend.inspect.return_value = {"State": {"Status": "exited"}}
        assert dead_container_status(backend, "c") == "exited"

    def test_missing_container_is_tolerated(self):
        backend = MagicMock()
        backend.inspect.side_effect = Exception("no such container")
        assert dead_container_status(backend, "c") is None


class TestAssertContainersAlive:
    def test_noop_when_all_running(self):
        backend = MagicMock()
        backend.inspect.return_value = {"State": {"Status": "running"}}
        assert_containers_alive(backend, ["a", "b"])

    def test_raises_with_logs_on_dead_container(self):
        backend = MagicMock()
        backend.inspect.return_value = {"State": {"Status": "exited"}}
        backend.logs.return_value = "segfault in revalidator"
        with pytest.raises(BootstrapError, match="exited"):
            assert_containers_alive(backend, ["stackbox-openvswitch-vswitchd"])
        backend.logs.assert_called_once()
