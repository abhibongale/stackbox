from __future__ import annotations

import json
import logging
import subprocess
import sys

from stackbox.containers.backend import ContainerBackend
from stackbox.exceptions import ContainerError
from stackbox.models.container import ContainerSpec

log = logging.getLogger(__name__)


class PodmanBackend(ContainerBackend):

    def _run_cmd(self, cmd: list[str], check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess:
        log.debug("podman: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContainerError(f"Command timed out: {' '.join(cmd)}") from exc
        except FileNotFoundError:
            raise ContainerError("podman not found. Install podman first.")

        if check and result.returncode != 0:
            raise ContainerError(
                f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n"
                f"{result.stderr.strip()}"
            )
        return result

    def run(self, spec: ContainerSpec) -> str:
        self._run_cmd(
            ["podman", "rm", "-f", spec.name], check=False
        )
        cmd = [
            "podman", "run", "-d",
            "--name", spec.name,
            "--network", spec.network,
        ]

        if spec.privileged:
            cmd.append("--privileged")

        for opt in spec.security_opts:
            cmd.extend(["--security-opt", opt])

        for vol in spec.volumes:
            mount_str = f"{vol.source}:{vol.target}"
            if vol.options:
                mount_str += f":{vol.options}"
            cmd.extend(["-v", mount_str])

        for key, value in spec.environment.items():
            cmd.extend(["-e", f"{key}={value}"])

        if spec.entrypoint is not None:
            cmd.extend(["--entrypoint", json.dumps(spec.entrypoint)])

        cmd.extend(spec.extra_args)
        cmd.append(spec.image)

        if spec.command is not None:
            cmd.extend(spec.command)

        result = self._run_cmd(cmd)
        container_id = result.stdout.strip()
        log.info("Started container %s (%s)", spec.name, container_id[:12])
        return container_id

    def stop(self, name: str, timeout: int = 10) -> None:
        self._run_cmd(["podman", "stop", "-t", str(timeout), name], check=False)

    def remove(self, name: str, force: bool = False) -> None:
        cmd = ["podman", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(name)
        self._run_cmd(cmd, check=False)

    def exec(self, name: str, cmd: list[str], timeout: int = 300) -> tuple[int, str]:
        result = self._run_cmd(["podman", "exec", name] + cmd, check=False, timeout=timeout)
        output = result.stdout + result.stderr
        return result.returncode, output.strip()

    def logs(self, name: str, follow: bool = False, tail: int | None = None) -> str:
        cmd = ["podman", "logs"]
        if tail is not None:
            cmd.extend(["--tail", str(tail)])
        if follow:
            cmd.append("-f")
            cmd.append(name)
            proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            try:
                proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
            return ""
        cmd.append(name)
        result = self._run_cmd(cmd, check=False)
        return result.stdout + result.stderr

    def inspect(self, name: str) -> dict:
        result = self._run_cmd(["podman", "inspect", name])
        data = json.loads(result.stdout)
        return data[0] if data else {}

    def is_running(self, name: str) -> bool:
        result = self._run_cmd(
            ["podman", "inspect", "--format", "{{.State.Running}}", name],
            check=False,
        )
        return result.stdout.strip().lower() == "true"

    def list_containers(self, prefix: str = "") -> list[dict]:
        cmd = ["podman", "ps", "-a", "--format", "json"]
        if prefix:
            cmd.extend(["--filter", f"name={prefix}"])
        result = self._run_cmd(cmd, check=False)
        if not result.stdout.strip():
            return []
        return json.loads(result.stdout)

    def pull_image(self, image: str) -> None:
        log.info("Pulling image %s", image)
        self._run_cmd(["podman", "pull", image], timeout=1800)

    def build_image(
        self,
        tag: str,
        context: str,
        containerfile: str,
        build_args: dict[str, str] | None = None,
    ) -> None:
        cmd = ["podman", "build", "-t", tag, "-f", containerfile]
        for key, value in (build_args or {}).items():
            cmd.extend(["--build-arg", f"{key}={value}"])
        cmd.append(context)
        log.info("Building image %s", tag)
        self._run_cmd(cmd, timeout=1800)

    def create_volume(self, name: str) -> None:
        result = self._run_cmd(
            ["podman", "volume", "exists", name], check=False
        )
        if result.returncode == 0:
            log.debug("Volume %s already exists, reusing", name)
            return
        self._run_cmd(["podman", "volume", "create", name])

    def remove_volume(self, name: str) -> None:
        self._run_cmd(["podman", "volume", "rm", "-f", name], check=False)
