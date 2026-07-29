from __future__ import annotations

from stackbox.exceptions import JobResolutionError
from stackbox.models.job_config import ResolvedJobConfig, VMSpecs
from stackbox.zuul.api import ZuulClient


def coerce_localrc(raw: dict) -> dict[str, str]:
    return {k: str(v) for k, v in raw.items()}


def coerce_services(raw: dict) -> dict[str, bool]:
    return {k: bool(v) for k, v in raw.items()}


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def extract_vm_specs(localrc: dict[str, str]) -> VMSpecs:
    return VMSpecs(
        count=_safe_int(localrc.get("IRONIC_VM_COUNT"), 1),
        ram_mb=_safe_int(localrc.get("IRONIC_VM_SPECS_RAM"), 3072),
        cpu=_safe_int(localrc.get("IRONIC_VM_SPECS_CPU"), 1),
        disk_gb=_safe_int(localrc.get("IRONIC_VM_SPECS_DISK"), 10),
        ephemeral_gb=_safe_int(localrc.get("IRONIC_VM_EPHEMERAL_DISK"), 0),
    )


def detect_bmc_driver(localrc: dict[str, str]) -> str:
    hw_types = localrc.get("IRONIC_ENABLED_HARDWARE_TYPES", "redfish")
    if "ipmi" in hw_types:
        return "ipmi"
    return "redfish"


def detect_boot_interface(localrc: dict[str, str]) -> str:
    raw = localrc.get("IRONIC_ENABLED_BOOT_INTERFACES", "redfish-virtual-media")
    return raw.split(",")[0].strip()


def detect_hardware_types(localrc: dict[str, str]) -> list[str]:
    raw = localrc.get("IRONIC_ENABLED_HARDWARE_TYPES", "redfish")
    return [t.strip() for t in raw.split(",") if t.strip()]


def build_resolved_config(
    job_name: str,
    localrc: dict[str, str],
    services: dict[str, bool],
    local_conf: dict[str, dict],
    tempest_regex: str,
    project: str = "openstack/ironic",
    branch: str = "master",
    pipeline: str = "gate",
) -> ResolvedJobConfig:
    return ResolvedJobConfig(
        job_name=job_name,
        project=project,
        branch=branch,
        pipeline=pipeline,
        devstack_localrc=localrc,
        devstack_local_conf=local_conf,
        devstack_services=services,
        tempest_test_regex=tempest_regex,
        vm_specs=extract_vm_specs(localrc),
        boot_interface=detect_boot_interface(localrc),
        bmc_driver=detect_bmc_driver(localrc),
        hardware_types=detect_hardware_types(localrc),
    )


class FreezeJobResolver:
    def __init__(self, client: ZuulClient):
        self.client = client

    def resolve(
        self,
        job_name: str,
        project: str = "openstack/ironic",
        branch: str = "master",
        pipeline: str = "gate",
    ) -> ResolvedJobConfig:
        raw = self.client.freeze_job(pipeline, project, branch, job_name)

        job_vars = raw.get("vars")
        if job_vars is None:
            raise JobResolutionError(
                f"freeze-job response for '{job_name}' missing 'vars' key"
            )

        localrc = coerce_localrc(job_vars.get("devstack_localrc", {}))
        services = coerce_services(job_vars.get("devstack_services", {}))
        local_conf = job_vars.get("devstack_local_conf", {})
        tempest_regex = str(job_vars.get("tempest_test_regex", ""))

        return build_resolved_config(
            job_name=job_name,
            localrc=localrc,
            services=services,
            local_conf=local_conf,
            tempest_regex=tempest_regex,
            project=project,
            branch=branch,
            pipeline=pipeline,
        )
