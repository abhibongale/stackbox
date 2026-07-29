from unittest.mock import MagicMock, patch

import pytest
import requests

from stackbox.exceptions import ZuulAPIError
from stackbox.zuul.api import ZuulClient


@pytest.fixture
def client():
    return ZuulClient(base_url="https://zuul.example.com/api", tenant="test")


class TestZuulClient:
    def test_freeze_job_url_encoding(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"vars": {}}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            client.freeze_job("gate", "openstack/ironic", "master", "test-job")
            url = mock_get.call_args[0][0]
            assert "openstack%2Fironic" in url
            assert "openstack/ironic" not in url.split("/project/")[1].split("/branch/")[0]

    def test_freeze_job_success(self, client):
        expected = {"vars": {"devstack_localrc": {"A": "1"}}}
        mock_resp = MagicMock()
        mock_resp.json.return_value = expected
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.freeze_job("gate", "openstack/ironic", "master", "test-job")
            assert result == expected

    def test_freeze_job_api_error(self, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        with patch.object(client.session, "get", return_value=mock_resp):
            with pytest.raises(ZuulAPIError, match="Zuul API request failed"):
                client.freeze_job("gate", "openstack/ironic", "master", "nonexistent")

    def test_get_build_success(self, client):
        expected = {"uuid": "abc123", "job_name": "test"}
        mock_resp = MagicMock()
        mock_resp.json.return_value = expected
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.get_build("abc123")
            assert result["uuid"] == "abc123"

    def test_list_jobs_filters_pipeline(self, client):
        project_data = {
            "configs": [{
                "pipelines": [
                    {
                        "name": "gate",
                        "jobs": [[{"name": "gate-job", "voting": True}]],
                    },
                    {
                        "name": "check",
                        "jobs": [[{"name": "check-job", "voting": False}]],
                    },
                ],
            }],
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = project_data
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp):
            gate_jobs = client.list_jobs("openstack/ironic", pipeline="gate")
            assert len(gate_jobs) == 1
            assert gate_jobs[0]["name"] == "gate-job"

    def test_list_jobs_all_pipelines(self, client):
        project_data = {
            "configs": [{
                "pipelines": [
                    {"name": "gate", "jobs": [[{"name": "j1", "voting": True}]]},
                    {"name": "check", "jobs": [[{"name": "j2", "voting": False}]]},
                ],
            }],
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = project_data
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp):
            all_jobs = client.list_jobs("openstack/ironic")
            assert len(all_jobs) == 2
