from unittest.mock import MagicMock

from stackbox.baremetal.bmc import setup_vbmc
from stackbox.baremetal.libvirt import SESSION_LIBVIRT_URI
from stackbox.models.baremetal import BMCConfig, BMCType, VirtualBMNode


def _node(name: str) -> VirtualBMNode:
    return VirtualBMNode(
        name=name,
        bmc=BMCConfig(type=BMCType.IPMI, username="admin", password="password"),
    )


def test_setup_vbmc_targets_session_libvirt():
    # vbmc must be told to manage the domain over the host session libvirt URI;
    # its container default (qemu:///system) does not contain the VM, so `add`
    # would fail with "No domain with matching name ... was found".
    backend = MagicMock()
    backend.exec.return_value = (0, "")

    setup_vbmc(backend, [_node("stackbox-node-0")], base_port=6230)

    add_call = backend.exec.call_args_list[0]
    args = add_call.args[1]
    assert args[:3] == ["vbmc", "add", "stackbox-node-0"]
    assert "--libvirt-uri" in args
    assert args[args.index("--libvirt-uri") + 1] == SESSION_LIBVIRT_URI


def test_setup_vbmc_assigns_incrementing_ports():
    backend = MagicMock()
    backend.exec.return_value = (0, "")

    nodes = [_node("stackbox-node-0"), _node("stackbox-node-1")]
    setup_vbmc(backend, nodes, base_port=6230)

    assert nodes[0].bmc.port == 6230
    assert nodes[1].bmc.port == 6231
