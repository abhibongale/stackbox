from __future__ import annotations

DEVSTACK_TO_SERVICE: dict[str, tuple[str, str, str] | None] = {
    # Ironic — config file mappings
    "IRONIC_ENABLED_HARDWARE_TYPES": ("ironic", "DEFAULT", "enabled_hardware_types"),
    "IRONIC_ENABLED_BOOT_INTERFACES": ("ironic", "DEFAULT", "enabled_boot_interfaces"),
    "IRONIC_ENABLED_DEPLOY_INTERFACES": ("ironic", "DEFAULT", "enabled_deploy_interfaces"),
    "IRONIC_ENABLED_MANAGEMENT_INTERFACES": ("ironic", "DEFAULT", "enabled_management_interfaces"),
    "IRONIC_ENABLED_POWER_INTERFACES": ("ironic", "DEFAULT", "enabled_power_interfaces"),
    "IRONIC_ENABLED_VENDOR_INTERFACES": ("ironic", "DEFAULT", "enabled_vendor_interfaces"),
    "IRONIC_ENABLED_BIOS_INTERFACES": ("ironic", "DEFAULT", "enabled_bios_interfaces"),
    "IRONIC_ENABLED_INSPECT_INTERFACES": ("ironic", "DEFAULT", "enabled_inspect_interfaces"),
    "IRONIC_ENABLED_RAID_INTERFACES": ("ironic", "DEFAULT", "enabled_raid_interfaces"),
    "IRONIC_ENABLED_RESCUE_INTERFACES": ("ironic", "DEFAULT", "enabled_rescue_interfaces"),
    "IRONIC_ENABLED_STORAGE_INTERFACES": ("ironic", "DEFAULT", "enabled_storage_interfaces"),
    "IRONIC_ENABLED_CONSOLE_INTERFACES": ("ironic", "DEFAULT", "enabled_console_interfaces"),
    "IRONIC_DEFAULT_BOOT_INTERFACE": ("ironic", "DEFAULT", "default_boot_interface"),
    "IRONIC_DEFAULT_DEPLOY_INTERFACE": ("ironic", "DEFAULT", "default_deploy_interface"),
    "IRONIC_DEPLOY_DRIVER": None,
    "IRONIC_AUTOMATED_CLEAN_ENABLED": ("ironic", "conductor", "automated_clean"),
    "IRONIC_CALLBACK_TIMEOUT": ("ironic", "conductor", "deploy_callback_timeout"),

    # Ironic — STACKBOX behavior (no config file mapping)
    "IRONIC_VM_COUNT": None,
    "IRONIC_VM_SPECS_RAM": None,
    "IRONIC_VM_SPECS_CPU": None,
    "IRONIC_VM_SPECS_DISK": None,
    "IRONIC_VM_EPHEMERAL_DISK": None,
    "IRONIC_VM_NETWORK_BRIDGE": None,
    "IRONIC_VM_LOG_DIR": None,
    "IRONIC_BAREMETAL_BASIC_OPS": None,
    "IRONIC_BUILD_DEPLOY_RAMDISK": None,
    "IRONIC_TEMPEST_BUILD_TIMEOUT": None,
    "IRONIC_TEMPEST_WHOLE_DISK_IMAGE": None,
    "IRONIC_REDFISH_EMULATOR_FEATURE_SET": None,
    "IRONIC_LOG_STEPS_TO_SYSLOG": None,
    "IRONIC_GRUB2_FILE": None,
    "IRONIC_GRUB2_SHIM_FILE": None,
    "IRONIC_GRUB2_CONFIG_PATH": None,

    # Neutron
    "Q_AGENT": None,
    "Q_ML2_TENANT_NETWORK_TYPE": ("neutron_ml2", "ml2", "tenant_network_types"),
    "Q_ML2_PLUGIN_MECHANISM_DRIVERS": ("neutron_ml2", "ml2", "mechanism_drivers"),
    "Q_USE_SECGROUP": None,

    # Nova
    "NOVA_VNC_ENABLED": ("nova", "vnc", "enabled"),
    "NOVA_LIBVIRT_TB_CACHE_SIZE": None,
    "VIRT_DRIVER": None,

    # Glance
    "GLANCE_LIMIT_IMAGE_SIZE_TOTAL": ("glance", "DEFAULT", "image_size_total_limit"),

    # Swift
    "SWIFT_HASH": ("swift_proxy", "swift-hash", "swift_hash_path_suffix"),
    "SWIFT_REPLICAS": None,
    "SWIFT_ENABLE_TEMPURLS": None,
    "SWIFT_TEMPURL_KEY": None,
    "SWIFT_START_ALL_SERVICES": None,

    # Tempest — handled by tempest_conf.py directly
    "TEMPEST_COMPUTE_TYPE": None,
    "DEFAULT_INSTANCE_TYPE": None,
    "INSTALL_TEMPEST": None,

    # Passwords — consumed by base.py password helpers
    "DATABASE_PASSWORD": None,
    "RABBIT_PASSWORD": None,
    "ADMIN_PASSWORD": None,
    "SERVICE_PASSWORD": None,

    # General behavior — no config file mapping
    "API_WORKERS": None,
    "SERVICE_TIMEOUT": None,
    "BUILD_TIMEOUT": None,
    "FORCE_CONFIG_DRIVE": None,
    "ERROR_ON_CLONE": None,
    "DEBUG_LIBVIRT_COREDUMPS": None,
    "LOGFILE": None,
    "LOG_COLOR": None,
    "VERBOSE": None,
    "VERBOSE_NO_TIMESTAMP": None,
    "ENABLE_SYSCTL_MEM_TUNING": None,
    "ENABLE_SYSCTL_NET_TUNING": None,
    "ENABLE_ZSWAP": None,
    "OVN_DBS_LOG_LEVEL": None,
    "LIBVIRT_TYPE": None,
    "CIRROS_VERSION": None,
    "IMAGE_URLS": None,

    # Network — STACKBOX behavior
    "FIXED_RANGE": None,
    "FLOATING_RANGE": None,
    "NETWORK_GATEWAY": None,
    "PUBLIC_NETWORK_GATEWAY": None,
    "PUBLIC_BRIDGE_MTU": None,
    "IPV4_ADDRS_SAFE_TO_USE": None,
    "NEUTRON_CREATE_INITIAL_NETWORKS": None,
    "HOST_IP": None,
    "SERVICE_HOST": None,
}
