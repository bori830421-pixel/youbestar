import os
from pathlib import Path


DEFAULT_LOCAL_RUNTIME_DIR = Path(r"D:\YoubestarLocal")


def _expand_path(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser()


def local_runtime_dir() -> Path:
    configured = os.getenv("YOUBESTAR_LOCAL_HOME") or os.getenv("YOUBESTAR_LOCAL_DIR")
    if configured and configured.strip():
        return _expand_path(configured.strip())
    return DEFAULT_LOCAL_RUNTIME_DIR


def local_data_dir() -> Path:
    return local_runtime_dir() / "data"


def local_skills_dir() -> Path:
    return local_runtime_dir() / "skills"


def local_skill_source_dir() -> Path:
    return local_skills_dir() / "local"


def local_registry_dir() -> Path:
    return local_runtime_dir() / "registries"


def local_skill_registry_file() -> Path:
    return local_registry_dir() / "local.registry.json"


def local_skill_settings_file() -> Path:
    return local_registry_dir() / "skill_settings.local.json"


def ensure_local_runtime_dirs() -> None:
    for path in (
        local_runtime_dir(),
        local_data_dir(),
        local_skill_source_dir(),
        local_registry_dir(),
        local_runtime_dir() / "imports",
        local_runtime_dir() / "backups",
        local_runtime_dir() / "logs",
    ):
        path.mkdir(parents=True, exist_ok=True)


def is_inside(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    base = root.resolve()
    return resolved == base or base in resolved.parents


def local_runtime_record_path(path: Path) -> str:
    return str(path.resolve().relative_to(local_runtime_dir().resolve())).replace("\\", "/")
