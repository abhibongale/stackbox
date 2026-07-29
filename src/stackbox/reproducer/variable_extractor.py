from __future__ import annotations

import re

from stackbox.models.job_config import ResolvedJobConfig
from stackbox.zuul.freeze import build_resolved_config, coerce_localrc, coerce_services

_JINJA2_RE = re.compile(r"\{\{.*?\}\}")


def _has_unresolvable_template(value: str) -> bool:
    return bool(_JINJA2_RE.search(value))


class VariableExtractor:
    def extract(
        self,
        hostvars: dict,
        job_name: str = "",
        project: str = "",
        branch: str = "",
        pipeline: str = "",
    ) -> ResolvedJobConfig:
        zuul_meta = hostvars.get("zuul", {})
        if not job_name:
            job_name = zuul_meta.get("job", "unknown")
        if not project:
            project_info = zuul_meta.get("project", {})
            project = project_info.get("canonical_name", "openstack/ironic")
            if "/" in project and project.count("/") > 1:
                parts = project.split("/")
                project = "/".join(parts[-2:])
        if not branch:
            branch = zuul_meta.get("branch", "master")
        if not pipeline:
            pipeline = zuul_meta.get("pipeline", "gate")

        raw_localrc = hostvars.get("devstack_localrc", {})
        localrc = coerce_localrc(raw_localrc)

        cleaned_localrc = {}
        for key, value in localrc.items():
            if _has_unresolvable_template(value):
                continue
            cleaned_localrc[key] = value

        raw_services = hostvars.get("devstack_services", {})
        services = coerce_services(raw_services)

        local_conf = hostvars.get("devstack_local_conf", {})
        tempest_regex = str(hostvars.get("tempest_test_regex", ""))

        return build_resolved_config(
            job_name=job_name,
            localrc=cleaned_localrc,
            services=services,
            local_conf=local_conf,
            tempest_regex=tempest_regex,
            project=project,
            branch=branch,
            pipeline=pipeline,
        )
