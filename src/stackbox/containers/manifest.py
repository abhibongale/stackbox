from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

MANIFEST_FILE = "manifest.json"


@dataclass
class SessionManifest:
    session_id: str
    containers: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    libvirt_domains: list[str] = field(default_factory=list)
    ovs_bridges: list[str] = field(default_factory=list)
    configs_dir: str = ""

    def record_container(self, name: str) -> None:
        if name not in self.containers:
            self.containers.append(name)

    def record_volume(self, name: str) -> None:
        if name not in self.volumes:
            self.volumes.append(name)

    def record_domain(self, name: str) -> None:
        if name not in self.libvirt_domains:
            self.libvirt_domains.append(name)

    def record_bridge(self, name: str) -> None:
        if name not in self.ovs_bridges:
            self.ovs_bridges.append(name)

    def save(self, session_dir: Path) -> None:
        session_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "containers": self.containers,
            "volumes": self.volumes,
            "libvirt_domains": self.libvirt_domains,
            "ovs_bridges": self.ovs_bridges,
            "configs_dir": self.configs_dir,
        }
        path = session_dir / MANIFEST_FILE
        path.write_text(json.dumps(data, indent=2) + "\n")
        log.debug("Manifest saved to %s", path)

    @classmethod
    def load(cls, session_dir: Path) -> SessionManifest:
        path = session_dir / MANIFEST_FILE
        if not path.exists():
            raise FileNotFoundError(f"No manifest found at {path}")
        data = json.loads(path.read_text())
        return cls(
            session_id=data["session_id"],
            containers=data.get("containers", []),
            volumes=data.get("volumes", []),
            libvirt_domains=data.get("libvirt_domains", []),
            ovs_bridges=data.get("ovs_bridges", []),
            configs_dir=data.get("configs_dir", ""),
        )
