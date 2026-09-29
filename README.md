# STACKBOX

Run OpenStack Ironic upstream Zuul CI jobs locally in Docker containers.

STACKBOX fetches job definitions from the Zuul API, generates the matching service configurations, and bootstraps a full Ironic development environment using containerized OpenStack services. It can also reproduce specific CI failures from a Zuul build URL.

## Prerequisites

- Python 3.10+
- Docker
- libvirt with QEMU/KVM (`/dev/kvm` must be accessible)
- At least 16 GB RAM (each baremetal VM uses 1-3 GB)

## Installation

```bash
git clone https://github.com/user/stackbox.git
cd stackbox
pip install -e ".[dev]"
```

## Quick Start

```bash
# 1. Validate prerequisites and pull container images
stackbox init

# 2. Run a Zuul CI job locally
stackbox run ironic-tempest-uefi-redfish-vmedia

# 3. Clean up all resources when done
stackbox clean
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `stackbox init` | Validate host prerequisites and pull base images |
| `stackbox run <job>` | Run a Zuul CI job locally |
| `stackbox reproduce <url>` | Reproduce a CI job from a Zuul build URL |
| `stackbox list` | List available Zuul jobs for a project |
| `stackbox config <job>` | Generate service configs without deploying |
| `stackbox status` | Show running stackbox containers |
| `stackbox logs <service>` | Tail logs from a service container |
| `stackbox exec <service> <cmd>` | Execute a command in a service container |
| `stackbox clean` | Clean up all stackbox resources |

### Global Options

```
--verbose, -v         Enable DEBUG logging
--log-file PATH       Write logs to a file
```

### Run / Reproduce Options

```
--dry-run             Show what would be deployed without deploying
--port-offset N       Shift all service ports by N (run multiple envs)
--local-repo svc=path Use local source for a service image
--skip-tempest        Skip test execution
--keep                Keep containers running after tests
--release TAG         Kolla image release tag
--project PROJECT     OpenStack project (default: openstack/ironic)
--branch BRANCH       Git branch (default: master)
--pipeline PIPELINE   Zuul pipeline (default: gate; use check for check-only jobs)
```

Run `stackbox <command> --help` for the full list of options per command.

> **Note:** `stackbox list` shows every job across *all* branches of a project,
> because that is how the Zuul project API aggregates configs. A job may be
> defined only on a stable/bugfix branch (not `master`), so resolving it with the
> default `--branch master` returns a "not defined" error. Use `stackbox list
> --branch master` to see only what `run` will resolve by default, and pass
> `--pipeline check` for check-only jobs.

## Supported Boot Modes

| Boot Interface | BMC Driver | Description |
|---------------|------------|-------------|
| `redfish-virtual-media` | `redfish` | UEFI virtual media boot via sushy-tools |
| `pxe` / `ipxe` | `ipmi` | PXE/iPXE boot via VBMC and dnsmasq |

## Job Support

STACKBOX targets single-host Ironic jobs. It reads each job's `devstack_services`
and `devstack_localrc` and deploys only the services the job enables, so
API/functional jobs bring up a smaller stack than full deploy jobs.

### Supported

- **redfish + virtual media** (UEFI and BIOS) — the best-supported deploy path.
- **ipmi + PXE/iPXE boot** — via VBMC; the TFTP/`ironic-pxe` container is added
  automatically for network-boot jobs.
- **`direct` and `partition`/`wholedisk` deploy interfaces**.
- **Functional / API-only jobs** (e.g. `ironic-tempest-functional-python3`) —
  nova/glance/placement are automatically skipped when the job disables them.
- **Cinder** (block storage) when a job enables `c-api`.

### Not supported (yet)

These jobs resolve and plan, but will not deploy correctly:

| Feature | Example job | Why |
|---------|-------------|-----|
| OVN networking | `ironic-tempest-ovn-*` | STACKBOX wires OVS/ML2 only |
| Multinode | `ironic-tempest-ipa-wholedisk-direct-multinode` | Single-host only |
| Boot from volume | `ironic-tempest-bfv` | `IRONIC_STORAGE_INTERFACE` not implemented |
| Standalone / no-auth | `ironic-tempest-standalone-advanced` | Provider networks + standalone mode |
| DIB image building | `*-dib`, `*-4k` | STACKBOX uses a prebuilt IPA ramdisk |
| IPv6 provisioning | `ironic-tempest-ovn-uefi-ipxe-ipv6` | IPv4 provisioning network only |
| VNC console provider | `ironic-tempest-vnc-container` | No VNC container provider |

Unmapped `devstack_localrc` keys are logged as a warning during resolution and
are a good signal that a job depends on an unsupported feature.

## Local Development

Use `--local-repo` to build and run services from local source checkouts:

```bash
stackbox run ironic-tempest-uefi-redfish-vmedia \
  --local-repo ironic-api=/path/to/ironic \
  --local-repo ironic-conductor=/path/to/ironic
