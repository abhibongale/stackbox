import pytest

from stackbox.exceptions import JobResolutionError
from stackbox.models.zuul import ZuulJobDefinition, ZuulJobVariable
from stackbox.zuul.inheritance import merge_variables, resolve_chain


def _job(name, parent=None, localrc=None, services=None, local_conf=None, regex=""):
    return ZuulJobDefinition(
        name=name,
        parent=parent,
        variables=ZuulJobVariable(
            devstack_localrc=localrc or {},
            devstack_services=services or {},
            devstack_local_conf=local_conf or {},
            tempest_test_regex=regex,
        ),
    )


class TestResolveChain:
    def test_single_job_no_parent(self):
        registry = {"base": _job("base")}
        assert resolve_chain("base", registry) == ["base"]

    def test_two_level_chain(self):
        registry = {
            "base": _job("base"),
            "child": _job("child", parent="base"),
        }
        assert resolve_chain("child", registry) == ["base", "child"]

    def test_three_level_chain(self):
        registry = {
            "grandparent": _job("grandparent"),
            "parent": _job("parent", parent="grandparent"),
            "child": _job("child", parent="parent"),
        }
        assert resolve_chain("child", registry) == ["grandparent", "parent", "child"]

    def test_missing_job(self):
        with pytest.raises(JobResolutionError, match="not found"):
            resolve_chain("nonexistent", {})

    def test_missing_parent(self):
        registry = {"child": _job("child", parent="missing")}
        with pytest.raises(JobResolutionError, match="Parent job 'missing' not found"):
            resolve_chain("child", registry)

    def test_cycle_detection(self):
        registry = {
            "a": _job("a", parent="b"),
            "b": _job("b", parent="a"),
        }
        with pytest.raises(JobResolutionError, match="Cycle detected"):
            resolve_chain("a", registry)


class TestMergeVariables:
    def test_dict_merge_child_overrides(self):
        chain = [
            _job("parent", localrc={"A": "1", "B": "2"}),
            _job("child", localrc={"B": "3", "C": "4"}),
        ]
        merged = merge_variables(chain)
        assert merged.devstack_localrc == {"A": "1", "B": "3", "C": "4"}

    def test_string_replace(self):
        chain = [
            _job("parent", regex="parent_regex"),
            _job("child", regex="child_regex"),
        ]
        merged = merge_variables(chain)
        assert merged.tempest_test_regex == "child_regex"

    def test_string_kept_when_child_empty(self):
        chain = [
            _job("parent", regex="parent_regex"),
            _job("child"),
        ]
        merged = merge_variables(chain)
        assert merged.tempest_test_regex == "parent_regex"

    def test_services_merge(self):
        chain = [
            _job("parent", services={"q-svc": True, "cinder": False}),
            _job("child", services={"s-proxy": True, "cinder": True}),
        ]
        merged = merge_variables(chain)
        assert merged.devstack_services == {
            "q-svc": True,
            "cinder": True,
            "s-proxy": True,
        }

    def test_nested_dict_merge(self):
        chain = [
            _job("parent", local_conf={
                "post-config": {"$NEUTRON_CONF": {"DEFAULT": {"mtu": "1500"}}},
            }),
            _job("child", local_conf={
                "post-config": {"$NEUTRON_CONF": {"DEFAULT": {"debug": "true"}}},
            }),
        ]
        merged = merge_variables(chain)
        neutron = merged.devstack_local_conf["post-config"]["$NEUTRON_CONF"]["DEFAULT"]
        assert neutron["mtu"] == "1500"
        assert neutron["debug"] == "true"

    def test_empty_chain(self):
        merged = merge_variables([])
        assert merged.devstack_localrc == {}
        assert merged.tempest_test_regex == ""

    def test_three_level_merge(self):
        chain = [
            _job("gp", localrc={"A": "1", "B": "2"}),
            _job("p", localrc={"B": "3", "C": "4"}),
            _job("c", localrc={"C": "5", "D": "6"}),
        ]
        merged = merge_variables(chain)
        assert merged.devstack_localrc == {"A": "1", "B": "3", "C": "5", "D": "6"}
