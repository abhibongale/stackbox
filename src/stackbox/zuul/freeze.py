from __future__ import annotations

from stackbox.exceptions import JobResolutionError, ZuulAPIError
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


def _hardware_types_raw(localrc: dict[str, str]) -> str:
    """The job's hardware type(s), as a comma-separated string.

    IRONIC_ENABLED_HARDWARE_TYPES is only set by some jobs; when absent devstack
    derives it from IRONIC_DEPLOY_DRIVER (which is always set — e.g. 'ipmi',
    'redfish'). Reading only IRONIC_ENABLED_HARDWARE_TYPES made every IPMI job
    fall back to the 'redfish' default, so stackbox planned sushy-tools instead
    of vbmc and could not control the nodes.
    """
    return (
        localrc.get("IRONIC_ENABLED_HARDWARE_TYPES")
        or localrc.get("IRONIC_DEPLOY_DRIVER")
        or "redfish"
    )


def detect_bmc_driver(localrc: dict[str, str]) -> str:
    hw_types = _hardware_types_raw(localrc)
    if "ipmi" in hw_types:
        return "ipmi"
    return "redfish"


def _ipxe_enabled(localrc: dict[str, str]) -> bool:
    # devstack-plugin-ironic defaults IRONIC_IPXE_ENABLED to True.
    raw = str(localrc.get("IRONIC_IPXE_ENABLED", "True")).strip().lower()
    return raw not in ("false", "0", "no", "")


def detect_boot_interface(localrc: dict[str, str]) -> str:
    explicit = localrc.get("IRONIC_ENABLED_BOOT_INTERFACES")
    if explicit:
        return explicit.split(",")[0].strip()

    # Not pinned by the job: devstack derives the boot interface from the driver.
    # redfish uses virtual media; ipmi (and other PXE-based types) boot over the
    # network — iPXE unless explicitly disabled. Getting this right is what tells
    # required_containers() to add the TFTP/ironic-pxe container for IPMI jobs.
    if detect_bmc_driver(localrc) == "redfish":
        return "redfish-virtual-media"
    return "ipxe" if _ipxe_enabled(localrc) else "pxe"


def detect_boot_mode(localrc: dict[str, str]) -> str:
    """Resolve the VM firmware / Ironic boot mode (uefi or bios)."""
    raw = localrc.get("IRONIC_BOOT_MODE", "uefi").strip().lower()
    return "bios" if raw == "bios" else "uefi"


def detect_hardware_types(localrc: dict[str, str]) -> list[str]:
    raw = _hardware_types_raw(localrc)
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
        boot_mode=detect_boot_mode(localrc),
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
        try:
            raw = self.client.freeze_job(pipeline, project, branch, job_name)
        except ZuulAPIError as exc:
            if "404" in str(exc):
                raise JobResolutionError(
                    f"Job '{job_name}' is not defined for {project} on "
                    f"pipeline '{pipeline}', branch '{branch}'. "
                    f"It may only exist on another branch or pipeline "
                    f"(run 'stackbox list --project {project}' to check "
                    f"branch/pipeline scoping)."
                ) from exc
            raise

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
