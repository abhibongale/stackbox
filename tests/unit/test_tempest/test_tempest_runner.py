from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stackbox.tempest.runner import TempestRunner


@pytest.fixture
def runner():
    backend = MagicMock()
    return TempestRunner(backend=backend)


class TestTempestRunner:

    def test_build_run_cmd_basic(self, runner, tmp_path):
        from stackbox.models.container import ContainerSpec, VolumeMount

        spec = ContainerSpec(
            name="stackbox-tempest",
            image="stackbox-tempest:local",
            volumes=[
                VolumeMount(source="/tmp/tempest.conf", target="/opt/tempest/workspace/etc/tempest.conf", options="ro,z"),
            ],
            command=["tempest", "run", "--regex", "test_.*baremetal"],
        )
        cmd = runner._build_run_cmd(spec)
        assert cmd[0] == "podman"
        assert "run" in cmd
        assert "--rm" in cmd
        assert "--name" in cmd
        assert "stackbox-tempest" in cmd
        assert "--network" in cmd
        assert "host" in cmd
        assert "stackbox-tempest:local" in cmd
        assert "tempest" in cmd
        assert "--regex" in cmd
        assert "test_.*baremetal" in cmd

    def test_build_run_cmd_volumes(self, runner):
        from stackbox.models.container import ContainerSpec, VolumeMount

        spec = ContainerSpec(
            name="stackbox-tempest",
            image="img:1",
            volumes=[
                VolumeMount(source="/a", target="/b", options="ro,z"),
                VolumeMount(source="/c", target="/d", options="z"),
            ],
        )
        cmd = runner._build_run_cmd(spec)
        assert "-v" in cmd
        vol_args = []
        for i, arg in enumerate(cmd):
            if arg == "-v":
                vol_args.append(cmd[i + 1])
        assert "/a:/b:ro,z" in vol_args
        assert "/c:/d:z" in vol_args

    @patch("subprocess.Popen")
    def test_run_returns_exit_code(self, mock_popen, runner, tmp_path):
        conf = tmp_path / "tempest.conf"
        conf.write_text("[DEFAULT]\n")
        results = tmp_path / "results"

        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        exit_code = runner.run(conf, "test_baremetal", results)
        assert exit_code == 0

    @patch("subprocess.Popen")
    def test_run_failure_returns_nonzero(self, mock_popen, runner, tmp_path):
        conf = tmp_path / "tempest.conf"
        conf.write_text("[DEFAULT]\n")
        results = tmp_path / "results"

        mock_proc = MagicMock()
        mock_proc.wait.return_value = 1
        mock_popen.return_value = mock_proc

        exit_code = runner.run(conf, "test_baremetal", results)
        assert exit_code == 1

    @patch("subprocess.Popen")
    def test_run_creates_results_dir(self, mock_popen, runner, tmp_path):
        conf = tmp_path / "tempest.conf"
        conf.write_text("[DEFAULT]\n")
        results = tmp_path / "nested" / "results"

        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        runner.run(conf, "test_baremetal", results)
        assert results.exists()

    @patch("subprocess.Popen")
    def test_run_removes_existing_container(self, mock_popen, runner, tmp_path):
        conf = tmp_path / "tempest.conf"
        conf.write_text("[DEFAULT]\n")
        results = tmp_path / "results"

        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        runner.run(conf, "test_baremetal", results)
        runner.backend.remove.assert_called_once_with("stackbox-tempest", force=True)
