ZUUL_API_BASE = "https://zuul.opendev.org/api"
ZUUL_TENANT = "openstack"

KOLLA_REGISTRY = "quay.io/openstack.kolla"
METAL3_REGISTRY = "quay.io/metal3-io"

DEFAULT_RELEASE = "master-ubuntu-noble"

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
    "mariadb": "mariadb",
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

METAL3_IMAGES = {
    "sushy-tools": "sushy-tools",
    "vbmc": "vbmc",
}
