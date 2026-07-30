from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from stackbox.bootstrap.orchestrator import BootstrapOrchestrator
from stackbox.containers.manifest import SessionManifest
from stackbox.models.job_config import ResolvedJobConfig


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.run.return_value = "container-id-123"
    backend.is_running.return_value = False
    backend.exec.return_value = (0, "OK")
    return backend


@pytest.fixture
def job():
    return ResolvedJobConfig(
        job_name="test-job",
        boot_interface="redfish-virtual-media",
        bmc_driver="redfish",
        devstack_localrc={"ADMIN_PASSWORD": "testpass"},
    )


@pytest.fixture
def manifest(tmp_path):
    return SessionManifest(session_id="test-session", configs_dir=str(tmp_path / "configs"))


class TestBootstrapOrchestrator:

    def test_init_sets_admin_pass_from_localrc(self, mock_backend, job, manifest, tmp_path):
        orch = BootstrapOrchestrator(mock_backend, job, tmp_path, manifest)
        assert orch.admin_pass == "testpass"

    def test_init_default_admin_pass(self, mock_backend, manifest, tmp_path):
        job = ResolvedJobConfig(job_name="test", devstack_localrc={})
        orch = BootstrapOrchestrator(mock_backend, job, tmp_path, manifest)
        assert orch.admin_pass == "secretadmin"

    def test_create_volumes(self, mock_backend, job, manifest, tmp_path):
        orch = BootstrapOrchestrator(mock_backend, job, tmp_path, manifest)
        orch._create_volumes()
        assert mock_backend.create_volume.call_count == 4
        assert len(manifest.volumes) == 4

    @patch("stackbox.bootstrap.orchestrator.init_database")
    @patch("stackbox.bootstrap.orchestrator.check")
    def test_start_infrastructure(self, mock_check, mock_init_db, mock_backend, job, manifest, tmp_path):
        orch = BootstrapOrchestrator(mock_backend, job, tmp_path, manifest)
        orch._start_infrastructure()
        assert mock_backend.run.call_count >= 4
        assert "stackbox-mariadb" in manifest.containers
        assert "stackbox-keystone" in manifest.containers

    @patch("stackbox.bootstrap.orchestrator.enroll_nodes")
    @patch("stackbox.bootstrap.orchestrator.wait_for_bmc")
    @patch("stackbox.bootstrap.orchestrator.LibvirtManager")
    @patch("stackbox.bootstrap.orchestrator.setup_resources")
    @patch("stackbox.bootstrap.orchestrator.create_networks")
    @patch("stackbox.bootstrap.orchestrator.setup_ovs_bridges")
    @patch("stackbox.bootstrap.orchestrator.start_services")
    @patch("stackbox.bootstrap.orchestrator.run_dbsync")
    @patch("stackbox.bootstrap.orchestrator.register_services")
    @patch("stackbox.bootstrap.orchestrator.bootstrap_keystone")
    @patch("stackbox.bootstrap.orchestrator.init_database")
    @patch("stackbox.bootstrap.orchestrator.check")
    def test_run_calls_all_phases(
        self, mock_check, mock_init_db, mock_ks, mock_register,
        mock_dbsync, mock_services, mock_ovs, mock_networks, mock_resources,
        mock_libvirt_cls, mock_wait_bmc, mock_enroll,
        mock_backend, job, manifest, tmp_path,
    ):
        mock_libvirt = MagicMock()
        mock_libvirt.create_nodes.return_value = []
        mock_libvirt_cls.return_value = mock_libvirt

        orch = BootstrapOrchestrator(mock_backend, job, tmp_path, manifest)
        orch.run()

        mock_ks.assert_called_once()
        mock_register.assert_called_once()
        mock_dbsync.assert_called_once()
        mock_services.assert_called_once()
        mock_ovs.assert_called_once()
        mock_networks.assert_called_once()
        mock_resources.assert_called_once()
        mock_libvirt_cls.assert_called_once()
        mock_enroll.assert_called_once()

    @patch("stackbox.bootstrap.orchestrator.init_database")
    @patch("stackbox.bootstrap.orchestrator.check")
    def test_start_dbsync_containers(self, mock_check, mock_init_db, mock_backend, job, manifest, tmp_path):
        orch = BootstrapOrchestrator(mock_backend, job, tmp_path, manifest)
        orch._start_infrastructure()
        mock_backend.run.reset_mock()

        orch._start_dbsync_containers()
        started = [c[0][0].name for c in mock_backend.run.call_args_list]
        assert "stackbox-glance-api" in started
        assert "stackbox-neutron-server" in started
        assert "stackbox-ironic-api" in started
