import signal
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from stackbox.cli.main import _graceful_shutdown


class TestGracefulShutdown:

    def test_restores_original_handlers(self):
        manifest = MagicMock()
        console = Console(file=MagicMock())
        original_int = signal.getsignal(signal.SIGINT)
        original_term = signal.getsignal(signal.SIGTERM)

        with _graceful_shutdown(manifest, "/tmp/test-session", console):
            assert signal.getsignal(signal.SIGINT) != original_int
            assert signal.getsignal(signal.SIGTERM) != original_term

        assert signal.getsignal(signal.SIGINT) == original_int
        assert signal.getsignal(signal.SIGTERM) == original_term

    def test_restores_on_exception(self):
        manifest = MagicMock()
        console = Console(file=MagicMock())
        original_int = signal.getsignal(signal.SIGINT)

        with pytest.raises(ValueError):
            with _graceful_shutdown(manifest, "/tmp/test-session", console):
                raise ValueError("test error")

        assert signal.getsignal(signal.SIGINT) == original_int


class TestEnsureDirs:

    def test_ensure_dirs_creates_directories(self, tmp_path, monkeypatch):
        monkeypatch.setattr("stackbox.config.XDG_CONFIG_HOME", tmp_path / "config")
        monkeypatch.setattr("stackbox.config.XDG_DATA_HOME", tmp_path / "data")
        monkeypatch.setattr("stackbox.config.XDG_CACHE_HOME", tmp_path / "cache")
        monkeypatch.setattr("stackbox.config.SESSIONS_DIR", tmp_path / "data" / "sessions")
        monkeypatch.setattr("stackbox.config.REPO_CACHE_DIR", tmp_path / "cache" / "repos")
        monkeypatch.setattr("stackbox.config.LOG_DIR", tmp_path / "data" / "logs")

        from stackbox.config import ensure_dirs
        ensure_dirs()

        assert (tmp_path / "config").is_dir()
        assert (tmp_path / "data").is_dir()
        assert (tmp_path / "cache").is_dir()
        assert (tmp_path / "data" / "sessions").is_dir()
        assert (tmp_path / "cache" / "repos").is_dir()
        assert (tmp_path / "data" / "logs").is_dir()
