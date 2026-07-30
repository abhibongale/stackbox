from unittest.mock import MagicMock, call

import pytest

from stackbox.containers.images import ImageManager
from stackbox.constants import KOLLA_REGISTRY, METAL3_REGISTRY


@pytest.fixture
def img_mgr():
    backend = MagicMock()
    return ImageManager(backend=backend, release="master-ubuntu-noble")


class TestImageManager:

    def test_kolla_image_known(self, img_mgr):
        result = img_mgr.kolla_image("keystone")
        assert result == f"{KOLLA_REGISTRY}/keystone:master-ubuntu-noble"

    def test_kolla_image_nova_compute(self, img_mgr):
        result = img_mgr.kolla_image("nova-compute")
        assert result == f"{KOLLA_REGISTRY}/nova-compute-ironic:master-ubuntu-noble"

    def test_kolla_image_unknown_fallback(self, img_mgr):
        result = img_mgr.kolla_image("unknown-service")
        assert result == f"{KOLLA_REGISTRY}/unknown-service:master-ubuntu-noble"

    def test_metal3_image(self, img_mgr):
        result = img_mgr.metal3_image("sushy-tools")
        assert result == f"{METAL3_REGISTRY}/sushy-tools:latest"

    def test_pull_kolla(self, img_mgr):
        img_mgr.pull_kolla(["keystone", "glance-api"])
        assert img_mgr.backend.pull_image.call_count == 2
        img_mgr.backend.pull_image.assert_any_call(
            f"{KOLLA_REGISTRY}/keystone:master-ubuntu-noble"
        )
        img_mgr.backend.pull_image.assert_any_call(
            f"{KOLLA_REGISTRY}/glance-api:master-ubuntu-noble"
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
        assert tag == "stackbox-tempest:local"
        img_mgr.backend.build_image.assert_called_once_with(
            tag="stackbox-tempest:local",
            context="/ctx",
            containerfile="Containerfile.tempest",
            build_args={},
        )

    def test_build_tempest_with_plugin(self, img_mgr):
        tag = img_mgr.build_tempest("/ctx", "Containerfile.tempest", plugin_source="/src/ironic-tempest-plugin")
        img_mgr.backend.build_image.assert_called_once_with(
            tag="stackbox-tempest:local",
            context="/ctx",
            containerfile="Containerfile.tempest",
            build_args={"TEMPEST_PLUGIN_SOURCE": "/src/ironic-tempest-plugin"},
        )
