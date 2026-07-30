import uuid as _uuid

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
    from stackbox.config_gen.ports import PortManager
    from stackbox.containers import preflight
    from stackbox.containers.images import ImageManager
    from stackbox.containers.podman import PodmanBackend
    from stackbox.models.job_config import ResolvedJobConfig

    console = Console()

    with console.status("Running preflight checks..."):
        job = ResolvedJobConfig(job_name="preflight")
        pm = PortManager()
        preflight.check_all(job, pm)

    console.print("[green]Preflight checks passed[/green]")

    backend = PodmanBackend()
    images = ImageManager(backend, release)

    core_kolla = [
        "mariadb", "rabbitmq", "memcached", "keystone",
        "glance-api", "placement-api", "neutron-server",
        "nova-api", "nova-scheduler", "nova-conductor", "nova-compute",
        "ironic-api", "ironic-conductor",
        "openvswitch-db-server", "openvswitch-vswitchd", "nova-libvirt",
    ]

    with console.status(f"Pulling {len(core_kolla)} Kolla images..."):
        images.pull_kolla(core_kolla)

    with console.status("Pulling Metal3 images..."):
        images.pull_metal3(["sushy-tools"])

    console.print(f"[green]Pulled {len(core_kolla) + 1} images[/green]")


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
    from pathlib import Path

    from stackbox.bootstrap.orchestrator import BootstrapOrchestrator
    from stackbox.config_gen import ConfigPipeline
    from stackbox.containers.manifest import SessionManifest
    from stackbox.containers.podman import PodmanBackend

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

    session_id = _uuid.uuid4().hex[:12]
    session_dir = SESSIONS_DIR / session_id
    configs_dir = session_dir / "configs"

    with console.status("Generating configs..."):
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(config, configs_dir)

    console.print(f"[green]Generated {len(generated)} config files[/green]")

    backend = PodmanBackend()
    manifest = SessionManifest(
        session_id=session_id,
        configs_dir=str(configs_dir),
    )

    orchestrator = BootstrapOrchestrator(
        backend=backend,
        job=config,
        configs_dir=configs_dir,
        manifest=manifest,
        release=release,
    )

    try:
        with console.status("Bootstrapping services..."):
            orchestrator.run()

        console.print("[green]All services bootstrapped[/green]")

        if not skip_tempest and config.tempest_test_regex:
            from stackbox.tempest.runner import TempestRunner

            runner = TempestRunner(backend)
            results_dir = session_dir / "results"
            exit_code = runner.run(
                tempest_conf=configs_dir / "tempest.conf",
                test_regex=config.tempest_test_regex,
                results_dir=results_dir,
            )
            if exit_code == 0:
                console.print("[green]Tempest tests PASSED[/green]")
            else:
                console.print(f"[red]Tempest tests FAILED (exit {exit_code})[/red]")
        elif skip_tempest:
            console.print("[yellow]Tempest skipped (--skip-tempest)[/yellow]")

    finally:
        manifest.save(session_dir)
        if not keep:
            console.print("[yellow]Use 'stackbox clean' to tear down, or --keep to leave running[/yellow]")

    console.print(f"\nSession: {session_id}")
    console.print(f"Configs: {configs_dir}")


@cli.command()
@click.argument("build_url")
@click.option("--local-repo", multiple=True, help="service=path pairs for local builds")
@click.option("--port-offset", type=int, default=0, help="Shift all service ports by N")
@click.option("--dry-run", is_flag=True, help="Show config without deploying")
@click.option("--skip-tempest", is_flag=True, help="Skip test execution")
@click.option("--keep", is_flag=True, help="Keep containers running after tests")
@click.option("--release", default=DEFAULT_RELEASE, help="Kolla image release tag")
def reproduce(build_url, local_repo, port_offset, dry_run, skip_tempest, keep, release):
    """Reproduce a CI job from a Zuul build URL."""
    from pathlib import Path

    from stackbox.bootstrap.orchestrator import BootstrapOrchestrator
    from stackbox.config_gen import ConfigPipeline
    from stackbox.containers.manifest import SessionManifest
    from stackbox.containers.podman import PodmanBackend
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

    session_id = _uuid.uuid4().hex[:12]
    session_dir = SESSIONS_DIR / session_id
    configs_dir = session_dir / "configs"

    with console.status("Generating configs..."):
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(config, configs_dir)

    backend = PodmanBackend()
    manifest = SessionManifest(session_id=session_id, configs_dir=str(configs_dir))

    orchestrator = BootstrapOrchestrator(
        backend=backend, job=config, configs_dir=configs_dir,
        manifest=manifest, release=release,
    )

    try:
        with console.status("Bootstrapping services..."):
            orchestrator.run()

        console.print("[green]All services bootstrapped[/green]")

        if not skip_tempest and config.tempest_test_regex:
            from stackbox.tempest.runner import TempestRunner

            runner = TempestRunner(backend)
            exit_code = runner.run(
                tempest_conf=configs_dir / "tempest.conf",
                test_regex=config.tempest_test_regex,
                results_dir=session_dir / "results",
            )
            if exit_code == 0:
                console.print("[green]Tempest tests PASSED[/green]")
            else:
                console.print(f"[red]Tempest tests FAILED (exit {exit_code})[/red]")

    finally:
        manifest.save(session_dir)

    console.print(f"\nSession: {session_id}")


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
    from stackbox.containers.podman import PodmanBackend

    console = Console()
    backend = PodmanBackend()

    containers = backend.list_containers(prefix="stackbox-")
    if not containers:
        console.print("No stackbox containers running")
        return

    table = Table(title="STACKBOX Containers")
    table.add_column("Name", style="cyan")
    table.add_column("Image")
    table.add_column("Status")
    table.add_column("Created")

    for c in containers:
        name = c.get("Names", [c.get("Name", "unknown")])
        if isinstance(name, list):
            name = name[0] if name else "unknown"
        table.add_row(
            name,
            c.get("Image", ""),
            c.get("State", c.get("Status", "")),
            c.get("Created", ""),
        )

    console.print(table)


