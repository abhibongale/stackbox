from unittest.mock import MagicMock, call

import pytest

from stackbox.containers.images import ImageManager
from stackbox.constants import KOLLA_REGISTRY, METAL3_REGISTRY


@pytest.fixture
def img_mgr():
    backend = MagicMock()
    return ImageManager(backend=backend, release="2025.1-ubuntu-noble")


class TestImageManager:

    def test_kolla_image_known(self, img_mgr):
        result = img_mgr.kolla_image("keystone")
        assert result == f"{KOLLA_REGISTRY}/keystone:2025.1-ubuntu-noble"

    def test_kolla_image_nova_compute(self, img_mgr):
        result = img_mgr.kolla_image("nova-compute")
        assert result == f"{KOLLA_REGISTRY}/nova-compute-ironic:2025.1-ubuntu-noble"

    def test_kolla_image_unknown_fallback(self, img_mgr):
        result = img_mgr.kolla_image("unknown-service")
        assert result == f"{KOLLA_REGISTRY}/unknown-service:2025.1-ubuntu-noble"

    def test_metal3_image(self, img_mgr):
        result = img_mgr.metal3_image("sushy-tools")
        assert result == f"{METAL3_REGISTRY}/sushy-tools:latest"

    def test_pull_kolla(self, img_mgr):
        img_mgr.pull_kolla(["keystone", "glance-api"])
        assert img_mgr.backend.pull_image.call_count == 2
        img_mgr.backend.pull_image.assert_any_call(
            f"{KOLLA_REGISTRY}/keystone:2025.1-ubuntu-noble"
        )
        img_mgr.backend.pull_image.assert_any_call(
            f"{KOLLA_REGISTRY}/glance-api:2025.1-ubuntu-noble"
        )

    def test_pull_metal3(self, img_mgr):
        img_mgr.pull_metal3(["sushy-tools"])
        img_mgr.backend.pull_image.assert_called_once_with(
            f"{METAL3_REGISTRY}/sushy-tools:latest"
        )

    def test_build_local_returns_tag(self, img_mgr):
        tag = img_mgr.build_local("ironic-api", "/src/ironic", "Containerfile.service-dev")
        assert tag == "stackbox-ironic-api:local"
        img_mgr.backend.build_image.assert_called_once_with(
            tag="stackbox-ironic-api:local",
            context="/src/ironic",
            containerfile="Containerfile.service-dev",
            build_args={"SERVICE_NAME": "ironic-api"},
        )

    def test_build_tempest_no_plugin(self, img_mgr):
        tag = img_mgr.build_tempest("/ctx", "Containerfile.tempest")
        assert tag == "localhost/stackbox-tempest:local"
        img_mgr.backend.build_image.assert_called_once_with(
            tag="localhost/stackbox-tempest:local",
            context="/ctx",
            containerfile="Containerfile.tempest",
            build_args={},
        )

    def test_build_tempest_with_plugin(self, img_mgr):
        tag = img_mgr.build_tempest("/ctx", "Containerfile.tempest", plugin_source="/src/ironic-tempest-plugin")
        img_mgr.backend.build_image.assert_called_once_with(
            tag="localhost/stackbox-tempest:local",
            context="/ctx",
            containerfile="Containerfile.tempest",
            build_args={"TEMPEST_PLUGIN_SOURCE": "/src/ironic-tempest-plugin"},
        )

    def test_build_local_repos_returns_overrides(self, img_mgr):
        overrides = img_mgr.build_local_repos({"ironic-api": "/src/ironic", "nova-api": "/src/nova"})
        assert overrides == {
            "ironic-api": "stackbox-ironic-api:local",
            "nova-api": "stackbox-nova-api:local",
        }
        assert img_mgr.backend.build_image.call_count == 2

    def test_build_local_repos_empty(self, img_mgr):
        overrides = img_mgr.build_local_repos({})
        assert overrides == {}
        img_mgr.backend.build_image.assert_not_called()

    def test_build_local_repos_raises_image_build_error(self, img_mgr):
        from stackbox.exceptions import ImageBuildError

        img_mgr.backend.build_image.side_effect = RuntimeError("build failed")
        with pytest.raises(ImageBuildError, match="Failed to build ironic-api"):
            img_mgr.build_local_repos({"ironic-api": "/src/ironic"})
