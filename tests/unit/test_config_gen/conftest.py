import json
from pathlib import Path

import pytest

from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig
from stackbox.zuul.freeze import (
    build_resolved_config,
    coerce_localrc,
    coerce_services,
)

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture
def vmedia_job_config():
    data = json.loads((FIXTURES_DIR / "frozen-job-vmedia.json").read_text())
    job_vars = data["vars"]

    localrc = coerce_localrc(job_vars.get("devstack_localrc", {}))
    services = coerce_services(job_vars.get("devstack_services", {}))
    local_conf = job_vars.get("devstack_local_conf", {})
    tempest_regex = str(job_vars.get("tempest_test_regex", ""))

    return build_resolved_config(
        job_name="ironic-tempest-uefi-redfish-vmedia",
        localrc=localrc,
        services=services,
        local_conf=local_conf,
        tempest_regex=tempest_regex,
    )


@pytest.fixture
def port_manager():
    return PortManager(offset=0)


@pytest.fixture
def offset_port_manager():
    return PortManager(offset=10000)
