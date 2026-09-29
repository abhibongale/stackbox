import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stackbox.zuul.freeze import (
    FreezeJobResolver,
    coerce_localrc,
    detect_bmc_driver,
    detect_boot_interface,
    detect_boot_mode,
    detect_hardware_types,
    extract_vm_specs,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def vmedia_fixture():
    return json.loads((FIXTURES_DIR / "frozen-job-vmedia.json").read_text())


@pytest.fixture
def mock_client(vmedia_fixture):
    client = MagicMock()
    client.freeze_job.return_value = vmedia_fixture
    return client


class TestHelpers:
    def test_coerce_localrc_mixed_types(self):
        raw = {"STR": "hello", "BOOL": True, "INT": 42, "BOOL_F": False}
        result = coerce_localrc(raw)
        assert result == {"STR": "hello", "BOOL": "True", "INT": "42", "BOOL_F": "False"}

    def test_extract_vm_specs_from_localrc(self):
        localrc = {
            "IRONIC_VM_COUNT": "2",
            "IRONIC_VM_SPECS_RAM": "4096",
            "IRONIC_VM_SPECS_CPU": "2",
            "IRONIC_VM_SPECS_DISK": "20",
        }
        specs = extract_vm_specs(localrc)
        assert specs.count == 2
        assert specs.ram_mb == 4096
        assert specs.cpu == 2
        assert specs.disk_gb == 20
        assert specs.ephemeral_gb == 0

    def test_extract_vm_specs_defaults(self):
        specs = extract_vm_specs({})
        assert specs.count == 1
        assert specs.ram_mb == 3072

    def test_detect_bmc_driver_redfish(self):
        assert detect_bmc_driver({"IRONIC_ENABLED_HARDWARE_TYPES": "redfish"}) == "redfish"

    def test_detect_bmc_driver_ipmi(self):
        assert detect_bmc_driver({"IRONIC_ENABLED_HARDWARE_TYPES": "ipmi"}) == "ipmi"

    def test_detect_bmc_driver_mixed(self):
        assert detect_bmc_driver({"IRONIC_ENABLED_HARDWARE_TYPES": "redfish,ipmi"}) == "ipmi"

    def test_detect_bmc_driver_default(self):
        assert detect_bmc_driver({}) == "redfish"

    def test_detect_bmc_driver_falls_back_to_deploy_driver(self):
        # IPMI jobs often omit IRONIC_ENABLED_HARDWARE_TYPES and only set
        # IRONIC_DEPLOY_DRIVER; detection must not default such jobs to redfish.
        assert detect_bmc_driver({"IRONIC_DEPLOY_DRIVER": "ipmi"}) == "ipmi"
        assert detect_bmc_driver({"IRONIC_DEPLOY_DRIVER": "redfish"}) == "redfish"

    def test_detect_bmc_driver_prefers_hardware_types_over_deploy_driver(self):
        localrc = {"IRONIC_ENABLED_HARDWARE_TYPES": "ipmi", "IRONIC_DEPLOY_DRIVER": "redfish"}
        assert detect_bmc_driver(localrc) == "ipmi"

    def test_detect_boot_interface(self):
        localrc = {"IRONIC_ENABLED_BOOT_INTERFACES": "redfish-virtual-media,pxe"}
        assert detect_boot_interface(localrc) == "redfish-virtual-media"

    def test_detect_boot_interface_default(self):
        assert detect_boot_interface({}) == "redfish-virtual-media"

    def test_detect_boot_interface_ipmi_defaults_to_ipxe(self):
        # No explicit boot interface + ipmi driver -> network boot (iPXE default).
        assert detect_boot_interface({"IRONIC_DEPLOY_DRIVER": "ipmi"}) == "ipxe"

    def test_detect_boot_interface_ipmi_pxe_when_ipxe_disabled(self):
        localrc = {"IRONIC_DEPLOY_DRIVER": "ipmi", "IRONIC_IPXE_ENABLED": "False"}
        assert detect_boot_interface(localrc) == "pxe"

    def test_detect_boot_interface_explicit_wins(self):
        localrc = {"IRONIC_DEPLOY_DRIVER": "ipmi", "IRONIC_ENABLED_BOOT_INTERFACES": "pxe"}
        assert detect_boot_interface(localrc) == "pxe"

    def test_detect_hardware_types_falls_back_to_deploy_driver(self):
        assert detect_hardware_types({"IRONIC_DEPLOY_DRIVER": "ipmi"}) == ["ipmi"]

    def test_detect_boot_mode_bios(self):
        assert detect_boot_mode({"IRONIC_BOOT_MODE": "bios"}) == "bios"

    def test_detect_boot_mode_uefi(self):
        assert detect_boot_mode({"IRONIC_BOOT_MODE": "uefi"}) == "uefi"

    def test_detect_boot_mode_default(self):
        assert detect_boot_mode({}) == "uefi"

    def test_detect_hardware_types_single(self):
        assert detect_hardware_types({"IRONIC_ENABLED_HARDWARE_TYPES": "redfish"}) == ["redfish"]

    def test_detect_hardware_types_multiple(self):
        result = detect_hardware_types({"IRONIC_ENABLED_HARDWARE_TYPES": "redfish, ipmi"})
        assert result == ["redfish", "ipmi"]


class TestFreezeJobResolver:
    def test_resolve_vmedia_job(self, mock_client, vmedia_fixture):
        resolver = FreezeJobResolver(mock_client)
        config = resolver.resolve("ironic-tempest-uefi-redfish-vmedia")

        assert config.job_name == "ironic-tempest-uefi-redfish-vmedia"
        assert config.tempest_test_regex == "test_baremetal_server_ops_wholedisk_image"
        assert config.bmc_driver == "redfish"
        assert "redfish" in config.hardware_types
        assert len(config.devstack_localrc) > 0
        assert isinstance(config.devstack_services, dict)

    def test_resolve_preserves_services(self, mock_client):
        resolver = FreezeJobResolver(mock_client)
        config = resolver.resolve("ironic-tempest-uefi-redfish-vmedia")
        assert isinstance(config.devstack_services.get("s-proxy"), bool)

    def test_resolve_coerces_localrc_to_strings(self, mock_client):
        resolver = FreezeJobResolver(mock_client)
        config = resolver.resolve("ironic-tempest-uefi-redfish-vmedia")
        for key, value in config.devstack_localrc.items():
            assert isinstance(value, str), f"{key} is {type(value)}, expected str"

    def test_resolve_missing_vars_key(self):
        client = MagicMock()
        client.freeze_job.return_value = {"job": "test"}
        resolver = FreezeJobResolver(client)

        from stackbox.exceptions import JobResolutionError
        with pytest.raises(JobResolutionError, match="missing 'vars' key"):
            resolver.resolve("test-job")

    def test_resolve_404_gives_actionable_error(self):
        from stackbox.exceptions import JobResolutionError, ZuulAPIError

        client = MagicMock()
        client.freeze_job.side_effect = ZuulAPIError(
            "Zuul API request failed: 404 Client Error: Not Found"
        )
        resolver = FreezeJobResolver(client)

        with pytest.raises(JobResolutionError, match="not defined for"):
            resolver.resolve("ironic-tempest-bios-ipmi-direct", branch="master")

    def test_resolve_non_404_reraises(self):
        from stackbox.exceptions import ZuulAPIError

        client = MagicMock()
        client.freeze_job.side_effect = ZuulAPIError(
            "Zuul API request failed: 500 Server Error"
        )
        resolver = FreezeJobResolver(client)

        with pytest.raises(ZuulAPIError, match="500"):
            resolver.resolve("test-job")
