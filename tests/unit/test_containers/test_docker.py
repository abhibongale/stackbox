import signal
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

    def test_run_restart_policy(self, backend):
        spec = ContainerSpec(name="ovs", image="img:1", restart_policy="on-failure:5")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="id\n", stderr="")
            backend.run(spec)
            cmd = mock_run.call_args[0][0]
            assert "--restart" in cmd
            assert cmd[cmd.index("--restart") + 1] == "on-failure:5"

    def test_run_no_restart_policy_by_default(self, backend):
        spec = ContainerSpec(name="plain", image="img:1")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="id\n", stderr="")
            backend.run(spec)
            cmd = mock_run.call_args[0][0]
            assert "--restart" not in cmd

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

    def test_list_volumes_with_prefix(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="stackbox-mariadb-data\nstackbox-ovs-run\n", stderr=""
            )
            vols = backend.list_volumes(prefix="stackbox-")
            assert vols == ["stackbox-mariadb-data", "stackbox-ovs-run"]
            assert mock_run.call_args[0][0] == [
                "docker", "volume", "ls", "--format", "{{.Name}}",
                "--filter", "name=stackbox-",
            ]

    def test_remove_volume_success(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            assert backend.remove_volume("testvol") is True
            assert mock_run.call_args[0][0] == ["docker", "volume", "rm", "-f", "testvol"]

    def test_remove_volume_in_use_returns_false(self, backend):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="volume is in use"
            )
            assert backend.remove_volume("testvol") is False

    def test_build_image_success(self, backend):
        with patch.object(backend, "_run_build_cmd") as mock_build:
            mock_build.return_value = MagicMock(returncode=0, stdout="", stderr="")
            backend.build_image(
                tag="img:local", context=".", containerfile="Containerfile",
                build_args={"SERVICE_NAME": "ironic-api"},
            )
            mock_build.assert_called_once()
            cmd = mock_build.call_args[0][0]
            assert cmd[:3] == ["docker", "build", "-t"]
            assert "--build-arg" in cmd
            assert "SERVICE_NAME=ironic-api" in cmd

    def test_build_image_retries_on_locked_ref(self, backend):
        locked = MagicMock(
            returncode=1, stdout="",
            stderr="ref moby/1/abc locked for 34s: unavailable",
        )
        ok = MagicMock(returncode=0, stdout="", stderr="")
        with patch.object(backend, "_run_build_cmd", side_effect=[locked, ok]) as m, \
                patch("stackbox.containers.docker.time.sleep") as mock_sleep:
            backend.build_image(tag="img:local", context=".", containerfile="Cf")
            assert m.call_count == 2
            mock_sleep.assert_called_once()

    def test_build_image_raises_after_exhausting_retries(self, backend):
        locked = MagicMock(
            returncode=1, stdout="",
            stderr="ref moby/1/abc locked for 34s: unavailable",
        )
        with patch.object(backend, "_run_build_cmd", return_value=locked) as m, \
                patch("stackbox.containers.docker.time.sleep"):
            with pytest.raises(ContainerError):
                backend.build_image(tag="img:local", context=".", containerfile="Cf")
            assert m.call_count == 3

    CORRUPT_STDERR = (
        'runc run failed: unable to start container process: error '
        'during container init: exec: "/bin/sh": stat /bin/sh: '
        "no such file or directory"
    )

    def test_build_image_self_heals_on_transient_corruption(self, backend):
        corrupt = MagicMock(returncode=1, stdout="", stderr=self.CORRUPT_STDERR)
        ok = MagicMock(returncode=0, stdout="", stderr="")
        with patch.object(backend, "_run_build_cmd", side_effect=[corrupt, ok]) as m, \
                patch("stackbox.containers.docker.time.sleep"):
            backend.build_image(tag="img:local", context=".", containerfile="Cf")
            assert m.call_count == 2
            # The retry busts the cache so it doesn't remount the poisoned layer.
            assert "--no-cache" in m.call_args_list[1][0][0]

    def test_build_image_raises_fix_hint_when_corruption_persists(self, backend):
        corrupt = MagicMock(returncode=1, stdout="", stderr=self.CORRUPT_STDERR)
        with patch.object(backend, "_run_build_cmd", return_value=corrupt) as m, \
                patch("stackbox.containers.docker.time.sleep"):
            with pytest.raises(ContainerError, match="containerd-snapshotter"):
                backend.build_image(tag="img:local", context=".", containerfile="Cf")
            assert m.call_count == 3

    def test_build_image_does_not_retry_other_errors(self, backend):
        failed = MagicMock(
            returncode=1, stdout="", stderr="Containerfile syntax error",
        )
        with patch.object(backend, "_run_build_cmd", return_value=failed) as m:
            with pytest.raises(ContainerError):
                backend.build_image(tag="img:local", context=".", containerfile="Cf")
            m.assert_called_once()

    def test_cancel_build_sigint_releases_cleanly(self, backend):
        proc = MagicMock()
        proc.communicate.return_value = ("", "cancelled")
        out, err = backend._cancel_build(proc)
        proc.send_signal.assert_called_once_with(signal.SIGINT)
        assert err == "cancelled"

    def test_cancel_build_escalates_to_kill(self, backend):
        proc = MagicMock()
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="docker", timeout=15),
            subprocess.TimeoutExpired(cmd="docker", timeout=15),
            ("", ""),
        ]
        backend._cancel_build(proc)
        sent = [c.args[0] for c in proc.send_signal.call_args_list]
        assert sent == [signal.SIGINT, signal.SIGTERM, signal.SIGKILL]

    def test_run_build_cmd_cancels_on_timeout(self, backend):
        proc = MagicMock()
        proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="docker", timeout=1800
        )
        with patch("subprocess.Popen", return_value=proc), \
                patch.object(backend, "_cancel_build", return_value=("", "x")) as cancel:
            with pytest.raises(ContainerError, match="timed out"):
                backend._run_build_cmd(["docker", "build", "."], timeout=1800)
            cancel.assert_called_once_with(proc)
