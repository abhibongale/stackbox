ZUUL_API_BASE = "https://zuul.opendev.org/api"
ZUUL_TENANT = "openstack"

KOLLA_REGISTRY = "quay.io/openstack.kolla"
METAL3_REGISTRY = "quay.io/metal3-io"

DEFAULT_RELEASE = "2025.1-ubuntu-noble"

BASE_PORTS = {
    "mariadb": 3306,
    "rabbitmq": 5672,
    "memcached": 11211,
    "keystone": 5000,
    "glance": 9292,
    "placement": 8778,
    "neutron": 9696,
    "nova-api": 8774,
    "nova-metadata": 8775,
    "nova-novncproxy": 6080,
    "ironic-api": 6385,
    "ironic-http": 3928,
    "sushy-tools": 9132,
    "vbmc-base": 6230,
    "swift": 8080,
    "cinder": 8776,
    "tftp": 69,
    "ovs": 6640,
}

CONTAINER_PREFIX = "stackbox"

KOLLA_IMAGES = {
    "mariadb": "mariadb-server",
    "rabbitmq": "rabbitmq",
    "memcached": "memcached",
    "keystone": "keystone",
    "glance-api": "glance-api",
    "placement-api": "placement-api",
    "neutron-server": "neutron-server",
    "neutron-openvswitch-agent": "neutron-openvswitch-agent",
    "neutron-dhcp-agent": "neutron-dhcp-agent",
    "neutron-l3-agent": "neutron-l3-agent",
    "nova-api": "nova-api",
    "nova-scheduler": "nova-scheduler",
    "nova-conductor": "nova-conductor",
    "nova-compute": "nova-compute-ironic",
    "ironic-api": "ironic-api",
    "ironic-conductor": "ironic-conductor",
    "ironic-pxe": "ironic-pxe",
    "dnsmasq": "dnsmasq",
    "openvswitch-db-server": "openvswitch-db-server",
    "openvswitch-vswitchd": "openvswitch-vswitchd",
    "nova-libvirt": "nova-libvirt",
    "swift-proxy-server": "swift-proxy-server",
    "swift-object-server": "swift-object-server",
    "swift-container-server": "swift-container-server",
    "swift-account-server": "swift-account-server",
    "cinder-api": "cinder-api",
    "cinder-scheduler": "cinder-scheduler",
    "cinder-volume": "cinder-volume",
    "tgtd": "tgtd",
    "iscsid": "iscsid",
}

KOLLA_RELEASE_OVERRIDES = {
    "swift-proxy-server": "master-ubuntu-noble",
}

METAL3_IMAGES = {
    "sushy-tools": "sushy-tools",
    "vbmc": "vbmc",
}

KOLLA_SERVICE_COMMANDS = {
    "mariadb": "/usr/sbin/mariadbd",
    "rabbitmq": "/usr/sbin/rabbitmq-server",
    "memcached": "/usr/bin/memcached -u memcache",
    "glance-api": "glance-api",
    "neutron-server": "neutron-server --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini",
    "neutron-dhcp-agent": "neutron-dhcp-agent --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/dhcp_agent.ini",
    "neutron-l3-agent": "neutron-l3-agent --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/l3_agent.ini",
    "neutron-openvswitch-agent": "neutron-openvswitch-agent --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/openvswitch_agent.ini",
    "nova-api": "nova-api",
    "nova-scheduler": "nova-scheduler",
    "nova-conductor": "nova-conductor",
    "nova-compute": "nova-compute",
    "ironic-api": "ironic-api --config-file /etc/ironic/ironic.conf",
    "ironic-conductor": "ironic-conductor --config-file /etc/ironic/ironic.conf",
    "openvswitch-db-server": "ovsdb-server /etc/openvswitch/conf.db --remote=punix:/run/openvswitch/db.sock --remote=ptcp:6640",
    "openvswitch-vswitchd": "ovs-vswitchd unix:/run/openvswitch/db.sock",
    "nova-libvirt": "libvirtd --listen",
    "swift-proxy-server": "swift-proxy-server /etc/swift/proxy-server.conf",
    "cinder-api": "cinder-api --config-file /etc/cinder/cinder.conf",
    "cinder-scheduler": "cinder-scheduler --config-file /etc/cinder/cinder.conf",
    "cinder-volume": "cinder-volume --config-file /etc/cinder/cinder.conf",
    "tgtd": "tgtd -f",
    "ironic-pxe": "in.tftpd -L --address 0.0.0.0:69 -s /tftpboot",
    "dnsmasq": "dnsmasq -k --conf-file=/etc/dnsmasq.conf",
}

OPENDEV_GIT_BASE = "https://opendev.org"

REQUIRED_REPOS = {
    "zuul/zuul-jobs": f"{OPENDEV_GIT_BASE}/zuul/zuul-jobs.git",
    "openstack/openstack-zuul-jobs": f"{OPENDEV_GIT_BASE}/openstack/openstack-zuul-jobs.git",
    "openstack/devstack": f"{OPENDEV_GIT_BASE}/openstack/devstack.git",
    "openstack/devstack-plugin-ironic": f"{OPENDEV_GIT_BASE}/openstack/devstack-plugin-ironic.git",
    "openstack/ironic": f"{OPENDEV_GIT_BASE}/openstack/ironic.git",
}
