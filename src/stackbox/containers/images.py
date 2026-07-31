from __future__ import annotations

import logging
from pathlib import Path

from stackbox.constants import KOLLA_IMAGES, KOLLA_REGISTRY, METAL3_IMAGES, METAL3_REGISTRY
from stackbox.containers.backend import ContainerBackend

log = logging.getLogger(__name__)

CONTAINERFILES_DIR = Path(__file__).parent


class ImageManager:

    def __init__(self, backend: ContainerBackend, release: str):
        self.backend = backend
        self.release = release

    def kolla_image(self, service: str) -> str:
        image_name = KOLLA_IMAGES.get(service, service)
        return f"{KOLLA_REGISTRY}/{image_name}:{self.release}"

    def metal3_image(self, service: str) -> str:
        image_name = METAL3_IMAGES.get(service, service)
        return f"{METAL3_REGISTRY}/{image_name}:latest"

    def pull_kolla(self, services: list[str]) -> None:
        for svc in services:
            image = self.kolla_image(svc)
            log.info("Pulling Kolla image: %s", image)
            self.backend.pull_image(image)

    def pull_metal3(self, services: list[str]) -> None:
        for svc in services:
            image = self.metal3_image(svc)
            log.info("Pulling Metal3 image: %s", image)
            self.backend.pull_image(image)

    def build_local(self, service: str, source_path: str, containerfile: str) -> str:
        tag = f"stackbox-{service}:local"
        self.backend.build_image(
            tag=tag,
            context=source_path,
            containerfile=containerfile,
            build_args={"SERVICE_NAME": service},
        )
        return tag

    def build_local_repos(self, local_repos: dict[str, str]) -> dict[str, str]:
        from stackbox.exceptions import ImageBuildError

        overrides: dict[str, str] = {}
        containerfile = str(CONTAINERFILES_DIR / "Containerfile.service-dev")
        for service, source_path in local_repos.items():
            log.info("Building local image for %s from %s", service, source_path)
            try:
                tag = self.build_local(service, source_path, containerfile)
            except Exception as exc:
                raise ImageBuildError(
                    f"Failed to build {service} from {source_path}: {exc}"
                ) from exc
            overrides[service] = tag
        return overrides

    def build_tempest(
        self,
        context: str,
        containerfile: str,
        plugin_source: str | None = None,
    ) -> str:
        tag = "stackbox-tempest:local"
        build_args = {}
        if plugin_source:
            build_args["TEMPEST_PLUGIN_SOURCE"] = plugin_source
        self.backend.build_image(
            tag=tag,
            context=context,
            containerfile=containerfile,
            build_args=build_args,
        )
        return tag
