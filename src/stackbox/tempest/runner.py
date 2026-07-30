from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from stackbox.containers.backend import ContainerBackend
from stackbox.exceptions import BootstrapError

log = logging.getLogger(__name__)

CONTAINER = "stackbox-tempest"


class TempestRunner:

    def __init__(self, backend: ContainerBackend):
        self.backend = backend

    def run(
        self,
        tempest_conf: Path,
        test_regex: str,
        results_dir: Path,
        image: str = "stackbox-tempest:local",
    ) -> int:
        results_dir.mkdir(parents=True, exist_ok=True)

        from stackbox.models.container import ContainerSpec, VolumeMount

        spec = ContainerSpec(
            name=CONTAINER,
            image=image,
            volumes=[
                VolumeMount(
                    source=str(tempest_conf),
                    target="/opt/tempest/workspace/etc/tempest.conf",
                    options="ro,z",
                ),
                VolumeMount(
                    source=str(results_dir),
                    target="/opt/tempest/workspace/tempest_results",
                    options="z",
                ),
            ],
            command=["tempest", "run", "--regex", test_regex],
        )

        log.info("Starting Tempest: regex=%s", test_regex)

        try:
            self.backend.remove(CONTAINER, force=True)
        except Exception:
            pass

        cmd = self._build_run_cmd(spec)
        log.info("Running: %s", " ".join(cmd))

        proc = subprocess.Popen(
            cmd, stdout=sys.stdout, stderr=sys.stderr,
        )
        exit_code = proc.wait()

        if exit_code == 0:
            log.info("Tempest passed")
        else:
            log.warning("Tempest failed with exit code %d", exit_code)

        self._collect_results(results_dir)
        return exit_code

    def _build_run_cmd(self, spec: ContainerSpec) -> list[str]:
        cmd = [
            "podman", "run", "--rm",
            "--name", spec.name,
            "--network", spec.network,
        ]
        for vol in spec.volumes:
            mount_str = f"{vol.source}:{vol.target}"
            if vol.options:
                mount_str += f":{vol.options}"
            cmd.extend(["-v", mount_str])
        cmd.append(spec.image)
        if spec.command:
            cmd.extend(spec.command)
        return cmd

    def _collect_results(self, results_dir: Path) -> None:
        for f in results_dir.iterdir():
            log.info("Tempest result: %s (%d bytes)", f.name, f.stat().st_size)
