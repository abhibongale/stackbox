from __future__ import annotations

from pathlib import Path

import yaml

from stackbox.constants import REQUIRED_REPOS
from stackbox.exceptions import JobResolutionError
from stackbox.models.job_config import ResolvedJobConfig
from stackbox.models.zuul import ZuulJobDefinition, ZuulJobVariable
from stackbox.zuul.freeze import build_resolved_config, coerce_localrc, coerce_services
from stackbox.zuul.inheritance import merge_variables, resolve_chain
from stackbox.zuul.repo_cache import RepoCache


def _parse_job_entry(entry: dict) -> ZuulJobDefinition:
    job_vars = entry.get("vars", {})
    raw_localrc = job_vars.get("devstack_localrc", {})
    raw_services = job_vars.get("devstack_services", {})

    variables = ZuulJobVariable(
        devstack_localrc=coerce_localrc(raw_localrc),
        devstack_local_conf=job_vars.get("devstack_local_conf", {}),
        devstack_services=coerce_services(raw_services),
        tempest_test_regex=str(job_vars.get("tempest_test_regex", "")),
    )

    run_playbooks = entry.get("run", [])
    if isinstance(run_playbooks, str):
        run_playbooks = [run_playbooks]

    return ZuulJobDefinition(
        name=entry["name"],
        parent=entry.get("parent"),
        branches=entry.get("branches", []),
        variables=variables,
        playbooks=[{"run": p} for p in run_playbooks],
        nodeset=entry.get("nodeset"),
        voting=entry.get("voting", True),
    )


class OfflineJobParser:
    def __init__(
        self,
        repo_cache: RepoCache,
        local_overrides: dict[str, str] | None = None,
    ):
        self.repo_cache = repo_cache
        self.local_overrides = local_overrides or {}

    def parse_jobs(self, repo_path: Path) -> dict[str, ZuulJobDefinition]:
        jobs: dict[str, ZuulJobDefinition] = {}
        yaml_files: list[Path] = []

        zuul_d = repo_path / "zuul.d"
        if zuul_d.is_dir():
            yaml_files.extend(sorted(zuul_d.glob("*.yaml")))
            yaml_files.extend(sorted(zuul_d.glob("*.yml")))

        zuul_yaml = repo_path / ".zuul.yaml"
        if zuul_yaml.is_file():
            yaml_files.append(zuul_yaml)

        for yaml_file in yaml_files:
            try:
                docs = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue
            if not isinstance(docs, list):
                continue
            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                if "job" not in doc:
                    continue
                entry = doc["job"]
                if "name" not in entry:
                    continue
                jobs[entry["name"]] = _parse_job_entry(entry)

        return jobs

    def build_registry(self) -> dict[str, ZuulJobDefinition]:
        registry: dict[str, ZuulJobDefinition] = {}

        for repo in REQUIRED_REPOS:
            if repo in self.local_overrides:
                repo_path = Path(self.local_overrides[repo])
            else:
                try:
                    repo_path = self.repo_cache.get_repo_path(repo)
                except JobResolutionError:
                    continue

            repo_jobs = self.parse_jobs(repo_path)
            registry.update(repo_jobs)

        return registry

    def resolve(
        self,
        job_name: str,
        project: str = "openstack/ironic",
        branch: str = "master",
        pipeline: str = "gate",
    ) -> ResolvedJobConfig:
        registry = self.build_registry()
        chain_names = resolve_chain(job_name, registry)
        chain_defs = [registry[name] for name in chain_names]
        merged = merge_variables(chain_defs)

        return build_resolved_config(
            job_name=job_name,
            localrc=merged.devstack_localrc,
            services=merged.devstack_services,
            local_conf=merged.devstack_local_conf,
            tempest_regex=merged.tempest_test_regex,
            project=project,
            branch=branch,
            pipeline=pipeline,
        )
