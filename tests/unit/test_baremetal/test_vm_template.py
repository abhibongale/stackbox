import pytest

from stackbox.baremetal.vm_template import render_domain_xml
from stackbox.models.baremetal import BMCConfig, BMCType, VirtualBMNode


@pytest.fixture
def uefi_node():
    return VirtualBMNode(
        name="stackbox-bm-0",
        ram_mb=4096,
        vcpus=2,
        disk_gb=20,
        mac_address="52:54:00:aa:bb:cc",
        firmware="uefi",
    )


@pytest.fixture
def bios_node():
    return VirtualBMNode(
        name="stackbox-bm-1",
        ram_mb=2048,
        vcpus=1,
        disk_gb=10,
        firmware="bios",
    )


class TestRenderDomainXml:

    def test_contains_domain_name(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "<name>stackbox-bm-0</name>" in xml

    def test_memory_and_vcpus(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "<memory unit='MiB'>4096</memory>" in xml
        assert "<vcpu>2</vcpu>" in xml

    def test_uefi_firmware(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "firmware='efi'" in xml

    def test_bios_no_firmware(self, bios_node):
        xml = render_domain_xml(bios_node)
        assert "firmware='efi'" not in xml
        assert "<type arch='x86_64' machine='q35'>hvm</type>" in xml

    def test_disk_image_path(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "/var/lib/libvirt/images/stackbox-bm-0.qcow2" in xml

    def test_ephemeral_disk_present_when_specified(self, uefi_node):
        xml = render_domain_xml(uefi_node, ephemeral_gb=20)
        assert "stackbox-bm-0-ephemeral.qcow2" in xml

    def test_no_ephemeral_disk_by_default(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "ephemeral" not in xml

    def test_mac_address(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "52:54:00:aa:bb:cc" in xml

    def test_no_mac_when_absent(self, bios_node):
        xml = render_domain_xml(bios_node)
        assert "<mac address=" not in xml

    def test_bridge_interface(self, uefi_node):
        xml = render_domain_xml(uefi_node, bridge="brbm-link")
        assert "<interface type='bridge'>" in xml
        assert "<source bridge='brbm-link'/>" in xml

    def test_e1000_nic(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "<model type='e1000'/>" in xml

    def test_serial_console(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "<serial type='pty'>" in xml

    def test_kvm_domain_type(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "<domain type='kvm'>" in xml

    def test_cdrom_device_present(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "device='cdrom'" in xml
        assert "<target dev='sda' bus='sata'/>" in xml
        assert "<readonly/>" in xml

    def test_boot_order_includes_cdrom(self, uefi_node):
        xml = render_domain_xml(uefi_node)
        assert "<boot dev='cdrom'/>" in xml
        assert "<boot dev='network'/>" in xml
        assert "<boot dev='hd'/>" in xml
