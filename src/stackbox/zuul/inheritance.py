from __future__ import annotations

from stackbox.exceptions import JobResolutionError
from stackbox.models.zuul import ZuulJobDefinition, ZuulJobVariable


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def resolve_chain(
    job_name: str,
    job_registry: dict[str, ZuulJobDefinition],
) -> list[str]:
    chain: list[str] = []
    visited: set[str] = set()
    current: str | None = job_name

    while current is not None:
        if current in visited:
            raise JobResolutionError(
                f"Cycle detected in job inheritance: {' -> '.join(chain)} -> {current}"
            )
        if current not in job_registry:
            if chain:
                raise JobResolutionError(
                    f"Parent job '{current}' not found "
                    f"(referenced by '{chain[-1]}')"
                )
            raise JobResolutionError(f"Job '{current}' not found in registry")

        visited.add(current)
        chain.append(current)
        current = job_registry[current].parent

    chain.reverse()
    return chain


def merge_variables(
    chain: list[ZuulJobDefinition],
) -> ZuulJobVariable:
    merged_localrc: dict[str, str] = {}
    merged_local_conf: dict[str, dict] = {}
    merged_services: dict[str, bool] = {}
    merged_regex = ""

    for job in chain:
        v = job.variables
        merged_localrc = deep_merge(merged_localrc, v.devstack_localrc)
        merged_local_conf = deep_merge(merged_local_conf, v.devstack_local_conf)
        merged_services = deep_merge(merged_services, v.devstack_services)
        if v.tempest_test_regex:
            merged_regex = v.tempest_test_regex

    return ZuulJobVariable(
        devstack_localrc=merged_localrc,
        devstack_local_conf=merged_local_conf,
        devstack_services=merged_services,
        tempest_test_regex=merged_regex,
    )
