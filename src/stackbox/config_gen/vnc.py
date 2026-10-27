from __future__ import annotations

from dataclasses import dataclass

from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig

# Built from ironic's tools/vnc-container, mirroring devstack (lib/ironic
# "buildah bud ... -t localhost/ironic-vnc-container").
VNC_CONSOLE_IMAGE = "localhost/ironic-vnc-container"

# Devstack defaults (lib/ironic): ir-novnc swaps in fake-graphical and makes it
# the default so fake-hardware nodes don't silently pick no-console.
_VNC_CONSOLE_INTERFACES = "fake-graphical,fake,no-console"
_VNC_DEFAULT_CONSOLE_INTERFACE = "fake-graphical"
_DEVSTACK_DEFAULT_PROVIDER = "systemd"

# Providers that cannot run under stackbox, and what runs in their place.
# systemd needs a user systemd + quadlet on the conductor host, and kubernetes
# needs a cluster; both start the same console image, which the "container"
# provider runs via the host's container engine.
_PROVIDER_FALLBACKS = {"systemd": "container", "kubernetes": "container"}


@dataclass(frozen=True)
class VncSettings:
    console_interfaces: str
    default_console_interface: str
    # What the job asked for vs. what stackbox actually configures.
    provider: str
    effective_provider: str
    port: int

    @property
    def needs_engine(self) -> bool:
        """The conductor must drive a container engine to start consoles."""
        return self.effective_provider == "container"


def vnc_enabled(job: ResolvedJobConfig) -> bool:
    # Unlike most services, devstack leaves ir-novnc disabled unless a job
    # turns it on (ironic devstack/settings), so absent means off.
    return job.devstack_services.get("ir-novnc", False)


def vnc_settings(job: ResolvedJobConfig) -> VncSettings | None:
    """Graphical console settings for a job, or None if ir-novnc is off.

    A job's explicit devstack_localrc always wins over the devstack defaults.
    """
    if not vnc_enabled(job):
        return None
    lr = job.devstack_localrc
    provider = lr.get("IRONIC_VNC_CONTAINER_PROVIDER") or _DEVSTACK_DEFAULT_PROVIDER
    port_override = lr.get("IRONIC_NOVNCPROXY_PORT")
    port = (
        int(port_override) if port_override
        else PortManager(offset=job.port_offset).get("ironic-novncproxy")
    )
    return VncSettings(
        console_interfaces=(
            lr.get("IRONIC_ENABLED_CONSOLE_INTERFACES") or _VNC_CONSOLE_INTERFACES),
        default_console_interface=(
            lr.get("IRONIC_DEFAULT_CONSOLE_INTERFACE") or _VNC_DEFAULT_CONSOLE_INTERFACE),
        provider=provider,
        effective_provider=_PROVIDER_FALLBACKS.get(provider, provider),
        port=port,
    )


def enabled_console_interfaces(job: ResolvedJobConfig) -> str:
    """The console interfaces ironic enables; tempest must advertise the same.

    fake is always added so fake-hardware nodes (used by the API tests) can set
    it, matching how the other optional interfaces are handled.
    """
    vnc = vnc_settings(job)
    current = vnc.console_interfaces if vnc else (
        job.devstack_localrc.get("IRONIC_ENABLED_CONSOLE_INTERFACES") or "no-console")
    parts = [p.strip() for p in current.split(",")]
    return current if "fake" in parts else f"{current},fake"
