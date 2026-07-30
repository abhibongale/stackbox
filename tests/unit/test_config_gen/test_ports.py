import pytest

from stackbox.config_gen.ports import PortManager
from stackbox.exceptions import ConfigGenerationError


class TestPortManager:
    def test_get_default_port(self):
        pm = PortManager()
        assert pm.get("mariadb") == 3306
        assert pm.get("keystone") == 5000
        assert pm.get("ironic-api") == 6385

    def test_get_with_offset(self):
        pm = PortManager(offset=10000)
        assert pm.get("mariadb") == 13306
        assert pm.get("keystone") == 15000
        assert pm.get("ironic-api") == 16385

    def test_unknown_service_raises(self):
        pm = PortManager()
        with pytest.raises(ConfigGenerationError, match="Unknown service port"):
            pm.get("nonexistent")
