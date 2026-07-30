from __future__ import annotations

from jinja2 import Template

from stackbox.models.baremetal import VirtualBMNode

DOMAIN_XML = Template("""\
<domain type='kvm'>
  <name>{{ node.name }}</name>
  <memory unit='MiB'>{{ node.ram_mb }}</memory>
  <vcpu>{{ node.vcpus }}</vcpu>
  <os{% if node.firmware == 'uefi' %} firmware='efi'{% endif %}>
    <type arch='x86_64'>hvm</type>
    <boot dev='network'/>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <cpu mode='host-passthrough'/>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='/var/lib/libvirt/images/{{ node.name }}.qcow2'/>
      <target dev='vda' bus='virtio'/>
    </disk>
{% if node.disk_gb > 0 and ephemeral_gb > 0 %}
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='/var/lib/libvirt/images/{{ node.name }}-ephemeral.qcow2'/>
      <target dev='vdb' bus='virtio'/>
    </disk>
{% endif %}
    <interface type='bridge'>
{% if node.mac_address %}
      <mac address='{{ node.mac_address }}'/>
{% endif %}
      <source bridge='brbm'/>
      <virtualport type='openvswitch'/>
      <model type='e1000'/>
    </interface>
    <serial type='pty'>
      <target port='0'/>
    </serial>
    <console type='pty'>
      <target type='serial' port='0'/>
    </console>
    <graphics type='vnc' port='-1' autoport='yes' listen='127.0.0.1'/>
  </devices>
</domain>
""")


def render_domain_xml(node: VirtualBMNode, ephemeral_gb: int = 0) -> str:
    return DOMAIN_XML.render(node=node, ephemeral_gb=ephemeral_gb)
