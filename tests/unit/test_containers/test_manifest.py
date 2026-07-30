import json

import pytest

from stackbox.containers.manifest import SessionManifest


class TestSessionManifest:

    def test_record_container(self):
        m = SessionManifest(session_id="test-1")
        m.record_container("stackbox-mariadb")
        assert "stackbox-mariadb" in m.containers

    def test_record_container_dedup(self):
        m = SessionManifest(session_id="test-1")
        m.record_container("stackbox-mariadb")
        m.record_container("stackbox-mariadb")
        assert m.containers.count("stackbox-mariadb") == 1

    def test_record_volume(self):
        m = SessionManifest(session_id="test-1")
        m.record_volume("stackbox-libvirt-sock")
        assert "stackbox-libvirt-sock" in m.volumes

    def test_record_domain(self):
        m = SessionManifest(session_id="test-1")
        m.record_domain("stackbox-bm-0")
        assert "stackbox-bm-0" in m.libvirt_domains

    def test_record_bridge(self):
        m = SessionManifest(session_id="test-1")
        m.record_bridge("brbm")
        assert "brbm" in m.ovs_bridges

    def test_save_and_load_roundtrip(self, tmp_path):
        m = SessionManifest(
            session_id="test-42",
            containers=["stackbox-mariadb", "stackbox-keystone"],
            volumes=["stackbox-libvirt-sock"],
            libvirt_domains=["stackbox-bm-0"],
            ovs_bridges=["brbm"],
            configs_dir="/tmp/configs",
        )
        m.save(tmp_path)
        loaded = SessionManifest.load(tmp_path)

        assert loaded.session_id == "test-42"
        assert loaded.containers == ["stackbox-mariadb", "stackbox-keystone"]
        assert loaded.volumes == ["stackbox-libvirt-sock"]
        assert loaded.libvirt_domains == ["stackbox-bm-0"]
        assert loaded.ovs_bridges == ["brbm"]
        assert loaded.configs_dir == "/tmp/configs"

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SessionManifest.load(tmp_path)

    def test_save_creates_directory(self, tmp_path):
        subdir = tmp_path / "nested" / "dir"
        m = SessionManifest(session_id="test-1")
        m.save(subdir)
        assert (subdir / "manifest.json").exists()