```

This builds dev images from the local source and swaps them in for the standard Kolla images. For tempest plugins:

```bash
stackbox run ironic-tempest-uefi-redfish-vmedia \
  --local-repo ironic-tempest-plugin=/path/to/ironic-tempest-plugin
```

## Reproducing CI Failures

Reproduce a specific CI build from its Zuul URL:

```bash
stackbox reproduce https://zuul.opendev.org/t/openstack/build/<uuid>
```

This fetches the build's inventory and variables, then runs the exact same job configuration locally.

## Architecture

```
Zuul API --> Job Resolution --> Config Generation --> Container Orchestration --> Tempest
```

1. **Zuul API** (`zuul/`): Fetches job definitions from `zuul.opendev.org`
2. **Job Resolution** (`zuul/freeze.py`): Resolves parent jobs, merges variables into `ResolvedJobConfig`
3. **Config Generation** (`config_gen/`): Generates INI configs (ironic.conf, nova.conf, etc.) from job variables
4. **Container Orchestration** (`bootstrap/`): 8-phase bootstrap sequence using Docker containers
5. **Tempest** (`tempest/`): Runs tempest tests against the deployed environment

### Bootstrap Phases

1. Create shared volumes
2. Start infrastructure (MariaDB, RabbitMQ, Memcached, Keystone)
3. Bootstrap Keystone (db_sync, fernet, bootstrap, service users)
4. Register service catalog (endpoints)
5. Database sync (Glance, Neutron, Nova, Placement, Ironic)
6. Start services (all OpenStack services in dependency order)
7. Network and resource setup (OVS bridges, provisioning network, flavors)
8. Baremetal VMs and enrollment (libvirt VMs, BMC, node enrollment)

### Networking

STACKBOX sets up a flat provisioning network using OVS bridges:

```
VMs <--> brbm-link <--> veth <--> brbm (OVS) <--> br-int (OVS) <--> Neutron agents
```

The Neutron DHCP agent runs dnsmasq inside a `qdhcp-*` network namespace, serving
IP addresses from Neutron's port database. This ensures VMs always get the IP that
Neutron assigned to their port, which is required for tempest SSH validation.

### Container Runtime

STACKBOX uses Docker as its container runtime. All OpenStack services run in
[Kolla](https://docs.openstack.org/kolla/latest/) container images. Kolla's
`config_files` mechanism is used to install configuration files with correct
ownership and permissions at container startup.

## Configuration

STACKBOX follows XDG conventions:

| Path | Purpose |
|------|---------|
| `~/.config/stackbox/` | User configuration |
| `~/.local/share/stackbox/sessions/` | Session data (configs, manifests, results) |
| `~/.local/share/stackbox/logs/` | Log files |
| `~/.cache/stackbox/repos/` | Cached git repositories for offline mode |

## Known Issues

### Local image builds fail with `exec: "/bin/sh": no such file or directory`

On some hosts (notably very new kernels with Docker's **containerd image
store**, the default since Docker 25), a `RUN` step can fail with:

```
runc run failed: ... error during container init: exec: "/bin/sh": ...
no such file or directory
```

This is the containerd snapshotter committing an empty/corrupt layer — not a
STACKBOX or Containerfile bug. STACKBOX retries such builds with `--no-cache`
automatically, which clears the usual transient case. If it persists, disable
the containerd snapshotter and restart Docker:

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "features": {
    "containerd-snapshotter": false
  }
}
EOF
sudo systemctl restart docker
docker info --format '{{.Driver}}'   # should print: overlay2
```

Switching image stores hides existing images (kept, not deleted, in the other
store); STACKBOX rebuilds/pulls what it needs.

## License

Apache 2.0
