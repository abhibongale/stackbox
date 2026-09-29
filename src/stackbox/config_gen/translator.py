from __future__ import annotations

from stackbox.config_gen.mapping import DEVSTACK_TO_SERVICE


class DevStackTranslator:

    def __init__(self, mapping: dict | None = None):
        self.mapping = mapping if mapping is not None else DEVSTACK_TO_SERVICE

    def translate(self, localrc: dict[str, str]) -> dict[str, dict[str, dict[str, str]]]:
        result: dict[str, dict[str, dict[str, str]]] = {}

        for key, value in localrc.items():
            target = self.mapping.get(key)
            if target is None:
                continue
            # In devstack, an empty string means "unset — use the service's own
            # default". Never write it to a config file; doing so causes Ironic
            # (and other services) to look up an interface/driver named "" and crash.
            if value == "":
                continue

            service, section, option = target
            result.setdefault(service, {}).setdefault(section, {})[option] = value

        return result

    def unmapped_keys(self, localrc: dict[str, str]) -> set[str]:
        return {k for k in localrc if k not in self.mapping}
