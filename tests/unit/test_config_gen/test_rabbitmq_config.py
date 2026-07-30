import json

from stackbox.config_gen.rabbitmq import RabbitMQConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class TestRabbitMQConfigGenerator:
    def test_generates_two_files(self, vmedia_job_config, port_manager):
        gen = RabbitMQConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "rabbitmq.conf" in files
        assert "definitions.json" in files

    def test_conf_has_tcp_listener(self, vmedia_job_config, port_manager):
        gen = RabbitMQConfigGenerator(vmedia_job_config, port_manager)
        conf = gen.generate()["rabbitmq.conf"]
        assert f"listeners.tcp.default = {port_manager.get('rabbitmq')}" in conf

    def test_definitions_has_stackbox_user(self, vmedia_job_config, port_manager):
        gen = RabbitMQConfigGenerator(vmedia_job_config, port_manager)
        defs = json.loads(gen.generate()["definitions.json"])
        usernames = [u["name"] for u in defs["users"]]
        assert "stackbox" in usernames

    def test_definitions_uses_password_field(self, vmedia_job_config, port_manager):
        gen = RabbitMQConfigGenerator(vmedia_job_config, port_manager)
        defs = json.loads(gen.generate()["definitions.json"])
        stackbox_user = next(u for u in defs["users"] if u["name"] == "stackbox")
        assert "password" in stackbox_user
        assert "password_hash" not in stackbox_user

    def test_vhost_and_permissions(self, vmedia_job_config, port_manager):
        gen = RabbitMQConfigGenerator(vmedia_job_config, port_manager)
        defs = json.loads(gen.generate()["definitions.json"])
        assert defs["vhosts"][0]["name"] == "/"
        assert len(defs["permissions"]) >= 2
