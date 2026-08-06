from configparser import ConfigParser

from stackbox.config_gen.glance import GlanceConfigGenerator
from stackbox.config_gen.ports import PortManager
from stackbox.models.job_config import ResolvedJobConfig


class TestGlanceConfigGenerator:
    def test_generates_glance_api_conf(self, vmedia_job_config, port_manager):
        gen = GlanceConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert "glance-api.conf" in files

    def test_always_uses_file_backend(self, vmedia_job_config, port_manager):
        gen = GlanceConfigGenerator(vmedia_job_config, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["glance-api.conf"])
        assert config["glance_store"]["default_backend"] == "file"
        assert config["file"]["filesystem_store_datadir"] == "/var/lib/glance/images/"

    def test_image_size_limit_from_localrc(self, port_manager):
        job = ResolvedJobConfig(
            job_name="test",
            devstack_localrc={"GLANCE_LIMIT_IMAGE_SIZE_TOTAL": "5000"},
        )
        gen = GlanceConfigGenerator(job, port_manager)
        config = ConfigParser()
        config.read_string(gen.generate()["glance-api.conf"])
        assert config["DEFAULT"]["image_size_total_limit"] == "5000"
