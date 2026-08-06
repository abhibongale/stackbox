from __future__ import annotations

from stackbox.config_gen.base import ServiceConfigGenerator


class SwiftConfigGenerator(ServiceConfigGenerator):

    def generate(self) -> dict[str, str]:
        lr = self.job.devstack_localrc
        swift_hash = lr.get("SWIFT_HASH", "1234123412341234")
        swift_port = self.ports.get("swift")

        content = f"""\
[DEFAULT]
bind_ip = 0.0.0.0
bind_port = {swift_port}
workers = 1

[pipeline:main]
pipeline = catch_errors healthcheck proxy-logging cache bulk tempurl slo dlo ratelimit tempauth proxy-logging proxy-server

[app:proxy-server]
use = egg:swift#proxy
account_autocreate = true

[filter:tempauth]
use = egg:swift#tempauth
user_admin_admin = admin .admin .reseller_admin
user_test_tester = testing .admin
reseller_prefix = AUTH

[filter:tempurl]
use = egg:swift#tempurl

[filter:cache]
use = egg:swift#memcache
memcache_servers = localhost:{self.ports.get('memcached')}

[filter:catch_errors]
use = egg:swift#catch_errors

[filter:healthcheck]
use = egg:swift#healthcheck

[filter:proxy-logging]
use = egg:swift#proxy_logging

[filter:bulk]
use = egg:swift#bulk

[filter:slo]
use = egg:swift#slo

[filter:dlo]
use = egg:swift#dlo

[filter:ratelimit]
use = egg:swift#ratelimit

[swift-hash]
swift_hash_path_suffix = {swift_hash}
"""
        swift_conf = f"""\
[swift-hash]
swift_hash_path_suffix = {swift_hash}
swift_hash_path_prefix = {swift_hash}
"""
        return {"proxy-server.conf": content, "swift.conf": swift_conf}
