from enum import Enum

from pydantic import BaseModel


class BMCType(str, Enum):
    REDFISH = "redfish"
    IPMI = "ipmi"


class BMCConfig(BaseModel):
    type: BMCType
    address: str = "localhost"
    port: int = 9132
    username: str = "admin"
    password: str = "password"


class VirtualBMNode(BaseModel):
    name: str
    uuid: str | None = None
    ram_mb: int = 3072
    vcpus: int = 1
    disk_gb: int = 10
    mac_address: str | None = None
    bmc: BMCConfig = BMCConfig(type=BMCType.REDFISH)
    firmware: str = "uefi"
    boot_mode: str = "redfish-virtual-media"
