# Release Notes

## 0.2.0 — Ironic Virtual Media Deploy Chain

This release completes the end-to-end Ironic virtual media deploy chain
and passes upstream `ironic_tempest_plugin` integration tests.

### Major Changes

**Podman to Docker migration** — The container backend has been switched
from Podman to Docker. Podman's rootless mode had networking limitations
that prevented reliable OVS bridge integration with containerized Neutron
agents.

**Neutron DHCP agent** — Added a containerized Neutron DHCP agent that
runs dnsmasq inside a `qdhcp-*` network namespace. This replaces the
standalone dnsmasq container for virtual media boot, ensuring that VMs
receive the exact IP address assigned by Neutron. The standalone dnsmasq
is still used for PXE/iPXE boot where Neutron port awareness is not
required.

**UEFI virtual media boot support** — The service-dev container image
now builds a GRUB EFI boot image (`efiboot.img`) for UEFI virtual media
deployments. The Ironic conductor uses this to create bootable ISO images
for the deploy ramdisk.

**Tempest container fixes** — Added `iputils-ping` and `openssh-client`
to the tempest container image, required for the connectivity validation
phase of baremetal scenario tests.

### Configuration Generation

- Neutron config now includes `[oslo_concurrency] lock_path` (required
  by iptables manager for file locking)
- Neutron privsep uses `sudo privsep-helper` with a sudoers file
  installed via Kolla's `config_files` mechanism, supporting all privsep
  contexts (default, namespace, link, dhcp_release, etc.)
- Added `dhcp_agent.ini` generation for the DHCP agent
- Tempest config sets `console_output = false` (Ironic does not support
  Nova serial console) and `run_validation = true` with explicit
  ping/SSH timeouts
- Glance config updated for file-based image storage
- Ironic config updated with virtual media and deploy settings
- Sushy-tools emulator config generation added

### Container Orchestration

- Neutron DHCP agent container runs with `--pid host` and mounts
  `/var/run/netns` for network namespace access
- All Neutron agent containers (DHCP, OVS, L3) mount a privsep sudoers
  file via Kolla `config_files` for privilege escalation
- Container specs support `pid_mode` field for PID namespace sharing
- Kolla config JSON supports `config_files` entries for copying files
  with specific ownership and permissions
- dnsmasq container is now conditional — only included for PXE/iPXE boot
- Service start order updated to include DHCP agent alongside OVS and
  L3 agents

### Bootstrap and Resources

- Full Glance image upload (cirros whole-disk image)
- Provisioning network, subnet, and router creation via Neutron API
- Baremetal flavor creation with custom resource class
- Nova host aggregate for Ironic compute nodes
- Ironic node enrollment with port creation and validation

### Baremetal

- Libvirt VM creation with UEFI firmware, virtual media support, and
  configurable resource specs (vCPUs, RAM, disk)
- VM template generates OVMF-based UEFI VMs connected to the
  provisioning bridge

### Tests

- 321 unit tests passing
- Integration test for end-to-end config generation
- Tests cover DHCP agent config, sudoers generation, PID mode, netns
  mount, and conditional dnsmasq inclusion
