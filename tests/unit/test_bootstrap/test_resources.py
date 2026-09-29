from unittest.mock import MagicMock

from stackbox.bootstrap import resources
from stackbox.exceptions import ContainerError


class TestDownloadInContainer:

    def test_success_returns_exec_result(self):
        backend = MagicMock()
        backend.exec.return_value = (0, "")

        ec, out = resources._download_in_container(
            backend, "https://x/y.img", "/tmp/y.img", timeout=1800
        )

        assert ec == 0
        # runs python3 inside the deploy CONTAINER with the given timeout
        args, kwargs = backend.exec.call_args
        assert args[0] == resources.CONTAINER
        assert args[1][:2] == ["python3", "-c"]
        assert kwargs["timeout"] == 1800

    def test_generated_script_is_valid_python(self):
        backend = MagicMock()
        backend.exec.return_value = (0, "")

        resources._download_in_container(backend, "https://x/y.img", "/tmp/y.img")

        script = backend.exec.call_args[0][1][2]
        compile(script, "<generated>", "exec")  # raises SyntaxError if broken
        assert "urlopen" in script
        assert "setdefaulttimeout" in script

    def test_timeout_degrades_gracefully(self):
        # A docker exec timeout raises ContainerError; the helper must catch it
        # and return a non-zero code so the caller degrades instead of aborting
        # the whole bootstrap.
        backend = MagicMock()
        backend.exec.side_effect = ContainerError("Command timed out: ...")

        ec, out = resources._download_in_container(
            backend, "https://x/y.img", "/tmp/y.img"
        )

        assert ec == 1
        assert "timed out" in out
