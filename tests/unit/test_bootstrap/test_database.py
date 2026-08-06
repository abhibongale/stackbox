from unittest.mock import MagicMock, call, patch

import pytest

from stackbox.bootstrap.database import init_database
from stackbox.exceptions import BootstrapError


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.exec.return_value = (0, "OK")
    return backend


class TestInitDatabase:

    @patch("stackbox.bootstrap.database.wait_exec")
    @patch("stackbox.bootstrap.database.wait_tcp")
    def test_runs_init_sql_on_fresh_db(self, mock_wait_tcp, mock_wait_exec, mock_backend):
        mock_backend.exec.side_effect = [
            (0, ""),  # schema check: no keystone db
            (0, "OK"),  # init.sql
        ]
        init_database(mock_backend, 3306)
        assert mock_backend.exec.call_count == 2
        init_call = mock_backend.exec.call_args_list[1]
        cmd_str = " ".join(init_call[0][1])
        assert "init.sql" in cmd_str

    @patch("stackbox.bootstrap.database.wait_exec")
    @patch("stackbox.bootstrap.database.wait_tcp")
    def test_skips_init_sql_when_dbs_exist(self, mock_wait_tcp, mock_wait_exec, mock_backend):
        mock_backend.exec.return_value = (0, "keystone")
        init_database(mock_backend, 3306)
        assert mock_backend.exec.call_count == 1
        cmd_str = " ".join(mock_backend.exec.call_args_list[0][0][1])
        assert "SCHEMA_NAME" in cmd_str

    @patch("stackbox.bootstrap.database.wait_exec")
    @patch("stackbox.bootstrap.database.wait_tcp")
    def test_raises_if_init_sql_fails(self, mock_wait_tcp, mock_wait_exec, mock_backend):
        mock_backend.exec.side_effect = [
            (0, ""),  # schema check: no keystone db
            (1, "ERROR 1045"),  # init.sql fails
        ]
        with pytest.raises(BootstrapError, match="init.sql failed"):
            init_database(mock_backend, 3306)
