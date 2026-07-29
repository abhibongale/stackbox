from __future__ import annotations

import re

from stackbox.exceptions import JobResolutionError
from stackbox.models.zuul import BuildInfo
from stackbox.zuul.api import ZuulClient

_BUILD_UUID_RE = re.compile(r"[/:]build[/:]([0-9a-f]{32})")
_RAW_UUID_RE = re.compile(r"^[0-9a-f]{32}$")


class BuildFetcher:
    def __init__(self, client: ZuulClient):
        self.client = client

    def fetch(self, build_url: str) -> BuildInfo:
        uuid = self._parse_uuid(build_url)
        data = self.client.get_build(uuid)

        ref_data = data.get("ref") or {}

        return BuildInfo(
            uuid=data["uuid"],
            job_name=data["job_name"],
            project=ref_data.get("project", ""),
            branch=ref_data.get("branch", ""),
            ref=ref_data.get("ref", ""),
            log_url=data.get("log_url", ""),
            result=data.get("result", ""),
            pipeline=data.get("pipeline", ""),
        )

    def _parse_uuid(self, build_url: str) -> str:
        if _RAW_UUID_RE.match(build_url):
            return build_url

        match = _BUILD_UUID_RE.search(build_url)
        if match:
            return match.group(1)

        raise JobResolutionError(
            f"Could not extract build UUID from: {build_url}"
        )
