from pydantic import BaseModel


class ZuulJobVariable(BaseModel):
    devstack_localrc: dict[str, str] = {}
    devstack_local_conf: dict[str, dict] = {}
    devstack_services: dict[str, bool] = {}
    tempest_test_regex: str = ""


class ZuulJobDefinition(BaseModel):
    name: str
    parent: str | None = None
    branches: list[str] = []
    variables: ZuulJobVariable = ZuulJobVariable()
    playbooks: list[dict] = []
    nodeset: dict | None = None
    voting: bool = True


class BuildInfo(BaseModel):
    uuid: str
    job_name: str
    project: str
    branch: str
    ref: str
    log_url: str
    result: str
    pipeline: str = ""
