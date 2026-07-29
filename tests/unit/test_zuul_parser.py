import pytest

from stackbox.models.zuul import ZuulJobDefinition
from stackbox.zuul.parser import OfflineJobParser, _parse_job_entry


class TestParseJobEntry:
    def test_basic_job(self):
        entry = {
            "name": "test-job",
            "parent": "base-job",
            "vars": {
                "devstack_localrc": {"A": "1"},
                "devstack_services": {"svc": True},
                "tempest_test_regex": "test_foo",
            },
        }
        job = _parse_job_entry(entry)
        assert job.name == "test-job"
        assert job.parent == "base-job"
        assert job.variables.devstack_localrc == {"A": "1"}
        assert job.variables.devstack_services == {"svc": True}
        assert job.variables.tempest_test_regex == "test_foo"

    def test_coerces_localrc_values(self):
        entry = {
            "name": "test-job",
            "vars": {
                "devstack_localrc": {"INT_VAL": 42, "BOOL_VAL": True},
            },
        }
        job = _parse_job_entry(entry)
        assert job.variables.devstack_localrc == {"INT_VAL": "42", "BOOL_VAL": "True"}

    def test_no_parent(self):
        entry = {"name": "root-job"}
        job = _parse_job_entry(entry)
        assert job.parent is None

    def test_run_as_string(self):
        entry = {"name": "test-job", "run": "playbooks/run.yaml"}
        job = _parse_job_entry(entry)
        assert job.playbooks == [{"run": "playbooks/run.yaml"}]

    def test_run_as_list(self):
        entry = {"name": "test-job", "run": ["pb1.yaml", "pb2.yaml"]}
        job = _parse_job_entry(entry)
        assert len(job.playbooks) == 2


class TestOfflineJobParser:
    def test_parse_jobs_from_yaml(self, tmp_path):
        zuul_d = tmp_path / "zuul.d"
        zuul_d.mkdir()
        (zuul_d / "jobs.yaml").write_text("""
- job:
    name: base-job
    vars:
      devstack_localrc:
        A: "1"

- job:
    name: child-job
    parent: base-job
    vars:
      devstack_localrc:
        B: "2"

- project:
    name: openstack/test
""")
        parser = OfflineJobParser.__new__(OfflineJobParser)
        jobs = parser.parse_jobs(tmp_path)

        assert "base-job" in jobs
        assert "child-job" in jobs
        assert len(jobs) == 2
        assert jobs["child-job"].parent == "base-job"

    def test_ignores_non_job_entries(self, tmp_path):
        zuul_d = tmp_path / "zuul.d"
        zuul_d.mkdir()
        (zuul_d / "project.yaml").write_text("""
- project:
    name: openstack/test
- project-template:
    name: some-template
- job:
    name: the-only-job
""")
        parser = OfflineJobParser.__new__(OfflineJobParser)
        jobs = parser.parse_jobs(tmp_path)
        assert len(jobs) == 1
        assert "the-only-job" in jobs

    def test_handles_dot_zuul_yaml(self, tmp_path):
        (tmp_path / ".zuul.yaml").write_text("""
- job:
    name: dot-zuul-job
""")
        parser = OfflineJobParser.__new__(OfflineJobParser)
        jobs = parser.parse_jobs(tmp_path)
        assert "dot-zuul-job" in jobs

    def test_handles_yml_extension(self, tmp_path):
        zuul_d = tmp_path / "zuul.d"
        zuul_d.mkdir()
        (zuul_d / "jobs.yml").write_text("""
- job:
    name: yml-job
""")
        parser = OfflineJobParser.__new__(OfflineJobParser)
        jobs = parser.parse_jobs(tmp_path)
        assert "yml-job" in jobs

    def test_skips_invalid_yaml(self, tmp_path):
        zuul_d = tmp_path / "zuul.d"
        zuul_d.mkdir()
        (zuul_d / "bad.yaml").write_text(": invalid: yaml: {{")
        (zuul_d / "good.yaml").write_text("""
- job:
    name: good-job
""")
        parser = OfflineJobParser.__new__(OfflineJobParser)
        jobs = parser.parse_jobs(tmp_path)
        assert "good-job" in jobs

    def test_empty_dir(self, tmp_path):
        parser = OfflineJobParser.__new__(OfflineJobParser)
        jobs = parser.parse_jobs(tmp_path)
        assert jobs == {}
