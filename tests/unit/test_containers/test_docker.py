import subprocess
from unittest.mock import MagicMock, patch

import pytest

from stackbox.containers.docker import DockerBackend
from stackbox.exceptions import ContainerError
from stackbox.models.container import ContainerSpec, HealthCheck, VolumeMount


@pytest.fixture
def backend():
    return DockerBackend()


class TestDockerBackend:

    def test_run_builds_basic_command(self, backend):
        spec = ContainerSpec(name="test-ctr", image="test:latest")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n", stderr="")
            cid = backend.run(spec)
            assert cid == "abc123"
            cmd = mock_run.call_args[0][0]
            assert cmd[:4] == ["docker", "run", "-d", "--name"]
            assert "test-ctr" in cmd
            assert "--network" in cmd
            assert "host" in cmd
            assert "test:latest" in cmd

    def test_run_privileged(self, backend):
        spec = ContainerSpec(name="priv", image="img:1", privileged=True)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="id\n", stderr="")
            backend.run(spec)
            cmd = mock_run.call_args[0][0]
            assert "--privileged" in cmd

    def test_run_volumes(self, backend):
        spec = ContainerSpec(
            name="vol-test", image="img:1",
            volumes=[VolumeMount(source="/host/path", target="/ctr/path", options="ro,z")],
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="id\n", stderr="")
            backend.run(spec)
            cmd = mock_run.call_args[0][0]
            assert "-v" in cmd
            idx = cmd.index("-v")
            assert cmd[idx + 1] == "/host/path:/ctr/path:ro,z"

    def test_run_environment(self, backend):
        spec = ContainerSpec(
            name="env-test", image="img:1",
            environment={"FOO": "bar"},
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="id\n", stderr="")
            backend.run(spec)
            cmd = mock_run.call_args[0][0]
            assert "-e" in cmd
            idx = cmd.index("-e")
            assert cmd[idx + 1] == "FOO=bar"

    def test_run_with_command(self, backend):
        spec = ContainerSpec(name="cmd-test", image="img:1", command=["echo", "hello"])
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="id\n", stderr="")
            backend.run(spec)
            cmd = mock_run.call_args[0][0]
            assert cmd[-2:] == ["echo", "hello"]

    def test_run_raises_on_failure(self, backend):
        spec = ContainerSpec(name="fail", image="img:1")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
            with pytest.raises(ContainerError, match="error msg"):
                backend.run(spec)

    def test_run_raises_on_missing_docker(self, backend):
        spec = ContainerSpec(name="nodocker", image="img:1")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(ContainerError, match="docker not found"):
                backend.run(spec)

    def test_exec_returns_exit_code_and_output(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="output\n", stderr="")
            code, out = backend.exec("ctr", ["echo", "hi"])
            assert code == 0
            assert "output" in out

    def test_exec_nonzero_exit(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fail")
            code, out = backend.exec("ctr", ["false"])
            assert code == 1

    def test_stop_does_not_raise_on_failure(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            backend.stop("ctr")

    def test_is_running_true(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
            assert backend.is_running("ctr") is True

    def test_is_running_false(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="false\n", stderr="")
            assert backend.is_running("ctr") is False

    def test_list_containers_empty(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = backend.list_containers("stackbox-")
            assert result == []

    def test_list_containers_ndjson(self, backend):
        ndjson = '{"Names":"stackbox-keystone"}\n{"Names":"stackbox-glance"}\n'
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=ndjson, stderr="")
            result = backend.list_containers("stackbox-")
            assert len(result) == 2
            assert result[0]["Names"] == "stackbox-keystone"
            assert result[1]["Names"] == "stackbox-glance"

    def test_pull_image(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            backend.pull_image("test:latest")
            cmd = mock_run.call_args[0][0]
            assert cmd == ["docker", "pull", "test:latest"]

    def test_create_volume(self, backend):
        with patch("subprocess.run") as mock_run:
            exists_result = MagicMock(returncode=1, stdout="", stderr="")
            create_result = MagicMock(returncode=0, stdout="", stderr="")
            mock_run.side_effect = [exists_result, create_result]
            backend.create_volume("testvol")
            assert mock_run.call_count == 2
            assert mock_run.call_args_list[0][0][0] == ["docker", "volume", "inspect", "testvol"]
            assert mock_run.call_args_list[1][0][0] == ["docker", "volume", "create", "testvol"]

    def test_create_volume_already_exists(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            backend.create_volume("testvol")
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["docker", "volume", "inspect", "testvol"]
