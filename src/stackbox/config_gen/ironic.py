from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator
from stackbox.config_gen.translator import DevStackTranslator
from stackbox.models.network import NetworkConfig


class IronicConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        config = self._base_config("ironic")
        lr = self.job.devstack_localrc
        provisioning_ip = NetworkConfig().provisioning_subnet.gateway

        # These enabled_*_interfaces keys are often omitted by IPMI jobs, which
        # rely on devstack deriving them from IRONIC_DEPLOY_DRIVER. Fall back to
        # the resolved job values (which already honor the deploy driver) instead
        # of hardcoding redfish, otherwise an IPMI job gets a redfish config it
        # cannot talk to its (vbmc/IPMI-only) nodes with.
        boot_ifaces = lr.get("IRONIC_ENABLED_BOOT_INTERFACES") or self.job.boot_interface
        hardware_types = lr.get("IRONIC_ENABLED_HARDWARE_TYPES") or ",".join(
            self.job.hardware_types)
        # ipmi hardware type uses the ipmitool management/power interfaces;
        # redfish uses redfish. Honor an explicit localrc value when present.
        bmc_iface = "ipmitool" if self.job.bmc_driver == "ipmi" else "redfish"

        config["DEFAULT"].update({
            "enabled_hardware_types": hardware_types,
            "enabled_boot_interfaces": boot_ifaces,
            "enabled_deploy_interfaces": lr.get(
                "IRONIC_ENABLED_DEPLOY_INTERFACES", "direct"),
            "enabled_management_interfaces": lr.get(
                "IRONIC_ENABLED_MANAGEMENT_INTERFACES", bmc_iface),
            "enabled_power_interfaces": lr.get(
                "IRONIC_ENABLED_POWER_INTERFACES", bmc_iface),
            "auth_strategy": "keystone",
            "my_ip": provisioning_ip,
            "esp_image": "/opt/stackbox/efiboot.img",
            "kernel_append_params": "nofb nomodeset vga=normal console=ttyS0,115200",
        })

        config["conductor"] = {
            "automated_clean": lr.get("IRONIC_AUTOMATED_CLEAN_ENABLED", "true"),
            "deploy_callback_timeout": lr.get("IRONIC_CALLBACK_TIMEOUT", "600"),
        }

        config["deploy"] = {
            "http_url": f"http://{provisioning_ip}:{self.ports.get('ironic-http')}",
            "http_root": "/var/lib/ironic/httpboot",
            # Drives which PXE bootfile Ironic hands out over DHCP. Without this
            # Ironic defaults to uefi and serves snponly.efi, which a legacy-BIOS
            # VM cannot execute — the PXE chain dies before iPXE loads.
            "default_boot_mode": self.job.boot_mode,
        }

        # Ironic ships with oslo.policy >= 6.0, which removed the [oslo_policy]
        # enforce_scope option (scope is now *always* enforced from each rule's
        # scope_types) and defaults enforce_new_defaults to True. The previous
        # workaround set both to false and backfired:
        #   * enforce_scope=false is an unknown option and silently ignored, so
        #     scope is still enforced.
        #   * enforce_new_defaults=false forces allocation creation down the
        #     legacy baremetal:allocation:create_pre_rbac check, whose
        #     scope_types is ['project'] only. tempest's admin token is
        #     system-scoped, so that check raised InvalidScope -> 500 ServerFault
        #     on POST /v1/allocations.
        # Keeping the modern new-defaults behavior skips the create_pre_rbac
        # branch entirely; baremetal:allocation:create allows scope_types
        # ['system', 'project'], so the system-scoped tempest admin succeeds.
        config["oslo_policy"] = {
            "enforce_new_defaults": "true",
        }

        config["service_catalog"] = {
            "endpoint_override": f"http://{provisioning_ip}:{self.ports.get('ironic-api')}",
        }

        config["neutron"] = {
            "auth_url": f"http://localhost:{self.ports.get('keystone')}",
            "auth_type": "password",
            "project_domain_name": "Default",
            "user_domain_name": "Default",
            "project_name": "service",
            "username": "ironic",
            "password": self._service_pass(),
            "cleaning_network": "provisioning",
            "provisioning_network": "provisioning",
        }

        config["glance"] = {
            "auth_url": f"http://localhost:{self.ports.get('keystone')}",
            "auth_type": "password",
            "project_domain_name": "Default",
            "user_domain_name": "Default",
            "project_name": "service",
            "username": "ironic",
            "password": self._service_pass(),
            "endpoint_override": f"http://localhost:{self.ports.get('glance')}",
        }

        config["swift"] = {
            "auth_url": f"http://localhost:{self.ports.get('keystone')}",
            "auth_type": "password",
            "project_domain_name": "Default",
            "user_domain_name": "Default",
            "project_name": "service",
            "username": "ironic",
            "password": self._service_pass(),
        }

        config["pxe"] = {
            "tftp_server": provisioning_ip,
            "tftp_root": "/var/lib/ironic/tftpboot",
            # Override the upstream default of /tftpboot/master_images (which
            # lands on the container overlay fs). Ironic hardlinks cached deploy
            # images from this master cache into the per-node httpboot/tftpboot
            # dirs; keeping it under /var/lib/ironic (the shared volume) puts the
            # cache and its link targets on one filesystem so hardlinks succeed.
            "tftp_master_path": "/var/lib/ironic/tftpboot/master_images",
            "images_path": "/var/lib/ironic/httpboot/images",
            "instance_master_path": "/var/lib/ironic/httpboot/master_images",
        }

        config["nova"] = {
            "auth_url": f"http://localhost:{self.ports.get('keystone')}/v3",
            "auth_type": "password",
            "project_domain_name": "Default",
            "user_domain_name": "Default",
            "project_name": "service",
            "username": "ironic",
            "password": self._service_pass(),
            "endpoint_override": f"http://localhost:{self.ports.get('nova-api')}/v2.1",
        }

        config["api"] = {
            "host_ip": "0.0.0.0",
            "port": str(self.ports.get("ironic-api")),
        }

        translated = DevStackTranslator().translate(self.job.devstack_localrc)
        if "ironic" in translated:
            for section, opts in translated["ironic"].items():
                if section not in config:
                    config[section] = {}
                config[section].update(opts)

        # fake-hardware must always be enabled so ironic-tempest-plugin API
        # tests can create nodes and exercise all fake interface types.
        # (tempest.conf baremetal.driver is hardcoded to fake-hardware,
        # mirroring what devstack does for API tests.)
        # Applied after the translator so these are never overwritten by localrc.
        def _add_if_missing(csv: str, entry: str) -> str:
            parts = [p.strip() for p in csv.split(",")]
            return csv if entry in parts else f"{csv},{entry}"

        def _prepend_if_missing(csv: str, entry: str) -> str:
            parts = [p.strip() for p in csv.split(",")]
            return csv if entry in parts else f"{entry},{csv}"

        config["DEFAULT"]["enabled_hardware_types"] = _add_if_missing(
            config["DEFAULT"]["enabled_hardware_types"], "fake-hardware")

        # Prepend fake for boot and deploy so fake-hardware nodes pick the fake
        # variant as their default (real hardware skips fake since it's not in
        # their supported-interfaces list). Append for management/power where
        # interfaces are hardware-specific and order doesn't affect defaults.
        for iface in ("boot", "deploy"):
            key = f"enabled_{iface}_interfaces"
            config["DEFAULT"][key] = _prepend_if_missing(
                config["DEFAULT"][key], "fake")
        for iface in ("management", "power"):
            key = f"enabled_{iface}_interfaces"
            config["DEFAULT"][key] = _add_if_missing(
                config["DEFAULT"][key], "fake")

        # Optional interfaces not set by localrc: use the no-op default so
        # real drivers still work, plus fake so fake-hardware nodes can set them.
        # fake deploy also prevents automated cleaning from booting a real ramdisk
        # on fake-hardware nodes (which would leave them in "clean failed").
        for iface, no_op in [
            ("bios", "no-bios"),
            ("console", "no-console"),
            ("inspect", "no-inspect"),
            ("raid", "no-raid"),
            ("rescue", "no-rescue"),
            ("vendor", "no-vendor"),
        ]:
            key = f"enabled_{iface}_interfaces"
            current = config["DEFAULT"].get(key, no_op)
            config["DEFAULT"][key] = _add_if_missing(current, "fake")

        # The autodetect deploy interface refuses to load unless every entry in
        # autodetect_deploy_interfaces is also enabled. Ironic's default for that
        # option includes 'ramdisk', which these jobs don't enable, so the
        # conductor dies with DriverLoadError. Mirror devstack: honor the job's
        # IRONIC_AUTODETECT_DEPLOY_INTERFACES when set; otherwise constrain the
        # list to the concrete deploy interfaces the job actually enabled.
        enabled_deploy = [
            p.strip()
            for p in config["DEFAULT"]["enabled_deploy_interfaces"].split(",")
            if p.strip()
        ]
        if "autodetect" in enabled_deploy:
            autodetect_list = lr.get("IRONIC_AUTODETECT_DEPLOY_INTERFACES", "").strip()
            if not autodetect_list:
                autodetect_list = ",".join(
                    i for i in enabled_deploy if i not in ("autodetect", "fake")
                )
            config["DEFAULT"]["autodetect_deploy_interfaces"] = autodetect_list

        return {"ironic.conf": self._render(config)}
