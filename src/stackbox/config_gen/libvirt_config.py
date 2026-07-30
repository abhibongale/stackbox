from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator

LIBVIRTD_CONF = """\
listen_tls = 0
listen_tcp = 0
auth_unix_rw = "none"
log_level = 3
log_outputs = "3:stderr"
"""

QEMU_CONF = """\
user = "root"
group = "root"
cgroup_device_acl = [
    "/dev/null", "/dev/full", "/dev/zero",
    "/dev/random", "/dev/urandom",
    "/dev/ptmx", "/dev/kvm",
    "/dev/net/tun"
]
"""


class LibvirtConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        return {
            "libvirtd.conf": LIBVIRTD_CONF,
            "qemu.conf": QEMU_CONF,
        }
