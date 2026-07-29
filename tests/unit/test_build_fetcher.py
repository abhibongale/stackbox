import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stackbox.exceptions import JobResolutionError
from stackbox.reproducer.build_fetcher import BuildFetcher

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def build_fixture():
    return json.loads((FIXTURES_DIR / "build-vmedia.json").read_text())


@pytest.fixture
def mock_client(build_fixture):
    client = MagicMock()
    client.get_build.return_value = build_fixture
    return client


class TestBuildFetcher:
    def test_fetch_from_full_url(self, mock_client, build_fixture):
        fetcher = BuildFetcher(mock_client)
        uuid = build_fixture["uuid"]
        url = f"https://zuul.opendev.org/t/openstack/build/{uuid}"
        info = fetcher.fetch(url)

        assert info.uuid == uuid
        assert info.job_name == "ironic-tempest-uefi-redfish-vmedia"
        assert info.pipeline == "gate"

    def test_fetch_from_raw_uuid(self, mock_client, build_fixture):
        fetcher = BuildFetcher(mock_client)
        uuid = build_fixture["uuid"]
        info = fetcher.fetch(uuid)
        assert info.uuid == uuid

    def test_fetch_extracts_ref_fields(self, mock_client, build_fixture):
        fetcher = BuildFetcher(mock_client)
        info = fetcher.fetch(build_fixture["uuid"])

        ref_data = build_fixture["ref"]
        assert info.project == ref_data["project"]
        assert info.branch == ref_data["branch"]
        assert info.ref == ref_data["ref"]

    def test_fetch_invalid_url(self, mock_client):
        fetcher = BuildFetcher(mock_client)
        with pytest.raises(JobResolutionError, match="Could not extract build UUID"):
            fetcher.fetch("https://zuul.opendev.org/t/openstack/builds")

    def test_fetch_invalid_short_string(self, mock_client):
        fetcher = BuildFetcher(mock_client)
        with pytest.raises(JobResolutionError, match="Could not extract build UUID"):
            fetcher.fetch("not-a-uuid")

    def test_build_info_has_log_url(self, mock_client, build_fixture):
        fetcher = BuildFetcher(mock_client)
        info = fetcher.fetch(build_fixture["uuid"])
        assert info.log_url == build_fixture["log_url"]
