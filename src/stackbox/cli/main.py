import click
from rich.console import Console
from rich.table import Table

from stackbox.config import REPO_CACHE_DIR, SESSIONS_DIR
from stackbox.constants import DEFAULT_RELEASE


def _parse_local_repos(local_repo: tuple[str, ...]) -> dict[str, str]:
    repos = {}
    for entry in local_repo:
        if "=" not in entry:
            raise click.BadParameter(
                f"Invalid --local-repo format: '{entry}'. Use service=path."
            )
        service, path = entry.split("=", 1)
        repos[service.strip()] = path.strip()
    return repos


def _resolve_job(job_name, offline, project="openstack/ironic", branch="master", pipeline="gate"):
    if offline:
        from stackbox.zuul.parser import OfflineJobParser
        from stackbox.zuul.repo_cache import RepoCache

        cache = RepoCache(REPO_CACHE_DIR)
        cache.ensure_repos(branch=branch)
        parser = OfflineJobParser(cache)
        return parser.resolve(job_name, project=project, branch=branch, pipeline=pipeline)
    else:
        from stackbox.zuul.api import ZuulClient
        from stackbox.zuul.freeze import FreezeJobResolver

        client = ZuulClient()
        resolver = FreezeJobResolver(client)
        return resolver.resolve(job_name, project=project, branch=branch, pipeline=pipeline)


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
    console = Console()
    local_repos = _parse_local_repos(local_repo)

    with console.status(f"Resolving job [bold]{job_name}[/bold]..."):
        config = _resolve_job(job_name, offline)

    config.local_repos = local_repos
    config.port_offset = port_offset

    if dry_run:
        console.print_json(config.model_dump_json(indent=2))
        return

    console.print(f"[green]Resolved job:[/green] {config.job_name}")
    console.print(f"  Boot interface: {config.boot_interface}")
    console.print(f"  BMC driver: {config.bmc_driver}")
    console.print(f"  VM count: {config.vm_specs.count}")
    console.print(f"  Tempest regex: {config.tempest_test_regex}")
    console.print("\n[yellow]Container orchestration not yet implemented (Phase 4)[/yellow]")


@cli.command()
@click.argument("build_url")
@click.option("--local-repo", multiple=True, help="service=path pairs for local builds")
@click.option("--port-offset", type=int, default=0, help="Shift all service ports by N")
@click.option("--dry-run", is_flag=True, help="Show config without deploying")
@click.option("--keep", is_flag=True, help="Keep containers running after tests")
def reproduce(build_url, local_repo, port_offset, dry_run, keep):
    """Reproduce a CI job from a Zuul build URL."""
    from stackbox.reproducer.build_fetcher import BuildFetcher
    from stackbox.reproducer.inventory_parser import InventoryParser
    from stackbox.reproducer.variable_extractor import VariableExtractor
    from stackbox.zuul.api import ZuulClient

    console = Console()
    local_repos = _parse_local_repos(local_repo)

    with console.status("Fetching build info..."):
        client = ZuulClient()
        fetcher = BuildFetcher(client)
        build_info = fetcher.fetch(build_url)

    console.print(f"[green]Build:[/green] {build_info.job_name} ({build_info.result})")
    console.print(f"  Project: {build_info.project}")
    console.print(f"  Branch: {build_info.branch}")

    with console.status("Fetching inventory..."):
        inv_parser = InventoryParser()
        inventory = inv_parser.parse(build_info.log_url)
        hostvars = inv_parser.extract_hostvars(inventory)

    with console.status("Extracting variables..."):
        extractor = VariableExtractor()
        config = extractor.extract(
            hostvars,
            job_name=build_info.job_name,
            project=build_info.project,
            branch=build_info.branch,
            pipeline=build_info.pipeline,
        )

    config.local_repos = local_repos
    config.port_offset = port_offset

    if dry_run:
        console.print_json(config.model_dump_json(indent=2))
        return

    console.print(f"\n[green]Resolved config:[/green]")
    console.print(f"  Boot interface: {config.boot_interface}")
    console.print(f"  BMC driver: {config.bmc_driver}")
    console.print(f"  VM count: {config.vm_specs.count}")
    console.print(f"  Tempest regex: {config.tempest_test_regex}")
    console.print("\n[yellow]Container orchestration not yet implemented (Phase 4)[/yellow]")


@cli.command("list")
@click.option("--project", default="openstack/ironic", help="OpenStack project")
@click.option("--pipeline", default=None, help="Filter by pipeline (e.g. gate, check)")
def list_jobs(project, pipeline):
    """List available Zuul jobs for a project."""
    from stackbox.zuul.api import ZuulClient

    console = Console()

    with console.status(f"Fetching jobs for [bold]{project}[/bold]..."):
        client = ZuulClient()
        jobs = client.list_jobs(project, pipeline=pipeline)

    if not jobs:
        console.print(f"No jobs found for {project}")
        return

    table = Table(title=f"Zuul Jobs — {project}")
    table.add_column("Job Name", style="cyan")
    table.add_column("Pipeline")
    table.add_column("Voting")

    seen = set()
    for job in jobs:
        key = (job["name"], job["pipeline"])
        if key in seen:
            continue
        seen.add(key)
        voting_style = "green" if job["voting"] else "yellow"
        table.add_row(
            job["name"],
            job["pipeline"],
            f"[{voting_style}]{'yes' if job['voting'] else 'no'}[/{voting_style}]",
        )

    console.print(table)


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
@click.option("--output-dir", type=click.Path(), default=None, help="Directory for generated configs")
@click.option("--json", "show_json", is_flag=True, help="Show resolved config JSON instead of generating files")
def config(job_name, port_offset, offline, output_dir, show_json):
    """Generate service configs for a Zuul job."""
    from pathlib import Path

    console = Console()

    with console.status(f"Resolving job [bold]{job_name}[/bold]..."):
        resolved = _resolve_job(job_name, offline)

    resolved.port_offset = port_offset

    if show_json:
        console.print_json(resolved.model_dump_json(indent=2))
        return

    from stackbox.config_gen import ConfigPipeline

    if output_dir:
        out = Path(output_dir)
    else:
        import uuid as _uuid
        session_id = _uuid.uuid4().hex[:12]
        out = SESSIONS_DIR / session_id / "configs"

    with console.status("Generating configs..."):
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(resolved, out)

    console.print(f"[green]Generated {len(generated)} config files in:[/green] {out}")
    for f in generated:
        console.print(f"  {f}")


@cli.command()
@click.option("--all", "remove_all", is_flag=True, help="Also remove volumes and images")
def clean(remove_all):
    """Clean up all stackbox resources."""
    click.echo("stackbox clean — not yet implemented")
