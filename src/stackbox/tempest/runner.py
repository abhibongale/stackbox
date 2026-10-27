from __future__ import annotations

import logging
import re
import shlex
import subprocess
import sys
from pathlib import Path

from stackbox.containers.backend import ContainerBackend
from stackbox.containers.manifest import SessionManifest
from stackbox.exceptions import BootstrapError

log = logging.getLogger(__name__)

CONTAINER = "stackbox-tempest"
# stestr's "Totals" block, e.g. " - Passed: 0" / " - Skipped: 1".
_TOTALS_LINE = re.compile(r"^ - (Passed|Skipped|Failed): (\d+)\s*$")
WORKSPACE = "/opt/tempest/workspace"


class TempestRunner:

    def __init__(self, backend: ContainerBackend, manifest: SessionManifest | None = None):
        self.backend = backend
        self.manifest = manifest
        self.all_skipped = False

    def run(
        self,
        tempest_conf: Path,
        test_regex: str,
        results_dir: Path,
        image: str = "localhost/stackbox-tempest:local",
    ) -> int:
        results_dir.mkdir(parents=True, exist_ok=True)

        from stackbox.models.container import ContainerSpec, VolumeMount

        init_script = (
            f"tempest init /tmp/tempest-init 2>/dev/null; "
            f"mkdir -p {WORKSPACE}/etc; "
            f"cp /tmp/tempest-init/.stestr.conf {WORKSPACE}/; "
            f"cp /tmp/stackbox-tempest.conf {WORKSPACE}/etc/tempest.conf; "
            f"cd {WORKSPACE}; "
            f"stestr init 2>/dev/null; "
            f"tempest run --regex {shlex.quote(test_regex)}"
        )

        spec = ContainerSpec(
            name=CONTAINER,
            image=image,
            entrypoint=["/bin/bash"],
            volumes=[
                VolumeMount(
                    source=str(tempest_conf),
                    target="/tmp/stackbox-tempest.conf",
                    options="ro,z",
                ),
                VolumeMount(
                    source=str(results_dir),
                    target=f"{WORKSPACE}/tempest_results",
                    options="z",
                ),
            ],
            command=["-c", init_script],
        )

        log.info("Starting Tempest: regex=%s", test_regex)

        try:
            self.backend.remove(CONTAINER, force=True)
        except Exception:
            pass

        if self.manifest:
            self.manifest.record_container(CONTAINER)

        cmd = self._build_run_cmd(spec)
        log.info("Running: %s", " ".join(cmd))

        # Tee stdout so the stestr totals can be inspected after the run.
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=sys.stderr, text=True,
        )
        totals: dict[str, int] = {}
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            match = _TOTALS_LINE.match(line)
            if match:
                totals[match.group(1)] = int(match.group(2))
        exit_code = proc.wait()
        # stestr exits 1 when nothing passed even if nothing failed; that is
        # almost always a config gap (a feature the tests need isn't enabled).
        self.all_skipped = (
            totals.get("Passed") == 0
            and totals.get("Failed") == 0
            and totals.get("Skipped", 0) > 0
        )

        if exit_code == 0:
            log.info("Tempest passed")
        else:
            log.warning("Tempest failed with exit code %d", exit_code)

        self._collect_results(results_dir)
        return exit_code

    def _build_run_cmd(self, spec: ContainerSpec) -> list[str]:
        cmd = [
            "docker", "run",
            "--name", spec.name,
            "--network", spec.network,
        ]
        if spec.entrypoint:
            cmd.extend(["--entrypoint", spec.entrypoint[0]])
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
