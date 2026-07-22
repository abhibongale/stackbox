import click

from stackbox.constants import DEFAULT_RELEASE


@click.group()
@click.version_option(package_name="stackbox")
def cli():
    """STACKBOX — Run OpenStack Ironic Zuul CI jobs locally."""


@cli.command()
@click.option("--release", default=DEFAULT_RELEASE, help="Kolla image release tag")
def init(release):
    """Validate host prerequisites and pull base images."""
    click.echo("stackbox init — not yet implemented")


@cli.command()
@click.argument("job_name")
@click.option(
    "--local-repo",
    multiple=True,
    help="service=path pairs for local builds (e.g. ironic=./ironic)",
)
@click.option("--port-offset", type=int, default=0, help="Shift all service ports by N")
@click.option("--offline", is_flag=True, help="Resolve from local zuul.d/ files")
@click.option("--dry-run", is_flag=True, help="Show config without deploying")
@click.option("--skip-tempest", is_flag=True, help="Skip test execution")
@click.option("--keep", is_flag=True, help="Keep containers running after tests")
@click.option("--release", default=DEFAULT_RELEASE, help="Kolla image release tag")
def run(job_name, local_repo, port_offset, offline, dry_run, skip_tempest, keep, release):
    """Run a Zuul CI job locally."""
    click.echo(f"stackbox run {job_name} — not yet implemented")


@cli.command()
@click.argument("build_url")
@click.option("--local-repo", multiple=True, help="service=path pairs for local builds")
@click.option("--port-offset", type=int, default=0, help="Shift all service ports by N")
@click.option("--dry-run", is_flag=True, help="Show config without deploying")
@click.option("--keep", is_flag=True, help="Keep containers running after tests")
def reproduce(build_url, local_repo, port_offset, dry_run, keep):
    """Reproduce a CI job from a Zuul build URL."""
    click.echo(f"stackbox reproduce {build_url} — not yet implemented")


@cli.command("list")
@click.option("--project", default="openstack/ironic", help="OpenStack project")
@click.option("--pipeline", default=None, help="Filter by pipeline (e.g. gate, check)")
def list_jobs(project, pipeline):
    """List available Zuul jobs for a project."""
    click.echo(f"stackbox list --project {project} — not yet implemented")


@cli.command()
def status():
    """Show running stackbox containers."""
    click.echo("stackbox status — not yet implemented")


@cli.command()
@click.argument("service")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def logs(service, follow):
    """Tail logs from a service container."""
    click.echo(f"stackbox logs {service} — not yet implemented")


@cli.command("exec")
@click.argument("service")
@click.argument("cmd", nargs=-1, required=True)
def exec_cmd(service, cmd):
    """Execute a command in a service container."""
    click.echo(f"stackbox exec {service} — not yet implemented")


@cli.command()
@click.argument("job_name")
@click.option("--port-offset", type=int, default=0, help="Shift all service ports by N")
@click.option("--offline", is_flag=True, help="Resolve from local zuul.d/ files")
def config(job_name, port_offset, offline):
    """Generate service configs without deploying."""
    click.echo(f"stackbox config {job_name} — not yet implemented")


@cli.command()
@click.option("--all", "remove_all", is_flag=True, help="Also remove volumes and images")
def clean(remove_all):
    """Clean up all stackbox resources."""
    click.echo("stackbox clean — not yet implemented")
