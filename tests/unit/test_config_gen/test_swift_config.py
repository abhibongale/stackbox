from stackbox.config_gen.swift import SwiftConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class TestSwiftConfigGenerator:
    def test_generates_proxy_server_conf(self, vmedia_job_config, port_manager):
        gen = SwiftConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "proxy-server.conf" in files

    def test_contains_pipeline(self, vmedia_job_config, port_manager):
        gen = SwiftConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["proxy-server.conf"]
        assert "[pipeline:main]" in content

    def test_uses_swift_hash_from_localrc(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={"SWIFT_HASH": "myhashvalue"},
        )
        gen = SwiftConfigGenerator(job, port_manager)
        content = gen.generate()["proxy-server.conf"]
        assert "myhashvalue" in content

    def test_default_swift_hash(self, port_manager):
        job = ResolvedJobConfig(job_name="test")
        gen = SwiftConfigGenerator(job, port_manager)
        content = gen.generate()["proxy-server.conf"]
        assert "1234123412341234" in content

    def test_port_from_port_manager(self, port_manager):
        gen = SwiftConfigGenerator(
            ResolvedJobConfig(job_name="test"), port_manager
        )
        content = gen.generate()["proxy-server.conf"]
        assert f"bind_port = {port_manager.get('swift')}" in content
