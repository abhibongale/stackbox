import yaml
from pathlib import Path

import pytest

from stackbox.reproducer.inventory_parser import InventoryParser
from stackbox.reproducer.variable_extractor import VariableExtractor

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def inventory_hostvars():
    inventory = yaml.safe_load((FIXTURES_DIR / "inventory.yaml").read_text())
    parser = InventoryParser()
    return parser.extract_hostvars(inventory)


class TestVariableExtractor:
    def test_strips_zuul_vars(self, inventory_hostvars):
        extractor = VariableExtractor()
        config = extractor.extract(inventory_hostvars)
        assert "ansible_host" not in config.devstack_localrc
        assert "ansible_port" not in config.devstack_localrc

    def test_preserves_devstack_vars(self, inventory_hostvars):
        extractor = VariableExtractor()
        config = extractor.extract(inventory_hostvars)
        assert len(config.devstack_localrc) > 0
        assert "IRONIC_ENABLED_HARDWARE_TYPES" in config.devstack_localrc

    def test_preserves_services(self, inventory_hostvars):
        extractor = VariableExtractor()
        config = extractor.extract(inventory_hostvars)
        assert config.devstack_services["s-proxy"] is True

    def test_strips_jinja2_templates(self, inventory_hostvars):
        extractor = VariableExtractor()
        config = extractor.extract(inventory_hostvars)
        for key, value in config.devstack_localrc.items():
            assert "{{" not in value, f"{key} still has Jinja2 template: {value}"

    def test_extracts_job_name_from_zuul_var(self, inventory_hostvars):
        extractor = VariableExtractor()
        config = extractor.extract(inventory_hostvars)
        assert config.job_name == "ironic-tempest-uefi-redfish-vmedia"

    def test_extracts_branch_from_zuul_var(self, inventory_hostvars):
        extractor = VariableExtractor()
        config = extractor.extract(inventory_hostvars)
        assert config.branch == "master"

    def test_extracts_pipeline_from_zuul_var(self, inventory_hostvars):
        extractor = VariableExtractor()
        config = extractor.extract(inventory_hostvars)
        assert config.pipeline == "gate"

    def test_explicit_job_name_overrides(self, inventory_hostvars):
        extractor = VariableExtractor()
        config = extractor.extract(inventory_hostvars, job_name="custom-job")
        assert config.job_name == "custom-job"

    def test_merges_group_and_host_vars(self):
        hostvars = {
            "devstack_localrc": {"FROM_HOST": "host_val", "SHARED": "host_wins"},
            "devstack_services": {"svc1": True},
            "zuul": {"job": "test-job", "branch": "main", "pipeline": "check"},
        }
        extractor = VariableExtractor()
        config = extractor.extract(hostvars)
        assert config.devstack_localrc["FROM_HOST"] == "host_val"
        assert config.job_name == "test-job"

    def test_coerces_localrc_to_strings(self, inventory_hostvars):
        extractor = VariableExtractor()
        config = extractor.extract(inventory_hostvars)
        for key, value in config.devstack_localrc.items():
            assert isinstance(value, str), f"{key} is {type(value)}, expected str"
