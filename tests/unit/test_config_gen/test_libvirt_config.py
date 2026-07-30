from stackbox.config_gen.libvirt_config import LibvirtConfigGenerator


class TestLibvirtConfigGenerator:

    def test_generates_two_files(self, vmedia_job_config, port_manager):
        gen = LibvirtConfigGenerator(vmedia_job_config, port_manager)
        files = gen.generate()
        assert set(files.keys()) == {"libvirtd.conf", "qemu.conf"}

    def test_libvirtd_disables_tls(self, vmedia_job_config, port_manager):
        gen = LibvirtConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["libvirtd.conf"]
        assert "listen_tls = 0" in content

    def test_libvirtd_disables_tcp(self, vmedia_job_config, port_manager):
        gen = LibvirtConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["libvirtd.conf"]
        assert "listen_tcp = 0" in content

    def test_libvirtd_no_auth(self, vmedia_job_config, port_manager):
        gen = LibvirtConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["libvirtd.conf"]
        assert 'auth_unix_rw = "none"' in content

    def test_qemu_runs_as_root(self, vmedia_job_config, port_manager):
        gen = LibvirtConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["qemu.conf"]
        assert 'user = "root"' in content
        assert 'group = "root"' in content

    def test_qemu_cgroup_includes_kvm(self, vmedia_job_config, port_manager):
        gen = LibvirtConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["qemu.conf"]
        assert "/dev/kvm" in content

    def test_qemu_cgroup_includes_tun(self, vmedia_job_config, port_manager):
        gen = LibvirtConfigGenerator(vmedia_job_config, port_manager)
        content = gen.generate()["qemu.conf"]
        assert "/dev/net/tun" in content
