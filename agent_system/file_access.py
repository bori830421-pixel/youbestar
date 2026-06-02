from pathlib import Path
from typing import Any

from fastapi import HTTPException


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_READ_ROOT = Path("D:/codex_project")

ALLOWED_READ_ROOTS = [
    DEFAULT_READ_ROOT if DEFAULT_READ_ROOT.exists() else PROJECT_ROOT,
]

ALLOWED_EXTENSIONS = {
    ".bat",
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

DENIED_DIR_NAMES = {
    ".cache",
    ".data",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "data",
    "dist",
    "node_modules",
    "runtime",
    "wheels",
}

DENIED_FILE_NAMES = {
    "auth.json",
    "cookies.json",
    "credentials.json",
    "token.json",
    "youbestar.json",
}

DENIED_NAME_KEYWORDS = {
    "api_key",
    "apikey",
    "auth",
    "cookie",
    "credential",
    "password",
    "passwd",
    "private_key",
    "secret",
    "token",
}

MAX_LIST_ITEMS = 300
MAX_READ_BYTES = 200_000
MAX_RETURN_CHARS = 40_000


def normalize_path(path: str | None) -> Path:
    if not path or not path.strip():
        return ALLOWED_READ_ROOTS[0].resolve()
    return Path(path.strip()).resolve()


def path_is_inside(path: Path, root: Path) -> bool:
    resolved_root = root.resolve()
    return path == resolved_root or resolved_root in path.parents


def ensure_allowed_root(path: Path) -> None:
    if not any(path_is_inside(path, root) for root in ALLOWED_READ_ROOTS):
        roots = [str(root) for root in ALLOWED_READ_ROOTS]
        raise HTTPException(status_code=403, detail=f"只允许读取白名单目录：{roots}")


def is_denied_by_name(path: Path) -> bool:
    lower_parts = [part.lower() for part in path.parts]
    if any(part in DENIED_DIR_NAMES for part in lower_parts):
        return True

    lower_name = path.name.lower()
    if lower_name.startswith(".env"):
        return True
    if lower_name in DENIED_FILE_NAMES:
        return True
    return any(keyword in lower_name for keyword in DENIED_NAME_KEYWORDS)


def ensure_path_readable(path: Path, require_file: bool = False) -> None:
    ensure_allowed_root(path)
    if is_denied_by_name(path):
        raise HTTPException(status_code=403, detail="该路径命中敏感文件或敏感目录规则，禁止读取。")
    if not path.exists():
        raise HTTPException(status_code=404, detail="路径不存在。")
    if require_file and not path.is_file():
        raise HTTPException(status_code=400, detail="只能读取文件。")


def extension_allowed(path: Path) -> bool:
    return path.suffix.lower() in ALLOWED_EXTENSIONS


def file_summary(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "type": "directory" if path.is_dir() else "file",
        "size": path.stat().st_size if path.is_file() else None,
    }


def list_allowed_files(path: str | None = None, recursive: bool = False) -> dict[str, Any]:
    target = normalize_path(path)
    ensure_path_readable(target)

    if target.is_file():
        if not extension_allowed(target):
            raise HTTPException(status_code=403, detail="该文件类型不在允许读取范围内。")
        return {"root": str(target), "items": [file_summary(target)], "truncated": False}

    items: list[dict[str, Any]] = []
    truncated = False

    if recursive:
        for current, dirs, files in walk_allowed_tree(target):
            for dirname in dirs:
                directory = current / dirname
                items.append(file_summary(directory))
                if len(items) >= MAX_LIST_ITEMS:
                    return {"root": str(target), "items": items, "truncated": True}
            for filename in files:
                file_path = current / filename
                if extension_allowed(file_path):
                    items.append(file_summary(file_path))
                if len(items) >= MAX_LIST_ITEMS:
                    return {"root": str(target), "items": items, "truncated": True}
    else:
        for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
            if is_denied_by_name(child):
                continue
            if child.is_file() and not extension_allowed(child):
                continue
            items.append(file_summary(child))
            if len(items) >= MAX_LIST_ITEMS:
                truncated = True
                break

    return {"root": str(target), "items": items, "truncated": truncated}


def walk_allowed_tree(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue

        dirs = []
        files = []
        for child in children:
            if is_denied_by_name(child):
                continue
            if child.is_dir():
                dirs.append(child.name)
                stack.append(child)
            elif child.is_file():
                files.append(child.name)
        yield current, dirs, files


def read_allowed_file(path: str) -> dict[str, Any]:
    target = normalize_path(path)
    ensure_path_readable(target, require_file=True)
    if not extension_allowed(target):
        raise HTTPException(status_code=403, detail="该文件类型不在允许读取范围内。")

    size = target.stat().st_size
    if size > MAX_READ_BYTES:
        raise HTTPException(status_code=413, detail=f"文件过大，最大允许读取 {MAX_READ_BYTES} bytes。")

    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = target.read_text(encoding="utf-8-sig")

    truncated = len(text) > MAX_RETURN_CHARS
    if truncated:
        text = text[:MAX_RETURN_CHARS]

    return {
        "path": str(target),
        "size": size,
        "content": text,
        "truncated": truncated,
    }


def read_policy() -> dict[str, Any]:
    return {
        "allowed_read_roots": [str(root) for root in ALLOWED_READ_ROOTS],
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "denied_dir_names": sorted(DENIED_DIR_NAMES),
        "denied_file_names": sorted(DENIED_FILE_NAMES),
        "denied_name_keywords": sorted(DENIED_NAME_KEYWORDS),
        "max_list_items": MAX_LIST_ITEMS,
        "max_read_bytes": MAX_READ_BYTES,
        "max_return_chars": MAX_RETURN_CHARS,
    }
