from pydantic import BaseModel


class SubnetConfig(BaseModel):
    name: str
    cidr: str
    gateway: str | None = None
    allocation_pool_start: str | None = None
    allocation_pool_end: str | None = None
    enable_dhcp: bool = True


class NetworkConfig(BaseModel):
    provisioning_network: str = "provisioning"
    provisioning_subnet: SubnetConfig = SubnetConfig(
        name="provisioning-subnet",
        cidr="192.168.24.0/24",
        gateway="192.168.24.1",
        allocation_pool_start="192.168.24.100",
        allocation_pool_end="192.168.24.200",
    )
    cleaning_network: str = "provisioning"
    ovs_bridge_mappings: str = "physnet1:brbm"
