from unittest.mock import MagicMock, patch

import pytest

from stackbox.bootstrap.database import init_database
from stackbox.exceptions import BootstrapError


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.exec.return_value = (0, "OK")
    return backend


class TestInitDatabase:

    @patch("stackbox.bootstrap.database.wait_tcp")
    def test_runs_init_sql(self, mock_wait, mock_backend):
        init_database(mock_backend, 3306)
        assert mock_backend.exec.call_count == 2
        first_call = mock_backend.exec.call_args_list[0]
        assert first_call[0][1] == ["mysql", "-u", "root", "-pstackbox", "-e", "SELECT 1"]
        second_call = mock_backend.exec.call_args_list[1]
        cmd_str = " ".join(second_call[0][1])
        assert "init.sql" in cmd_str

    @patch("stackbox.bootstrap.database.wait_tcp")
    def test_raises_if_mariadb_not_responding(self, mock_wait, mock_backend):
        mock_backend.exec.return_value = (1, "connection refused")
        with pytest.raises(BootstrapError, match="not responding"):
            init_database(mock_backend, 3306)

    @patch("stackbox.bootstrap.database.wait_tcp")
    def test_raises_if_init_sql_fails(self, mock_wait, mock_backend):
        mock_backend.exec.side_effect = [
            (0, "OK"),
            (1, "ERROR 1045"),
        ]
        with pytest.raises(BootstrapError, match="init.sql failed"):
            init_database(mock_backend, 3306)