@cli.command()
@click.argument("service")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--tail", type=int, default=None, help="Number of lines to show")
def logs(service, follow, tail):
    """Tail logs from a service container."""
    from stackbox.containers.podman import PodmanBackend

    backend = PodmanBackend()
    name = f"stackbox-{service}" if not service.startswith("stackbox-") else service
    output = backend.logs(name, follow=follow, tail=tail)
    if output:
        click.echo(output)


@cli.command("exec")
@click.argument("service")
@click.argument("cmd", nargs=-1, required=True)
def exec_cmd(service, cmd):
    """Execute a command in a service container."""
    from stackbox.containers.podman import PodmanBackend

    backend = PodmanBackend()
    name = f"stackbox-{service}" if not service.startswith("stackbox-") else service
    exit_code, output = backend.exec(name, list(cmd))
    if output:
        click.echo(output)
    raise SystemExit(exit_code)


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
        session_id = _uuid.uuid4().hex[:12]
        out = SESSIONS_DIR / session_id / "configs"

    with console.status("Generating configs..."):
        pipeline = ConfigPipeline()
        generated = pipeline.generate_all(resolved, out)

    console.print(f"[green]Generated {len(generated)} config files in:[/green] {out}")
    for f in generated:
        console.print(f"  {f}")


@cli.command()
@click.option("--session", default=None, help="Session ID to clean (default: latest)")
@click.option("--all", "remove_all", is_flag=True, help="Also remove volumes and images")
def clean(session, remove_all):
    """Clean up all stackbox resources."""
    import subprocess

    from stackbox.containers.manifest import SessionManifest
    from stackbox.containers.podman import PodmanBackend

    console = Console()
    backend = PodmanBackend()

    if session:
        session_dir = SESSIONS_DIR / session
    else:
        sessions = sorted(SESSIONS_DIR.iterdir()) if SESSIONS_DIR.exists() else []
        if not sessions:
            console.print("No sessions found")
            return
        session_dir = sessions[-1]

    try:
        manifest = SessionManifest.load(session_dir)
    except FileNotFoundError:
        console.print(f"[yellow]No manifest found in {session_dir}, cleaning by prefix[/yellow]")
        containers = backend.list_containers(prefix="stackbox-")
        for c in containers:
            name = c.get("Names", [c.get("Name", "")])
            if isinstance(name, list):
                name = name[0] if name else ""
            if name:
                backend.stop(name)
                backend.remove(name, force=True)
                console.print(f"  Removed container {name}")
        return

    with console.status("Cleaning up..."):
        for name in reversed(manifest.containers):
            backend.stop(name)
            backend.remove(name, force=True)
            console.print(f"  Removed container {name}")

        for domain in manifest.libvirt_domains:
            subprocess.run(["virsh", "destroy", domain], capture_output=True)
            subprocess.run(["virsh", "undefine", domain, "--remove-all-storage"], capture_output=True)
            console.print(f"  Removed VM {domain}")

        for bridge in manifest.ovs_bridges:
            subprocess.run(["sudo", "ovs-vsctl", "--if-exists", "del-br", bridge], capture_output=True)
            console.print(f"  Removed bridge {bridge}")

        if remove_all:
            for vol in manifest.volumes:
                backend.remove_volume(vol)
                console.print(f"  Removed volume {vol}")

    console.print(f"[green]Session {manifest.session_id} cleaned up[/green]")
