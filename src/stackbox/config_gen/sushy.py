from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator


class SushyConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        lr = self.job.devstack_localrc
        feature_set = lr.get("IRONIC_REDFISH_EMULATOR_FEATURE_SET", "vmedia")
        port = self.ports.get("sushy-tools")

        content = f"""\
SUSHY_EMULATOR_LISTEN_IP = u''
SUSHY_EMULATOR_LISTEN_PORT = {port}
SUSHY_EMULATOR_LIBVIRT_URI = u'qemu:///system'
SUSHY_EMULATOR_FEATURE_SET = "{feature_set}"
SUSHY_EMULATOR_BOOT_LOADER_MAP = {{
    'UEFI': {{'x86_64': '/usr/share/OVMF/OVMF_CODE.fd'}},
    'Legacy': {{'x86_64': None}}
}}
SUSHY_EMULATOR_VMEDIA_VERIFY_SSL = False
"""
        return {"emulator.conf": content}
