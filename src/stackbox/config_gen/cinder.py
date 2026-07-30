from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator


class CinderConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = self._base_config("cinder")

        config["DEFAULT"].update({
            "my_ip": "0.0.0.0",
            "enabled_backends": "lvm",
            "default_volume_type": "lvm",
            "auth_strategy": "keystone",
        })

        config["lvm"] = {
            "volume_driver": "cinder.volume.drivers.lvm.LVMVolumeDriver",
            "volume_group": "stack-volumes-default",
            "target_protocol": "iscsi",
            "target_helper": "tgtadm",
            "volume_backend_name": "lvm",
        }

        return {"cinder.conf": self._render(config)}
