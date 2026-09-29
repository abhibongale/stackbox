from __future__ import annotations

import json
import logging
import signal
import subprocess
import sys
import time

from stackbox.containers.backend import ContainerBackend
from stackbox.exceptions import ContainerError
from stackbox.models.container import ContainerSpec

log = logging.getLogger(__name__)

# BuildKit leaves a build ref locked when a build is killed hard (SIGKILL on
# timeout, or an interrupted run) before it can tell the daemon to cancel. The
# lease releases on its own after ~35s, so a "locked ... unavailable" failure
# is transient and worth retrying rather than aborting the whole run.
_BUILD_LOCK_MARKER = "locked for"
_BUILD_MAX_ATTEMPTS = 3

# Docker's containerd image store (the default in Docker 25+, storage driver
# "overlayfs" / io.containerd.snapshotter.v1) can commit an empty/corrupt
# snapshot for a completed layer. The layer's files then vanish, so the next
# step's `RUN` can't even find /bin/sh and runc aborts during container init.
# The build fails with a cryptic error pointing at whatever command was next,
# not at the real cause — so detect the runc-init signature and surface an
# actionable message instead.
_SNAPSHOTTER_CORRUPTION_MARKERS = (
    "error during container init",
    "no such file or directory",
)
_SNAPSHOTTER_FIX_HINT = (
    "Docker's containerd image store committed an empty layer, so the build "
    "environment is missing its base files (runc could not find /bin/sh). "
    "This is a known instability of the containerd snapshotter, not a "
    "stackbox or Containerfile bug.\n"
    "Fix: disable the containerd snapshotter and restart Docker. Add to "
    "/etc/docker/daemon.json:\n"
    '  {"features": {"containerd-snapshotter": false}}\n'
    "then `sudo systemctl restart docker` and confirm "
    "`docker info --format '{{.Driver}}'` prints `overlay2`."
)


