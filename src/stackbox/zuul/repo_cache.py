from __future__ import annotations

import subprocess
from pathlib import Path

from stackbox.config import REPO_CACHE_DIR
from stackbox.constants import REQUIRED_REPOS
from stackbox.exceptions import JobResolutionError, StackboxError


class RepoCache:
    def __init__(self, cache_dir: Path = REPO_CACHE_DIR):
        self.cache_dir = cache_dir

    def _repo_dir(self, repo: str) -> Path:
        return self.cache_dir / repo.replace("/", "_")

    def ensure_repos(self, branch: str = "master") -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        for repo, url in REQUIRED_REPOS.items():
            repo_path = self._repo_dir(repo)
            if (repo_path / ".git").is_dir():
                continue
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", "--branch", branch, url, str(repo_path)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise StackboxError(
                    f"Failed to clone {repo}: {exc.stderr.strip()}"
                ) from exc

    def get_repo_path(self, repo: str) -> Path:
        repo_path = self._repo_dir(repo)
        if not repo_path.is_dir():
            raise JobResolutionError(
                f"Repo '{repo}' not cached. Run 'stackbox init' or "
                f"'stackbox run --offline' to clone required repos."
            )
        return repo_path

    def update(self, repo: str | None = None, branch: str = "master") -> None:
        repos = {repo: REQUIRED_REPOS[repo]} if repo else REQUIRED_REPOS
        for repo_name in repos:
            repo_path = self._repo_dir(repo_name)
            if not repo_path.is_dir():
                continue
            try:
                subprocess.run(
                    ["git", "-C", str(repo_path), "fetch", "--depth", "1", "origin", branch],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", str(repo_path), "reset", "--hard", "FETCH_HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise StackboxError(
                    f"Failed to update {repo_name}: {exc.stderr.strip()}"
                ) from exc
