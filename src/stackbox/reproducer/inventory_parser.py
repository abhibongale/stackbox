from __future__ import annotations

import requests
import yaml

from stackbox.exceptions import ZuulAPIError
from stackbox.zuul.inheritance import deep_merge


class InventoryParser:
    def parse(self, log_url: str) -> dict:
        inventory_url = f"{log_url.rstrip('/')}/zuul-info/inventory.yaml"
        try:
            response = requests.get(inventory_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ZuulAPIError(
                f"Failed to fetch inventory from {inventory_url}: {exc}"
            ) from exc
        return yaml.safe_load(response.text)

    def extract_hostvars(self, inventory: dict) -> dict:
        all_section = inventory.get("all", {})
        group_vars = dict(all_section.get("vars", {}))

        hosts = all_section.get("hosts", {})
        if not hosts:
            children = all_section.get("children", {})
            for group in children.values():
                hosts = group.get("hosts", {})
                if hosts:
                    break

        if not hosts:
            return group_vars

        host_vars = dict(next(iter(hosts.values())))
        return deep_merge(group_vars, host_vars)