class DockerBackend(ContainerBackend):

    def _run_cmd(self, cmd: list[str], check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess:
        log.debug("docker: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContainerError(f"Command timed out: {' '.join(cmd)}") from exc
        except FileNotFoundError:
            raise ContainerError("docker not found. Install docker first.")

        if check and result.returncode != 0:
            raise ContainerError(
                f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n"
                f"{result.stderr.strip()}"
            )
        return result

    def run(self, spec: ContainerSpec) -> str:
        self._run_cmd(
            ["docker", "rm", "-f", spec.name], check=False
        )
        cmd = [
            "docker", "run", "-d",
            "--name", spec.name,
            "--network", spec.network,
        ]

        if spec.privileged:
            cmd.append("--privileged")

        if spec.restart_policy:
            cmd.extend(["--restart", spec.restart_policy])

        if spec.pid_mode:
            cmd.extend(["--pid", spec.pid_mode])

        if spec.user:
            cmd.extend(["--user", spec.user])

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
        self._run_cmd(["docker", "stop", "-t", str(timeout), name], check=False)

    def remove(self, name: str, force: bool = False) -> None:
        cmd = ["docker", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(name)
        self._run_cmd(cmd, check=False)

    def exec(self, name: str, cmd: list[str], timeout: int = 300) -> tuple[int, str]:
        result = self._run_cmd(["docker", "exec", name] + cmd, check=False, timeout=timeout)
        output = result.stdout + result.stderr
        return result.returncode, output.strip()

    def logs(self, name: str, follow: bool = False, tail: int | None = None) -> str:
        cmd = ["docker", "logs"]
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
        result = self._run_cmd(["docker", "inspect", name])
        data = json.loads(result.stdout)
        return data[0] if data else {}

    def is_running(self, name: str) -> bool:
        result = self._run_cmd(
            ["docker", "inspect", "--format", "{{.State.Running}}", name],
            check=False,
        )
        return result.stdout.strip().lower() == "true"

    def list_containers(self, prefix: str = "") -> list[dict]:
        cmd = ["docker", "ps", "-a", "--format", "json"]
        if prefix:
            cmd.extend(["--filter", f"name={prefix}"])
        result = self._run_cmd(cmd, check=False)
        if not result.stdout.strip():
            return []
        return [json.loads(line) for line in result.stdout.strip().splitlines()]

    def pull_image(self, image: str) -> None:
        log.info("Pulling image %s", image)
        self._run_cmd(["docker", "pull", image], timeout=1800)

    def build_image(
        self,
        tag: str,
        context: str,
        containerfile: str,
        build_args: dict[str, str] | None = None,
    ) -> None:
        def make_cmd(no_cache: bool) -> list[str]:
            cmd = ["docker", "build", "-t", tag, "-f", containerfile]
            if no_cache:
                cmd.append("--no-cache")
            for key, value in (build_args or {}).items():
                cmd.extend(["--build-arg", f"{key}={value}"])
            cmd.append(context)  # context must stay last
            return cmd

        log.info("Building image %s", tag)

        # A poisoned layer gets cached, so a plain rebuild would just remount
        # it; force --no-cache once we've seen corruption to actually retry.
        no_cache = False
        for attempt in range(1, _BUILD_MAX_ATTEMPTS + 1):
            cmd = make_cmd(no_cache)
            result = self._run_build_cmd(cmd, timeout=1800)
            if result.returncode == 0:
                return

            stderr = result.stderr or ""
            corrupt = all(m in stderr for m in _SNAPSHOTTER_CORRUPTION_MARKERS)
            locked = _BUILD_LOCK_MARKER in stderr

            if (corrupt or locked) and attempt < _BUILD_MAX_ATTEMPTS:
                if corrupt:
                    # Intermittent empty-layer commit from the containerd
                    # snapshotter — usually clears on a fresh (uncached) build.
                    no_cache = True
                    wait = 2
                    log.warning(
                        "Build of %s hit containerd-snapshotter layer "
                        "corruption (attempt %d/%d); retrying with --no-cache",
                        tag, attempt, _BUILD_MAX_ATTEMPTS,
                    )
                else:
                    # Wait past the ~35s lease so the stale ref is released
                    # before we try again; back off a little on each retry.
                    wait = 40 * attempt
                    log.warning(
                        "Build of %s hit a locked BuildKit ref (attempt %d/%d); "
                        "retrying in %ds",
                        tag, attempt, _BUILD_MAX_ATTEMPTS, wait,
                    )
                time.sleep(wait)
                continue

            # Retries exhausted (or a non-retryable error). If it was the
            # snapshotter corruption, the host's image store is persistently
            # broken — point at the daemon fix rather than the misleading
            # command that happened to run when the layer went missing.
            if corrupt:
                raise ContainerError(
                    f"Failed to build {tag}: {_SNAPSHOTTER_FIX_HINT}\n\n"
                    f"Original error:\n{stderr.strip()}"
                )
            raise ContainerError(
                f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n"
                f"{stderr.strip()}"
            )

    def _run_build_cmd(
        self, cmd: list[str], timeout: int
    ) -> subprocess.CompletedProcess:
        """Run ``docker build`` so it can be cancelled gracefully.

        ``subprocess.run(timeout=...)`` sends SIGKILL when the timeout fires,
        which orphans the BuildKit ref (leaving it locked for the next build).
        Driving the process ourselves lets us send SIGINT first — which the
        docker CLI turns into a BuildKit cancel that releases the ref — and
        only fall back to SIGKILL if the build ignores it. The same path also
        cancels cleanly on a Ctrl-C during the build.
        """
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        except FileNotFoundError:
            raise ContainerError("docker not found. Install docker first.")

        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _, err = self._cancel_build(proc)
            raise ContainerError(
                f"Build timed out after {timeout}s: {' '.join(cmd)}\n"
                f"{(err or '').strip()}"
            )
        except KeyboardInterrupt:
            # The child already got SIGINT from the terminal; wait for it to
            # finish cancelling so it doesn't leave a locked ref behind, then
            # let the interrupt propagate.
            self._cancel_build(proc)
            raise

        return subprocess.CompletedProcess(cmd, proc.returncode, out, err)

    @staticmethod
    def _cancel_build(
        proc: subprocess.Popen, grace: int = 15
    ) -> tuple[str, str]:
        """Ask a running build to cancel and wait for it to release its ref.

        Escalates SIGINT -> SIGTERM -> SIGKILL, giving the docker CLI a chance
        to propagate the BuildKit cancel before resorting to a hard kill.
        """
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            try:
                proc.send_signal(sig)
            except ProcessLookupError:
                break
            try:
                return proc.communicate(timeout=grace)
            except subprocess.TimeoutExpired:
                continue
        return "", ""

    def create_volume(self, name: str) -> None:
        result = self._run_cmd(
            ["docker", "volume", "inspect", name], check=False
        )
        if result.returncode == 0:
            log.debug("Volume %s already exists, reusing", name)
            return
        self._run_cmd(["docker", "volume", "create", name])

    def list_volumes(self, prefix: str = "") -> list[str]:
        cmd = ["docker", "volume", "ls", "--format", "{{.Name}}"]
        if prefix:
            cmd.extend(["--filter", f"name={prefix}"])
        result = self._run_cmd(cmd, check=False)
        return [line for line in result.stdout.strip().splitlines() if line]

    def remove_volume(self, name: str) -> bool:
        result = self._run_cmd(["docker", "volume", "rm", "-f", name], check=False)
        if result.returncode != 0:
            log.warning(
                "Failed to remove volume %s (still in use?): %s",
                name, result.stderr.strip(),
            )
            return False
        return True
