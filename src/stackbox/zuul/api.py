from __future__ import annotations

from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from stackbox.constants import ZUUL_API_BASE, ZUUL_TENANT
from stackbox.exceptions import ZuulAPIError


class ZuulClient:
    def __init__(
        self,
        base_url: str = ZUUL_API_BASE,
        tenant: str = ZUUL_TENANT,
    ):
        self.base_url = base_url
        self.tenant = tenant
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{self.base_url}/{path}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise ZuulAPIError(f"Zuul API request failed: {exc}") from exc
        except ValueError as exc:
            raise ZuulAPIError(f"Invalid JSON in Zuul API response: {exc}") from exc

    def freeze_job(
        self,
        pipeline: str,
        project: str,
        branch: str,
        job: str,
    ) -> dict:
        encoded_project = quote(project, safe="")
        encoded_branch = quote(branch, safe="")
        path = (
            f"tenant/{self.tenant}/pipeline/{pipeline}"
            f"/project/{encoded_project}/branch/{encoded_branch}"
            f"/freeze-job/{job}"
        )
        return self._get(path)

    def get_build(self, build_uuid: str) -> dict:
        return self._get(f"tenant/{self.tenant}/build/{build_uuid}")

    def list_jobs(
        self,
        project: str,
        pipeline: str | None = None,
    ) -> list[dict]:
        encoded_project = quote(project, safe="")
        data = self._get(f"tenant/{self.tenant}/project/{encoded_project}")

        jobs = []
        for config in data.get("configs", []):
            for pipe in config.get("pipelines", []):
                if pipeline and pipe.get("name") != pipeline:
                    continue
                for job_group in pipe.get("jobs", []):
                    for job in job_group:
                        jobs.append({
                            "name": job.get("name", ""),
                            "voting": job.get("voting", True),
                            "pipeline": pipe.get("name", ""),
                        })
        return jobs
