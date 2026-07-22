from pathlib import Path

XDG_CONFIG_HOME = Path.home() / ".config" / "stackbox"
XDG_DATA_HOME = Path.home() / ".local" / "share" / "stackbox"
XDG_CACHE_HOME = Path.home() / ".cache" / "stackbox"

SESSIONS_DIR = XDG_DATA_HOME / "sessions"
REPO_CACHE_DIR = XDG_CACHE_HOME / "repos"


def ensure_dirs():
    for d in (XDG_CONFIG_HOME, XDG_DATA_HOME, XDG_CACHE_HOME, SESSIONS_DIR, REPO_CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
