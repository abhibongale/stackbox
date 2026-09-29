from pydantic import BaseModel


class VolumeMount(BaseModel):
    source: str
    target: str
    options: str = "z"


class HealthCheck(BaseModel):
    type: str  # "tcp", "http", "exec"
    target: str
    interval_seconds: int = 5
    timeout_seconds: int = 60


class ContainerSpec(BaseModel):
    name: str
    image: str
    network: str = "host"
    privileged: bool = False
    pid_mode: str | None = None
    user: str | None = None
    volumes: list[VolumeMount] = []
    environment: dict[str, str] = {}
    command: list[str] | None = None
    entrypoint: list[str] | None = None
    health_check: HealthCheck | None = None
    security_opts: list[str] = []
    # Docker restart policy (e.g. "on-failure:5"). Used for the OVS containers so
    # a vswitchd crash self-heals instead of silently killing the dataplane.
    restart_policy: str | None = None
    extra_args: list[str] = []
