# STACKBOX

Run OpenStack Ironic upstream Zuul CI jobs locally in Podman containers.

STACKBOX fetches job definitions from the Zuul API, generates the matching service configurations, and bootstraps a full Ironic development environment using containerized OpenStack services. It can also reproduce specific CI failures from a Zuul build URL.

## Prerequisites

- Python 3.10+
- Podman
- libvirt with QEMU/KVM (`/dev/kvm` must be accessible)
- Open vSwitch (`ovs-vsctl`)
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
```

Run `stackbox <command> --help` for the full list of options per command.

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
4. **Container Orchestration** (`bootstrap/`): 8-phase bootstrap sequence using Podman containers
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

## Configuration

STACKBOX follows XDG conventions:

| Path | Purpose |
|------|---------|
| `~/.config/stackbox/` | User configuration |
| `~/.local/share/stackbox/sessions/` | Session data (configs, manifests, results) |
| `~/.local/share/stackbox/logs/` | Log files |
| `~/.cache/stackbox/repos/` | Cached git repositories for offline mode |

## License

Apache 2.0
