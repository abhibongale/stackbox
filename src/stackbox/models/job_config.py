from pydantic import BaseModel


class VMSpecs(BaseModel):
    count: int = 1
    ram_mb: int = 3072
    cpu: int = 1
    disk_gb: int = 10
    ephemeral_gb: int = 0


class ResolvedJobConfig(BaseModel):
    job_name: str
    project: str = "openstack/ironic"
    branch: str = "master"
    pipeline: str = "gate"

    devstack_localrc: dict[str, str] = {}
    devstack_local_conf: dict[str, dict] = {}
    devstack_services: dict[str, bool] = {}
    tempest_test_regex: str = ""

    vm_specs: VMSpecs = VMSpecs()
    boot_interface: str = "redfish-virtual-media"
    bmc_driver: str = "redfish"
    hardware_types: list[str] = ["redfish"]

    local_repos: dict[str, str] = {}
    port_offset: int = 0
