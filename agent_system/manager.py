import ast
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from core.local_runtime import (
    ensure_local_runtime_dirs,
    is_inside,
    local_runtime_dir,
    local_runtime_record_path,
    local_skill_registry_file,
    local_skill_source_dir,
)


AGENT_SYSTEM_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_SYSTEM_DIR.parent
SKILLS_DIR = AGENT_SYSTEM_DIR / "skills"
SANDBOX_DIR = AGENT_SYSTEM_DIR / "sandbox"
TESTS_DIR = AGENT_SYSTEM_DIR / "tests"
APPROVALS_FILE = AGENT_SYSTEM_DIR / "approvals.json"
REGISTRY_FILE = SKILLS_DIR / "registry.json"

SAFE_SKILL_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
SAFE_FILE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.py$")
SKILL_SOURCES = {"official", "community", "local"}

BANNED_IMPORT_ROOTS = {
    "ctypes",
    "keyboard",
    "os",
    "pathlib",
    "playwright",
    "pyautogui",
    "pyperclip",
    "requests",
    "selenium",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "uiautomation",
    "webbrowser",
    "win32api",
    "win32con",
    "win32gui",
}
BANNED_CALL_NAMES = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "input",
    "open",
}
BANNED_ATTR_NAMES = {
    "delete",
    "kill",
    "move",
    "remove",
    "replace",
    "rmdir",
    "rmtree",
    "send",
    "startfile",
    "system",
    "unlink",
    "write",
}


def ensure_agent_dirs() -> None:
    for path in (
        SKILLS_DIR,
        SKILLS_DIR / "official",
        SKILLS_DIR / "community",
        SANDBOX_DIR,
        TESTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
    ensure_local_runtime_dirs()
    if not APPROVALS_FILE.exists():
        APPROVALS_FILE.write_text("[]", encoding="utf-8")
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text("{}", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_relative(path: Path) -> str:
    for candidate, root in ((Path(path), PROJECT_ROOT), (Path(path).resolve(), PROJECT_ROOT.resolve())):
        try:
            return str(candidate.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
    raise ValueError(f"{path} is not inside {PROJECT_ROOT}")


def to_record_path(path: Path, source: str) -> str:
    if source == "local":
        return local_runtime_record_path(path)
    return to_relative(path)


def _registry_for_source(source: str) -> Path:
    return local_skill_registry_file() if source == "local" else REGISTRY_FILE


def validate_skill_name(skill_name: str) -> str:
    clean_name = skill_name.strip()
    if not SAFE_SKILL_NAME_RE.fullmatch(clean_name):
        raise HTTPException(status_code=400, detail="skill_name 只能使用英文字母、数字和下划线，并且必须以字母开头。")
    return clean_name


def skill_source_dir(source: str) -> Path:
    if source not in SKILL_SOURCES:
        raise HTTPException(status_code=400, detail="技能来源只能是 official、community 或 local。")
    if source == "local":
        return local_skill_source_dir()
    return SKILLS_DIR / source


def validate_skill_id(skill_id: str) -> str:
    clean_id = skill_id.strip()
    parts = clean_id.split(".")
    if len(parts) < 2 or parts[0] not in SKILL_SOURCES:
        raise HTTPException(status_code=400, detail="skill_name 必须使用命名空间，例如 official.open_browser 或 local.my_skill。")

    source = parts[0]
    if source in {"official", "local"}:
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail=f"{source} 技能格式必须是 {source}.skill_name。")
        validate_skill_name(parts[1])
    elif source == "community":
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail="community 技能格式必须是 community.author.skill_name。")
        validate_skill_name(parts[1])
        validate_skill_name(parts[2])

    return clean_id


def normalize_skill_id(skill_name: str) -> str:
    clean_name = skill_name.strip()
    if "." not in clean_name:
        return f"local.{validate_skill_name(clean_name)}"
    return validate_skill_id(clean_name)


def skill_source(skill_id: str) -> str:
    return normalize_skill_id(skill_id).split(".", 1)[0]


def skill_simple_name(skill_id: str) -> str:
    return normalize_skill_id(skill_id).split(".")[-1]


def skill_file_path(skill_id: str) -> Path:
    clean_id = normalize_skill_id(skill_id)
    parts = clean_id.split(".")
    source = parts[0]
    if source == "community":
        return skill_source_dir(source) / f"{parts[1]}_{parts[2]}.py"
    return skill_source_dir(source) / f"{parts[1]}.py"


def skill_id_for_record_id(skill_id: str) -> str:
    return normalize_skill_id(skill_id).replace(".", "_")


def validate_python_filename(filename: str) -> str:
    clean_name = Path(filename.strip()).name
    if not SAFE_FILE_NAME_RE.fullmatch(clean_name):
        raise HTTPException(status_code=400, detail="Python 文件名只能使用英文字母、数字、下划线，并且必须以 .py 结尾。")
    return clean_name


def resolve_inside(base_dir: Path, file_path: str) -> Path:
    raw_path = Path(file_path)
    candidate = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
    resolved = candidate.resolve()
    base = base_dir.resolve()
    if resolved != base and base not in resolved.parents:
        raise HTTPException(status_code=400, detail=f"文件必须位于 {to_relative(base_dir)} 内。")
    return resolved


def scan_code_safety(code: str) -> list[str]:
    findings = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"语法错误：{exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in BANNED_IMPORT_ROOTS:
                    findings.append(f"禁止导入模块：{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in BANNED_IMPORT_ROOTS:
                findings.append(f"禁止导入模块：{node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_CALL_NAMES:
                findings.append(f"禁止调用函数：{node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in BANNED_ATTR_NAMES:
                findings.append(f"禁止调用方法：{node.func.attr}")
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTR_NAMES:
                findings.append(f"禁止访问高风险属性：{node.attr}")
        elif isinstance(node, ast.Name):
            if node.id.startswith("__") and node.id.endswith("__"):
                findings.append(f"禁止使用双下划线名称：{node.id}")

    return sorted(set(findings))


def assert_code_safe(code: str) -> None:
    findings = scan_code_safety(code)
    if findings:
        raise HTTPException(status_code=400, detail={"message": "安全扫描未通过", "findings": findings})


def read_json_file(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"{path.name} 不是有效 JSON：{exc}") from exc


def write_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_raw_registry_file(path: Path) -> dict[str, Any]:
    registry = read_json_file(path, {})
    if not isinstance(registry, dict):
        raise HTTPException(status_code=500, detail=f"{path.name} 必须是对象。")
    return registry


def _clean_registry_records(registry: dict[str, Any], registry_name: str) -> dict[str, dict[str, Any]]:
    clean_registry: dict[str, dict[str, Any]] = {}
    for skill_id, record in registry.items():
        clean_id = validate_skill_id(str(skill_id))
        if not isinstance(record, dict):
            raise HTTPException(status_code=500, detail=f"{registry_name} 中 {clean_id} 必须是对象。")
        source = str(record.get("source") or skill_source(clean_id))
        if source != skill_source(clean_id):
            raise HTTPException(status_code=500, detail=f"{registry_name} 中 {clean_id} 的 source 与命名空间不一致。")
        clean_registry[clean_id] = record
    return clean_registry


def load_skill_registry() -> dict[str, dict[str, Any]]:
    ensure_agent_dirs()
    clean_registry = _clean_registry_records(_load_raw_registry_file(REGISTRY_FILE), "registry.json")
    local_registry = _clean_registry_records(_load_raw_registry_file(local_skill_registry_file()), "local.registry.json")
    clean_registry.update(local_registry)
    return clean_registry


def save_skill_registry(registry: dict[str, dict[str, Any]]) -> None:
    ensure_agent_dirs()
    project_registry = {name: record for name, record in registry.items() if skill_source(name) != "local"}
    local_registry = {name: record for name, record in registry.items() if skill_source(name) == "local"}
    write_json_file(REGISTRY_FILE, project_registry)
    write_json_file(local_skill_registry_file(), local_registry)


def resolve_registered_skill_path(record: dict[str, Any]) -> Path:
    raw_path = Path(str(record.get("path", "")))
    source = str(record.get("source", ""))
    if raw_path.is_absolute():
        candidate = raw_path
    elif source == "local":
        candidate = local_runtime_dir() / raw_path
        legacy_candidate = PROJECT_ROOT / raw_path
        if not candidate.exists() and legacy_candidate.exists():
            candidate = legacy_candidate
    else:
        candidate = PROJECT_ROOT / raw_path
    resolved = candidate.resolve()
    base = skill_source_dir(source).resolve()
    legacy_base = (PROJECT_ROOT / "agent_system" / "skills" / "local").resolve()
    if source == "local" and is_inside(resolved, legacy_base):
        return resolved
    if resolved != base and base not in resolved.parents:
        base_label = str(base) if source == "local" else to_relative(skill_source_dir(source))
        raise HTTPException(status_code=400, detail=f"技能文件必须位于 {base_label} 内。")
    return resolved


def register_skill(
    skill_name: str,
    path: Path | str,
    version: str = "dev",
    source: str | None = None,
    description: str = "",
    author: str = "",
    title: str = "",
) -> dict[str, Any]:
    ensure_agent_dirs()
    skill_id = normalize_skill_id(skill_name)
    expected_source = skill_source(skill_id)
    clean_source = source or expected_source
    if clean_source != expected_source:
        raise HTTPException(status_code=400, detail="技能 source 必须与命名空间一致。")

    skill_path = Path(path).resolve()
    base = skill_source_dir(clean_source).resolve()
    if skill_path != base and base not in skill_path.parents:
        base_label = str(base) if clean_source == "local" else to_relative(skill_source_dir(clean_source))
        raise HTTPException(status_code=400, detail=f"技能文件必须位于 {base_label} 内。")
    if not skill_path.exists():
        raise HTTPException(status_code=404, detail="技能文件不存在，不能注册。")

    if clean_source == "community":
        assert_code_safe(skill_path.read_text(encoding="utf-8"))

    registry = _clean_registry_records(_load_raw_registry_file(_registry_for_source(clean_source)), _registry_for_source(clean_source).name)
    record = {
        "path": to_record_path(skill_path, clean_source),
        "version": version.strip() or "dev",
        "source": clean_source,
        "description": description.strip(),
        "author": author.strip(),
        "title": title.strip() or skill_id,
        "updated_at": utc_now(),
    }
    registry[skill_id] = record
    write_json_file(_registry_for_source(clean_source), registry)
    return record


def install_local_skill(
    skill_name: str,
    code: str,
    description: str = "",
    title: str = "",
    version: str = "dev",
    overwrite: bool = True,
) -> dict[str, Any]:
    ensure_agent_dirs()
    skill_id = normalize_skill_id(skill_name)
    if skill_source(skill_id) != "local":
        raise HTTPException(status_code=400, detail="自主安装技能只能使用 local 命名空间。")

    clean_code = code.strip()
    if not clean_code:
        raise HTTPException(status_code=400, detail="技能代码不能为空。")
    assert_code_safe(clean_code)

    skill_path = skill_file_path(skill_id)
    if skill_path.exists() and not overwrite:
        raise HTTPException(status_code=400, detail="同名 local 技能已存在。")

    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(clean_code + "\n", encoding="utf-8")
    record = register_skill(
        skill_id,
        skill_path,
        version=version,
        source="local",
        description=description,
        author="autonomous-agent",
        title=title or skill_id,
    )
    return {
        "status": "installed",
        "skill_name": skill_id,
        "file": record["path"],
        "registry": record,
    }


def load_approvals() -> list[dict[str, Any]]:
    ensure_agent_dirs()
    approvals = read_json_file(APPROVALS_FILE, [])
    if not isinstance(approvals, list):
        raise HTTPException(status_code=500, detail="approvals.json 必须是数组。")
    return approvals


def save_approvals(approvals: list[dict[str, Any]]) -> None:
    ensure_agent_dirs()
    write_json_file(APPROVALS_FILE, approvals)


def write_to_sandbox(filename: str, code: str) -> dict[str, Any]:
    ensure_agent_dirs()
    safe_filename = validate_python_filename(filename)
    assert_code_safe(code)

    path = SANDBOX_DIR / safe_filename
    path.write_text(code, encoding="utf-8")
    return {
        "status": "ok",
        "file": to_relative(path),
        "safety_findings": [],
    }


def write_test_file(skill_name: str, code: str) -> dict[str, Any]:
    ensure_agent_dirs()
    safe_skill_name = skill_simple_name(normalize_skill_id(skill_name))
    assert_code_safe(code)

    path = TESTS_DIR / f"{safe_skill_name}_test.py"
    path.write_text(code, encoding="utf-8")
    return {
        "status": "ok",
        "file": to_relative(path),
        "safety_findings": [],
    }


def run_sandbox_tests(skill_file: str, test_file: str | None = None) -> dict[str, Any]:
    ensure_agent_dirs()
    skill_path = resolve_inside(SANDBOX_DIR, skill_file)
    if not skill_path.exists():
        raise HTTPException(status_code=404, detail="sandbox 技能文件不存在。")

    target_test_path = resolve_inside(TESTS_DIR, test_file) if test_file else None
    if target_test_path is None:
        default_test = TESTS_DIR / f"{skill_path.stem.split('_v', 1)[0]}_test.py"
        target_test_path = default_test
    if not target_test_path.exists():
        raise HTTPException(status_code=400, detail=f"测试文件不存在：{to_relative(target_test_path)}")

    skill_code = skill_path.read_text(encoding="utf-8")
    test_code = target_test_path.read_text(encoding="utf-8")
    assert_code_safe(skill_code)
    assert_code_safe(test_code)

    command = [
        sys.executable,
        "-m",
        "agent_system.test_runner",
        str(skill_path),
        str(target_test_path),
    ]
    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "skill_file": to_relative(skill_path),
        "test_file": to_relative(target_test_path),
    }


def request_approval(skill_name: str, file: str, description: str, test_file: str | None = None) -> dict[str, Any]:
    ensure_agent_dirs()
    skill_id = normalize_skill_id(skill_name)
    if skill_source(skill_id) != "local":
        raise HTTPException(status_code=400, detail="模型申请审批的新技能只能进入 local 命名空间。")
    if skill_id in load_skill_registry():
        raise HTTPException(status_code=400, detail="同名正式技能已注册，当前审批流程不允许覆盖已有 local skill。")

    skill_path = resolve_inside(SANDBOX_DIR, file)
    if not skill_path.exists():
        raise HTTPException(status_code=404, detail="sandbox 技能文件不存在。")

    test_result = run_sandbox_tests(to_relative(skill_path), test_file)
    if not test_result["passed"]:
        raise HTTPException(status_code=400, detail={"message": "测试未通过，不能申请审批。", "test_result": test_result})

    approvals = load_approvals()
    record = {
        "id": f"{skill_id_for_record_id(skill_id)}-{int(datetime.now(timezone.utc).timestamp())}",
        "skill_name": skill_id,
        "file": to_relative(skill_path),
        "description": description.strip(),
        "test_file": test_result["test_file"],
        "status": "pending",
        "tests_passed": True,
        "requested_at": utc_now(),
        "reviewed_at": None,
        "reviewer": None,
        "review_note": "",
    }
    approvals.append(record)
    save_approvals(approvals)
    return record


def find_pending_record(skill_name: str, file: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    skill_id = normalize_skill_id(skill_name)
    approvals = load_approvals()
    for record in reversed(approvals):
        if record.get("skill_name") != skill_id or record.get("status") != "pending":
            continue
        if file and record.get("file") != file:
            continue
        return approvals, record
    raise HTTPException(status_code=404, detail="没有找到待审批记录。")


def approve_skill(skill_name: str, file: str | None = None, reviewer: str = "operator", note: str = "") -> dict[str, Any]:
    ensure_agent_dirs()
    approvals, record = find_pending_record(skill_name, file)
    skill_path = resolve_inside(SANDBOX_DIR, record["file"])
    test_result = run_sandbox_tests(record["file"], record.get("test_file"))
    if not test_result["passed"]:
        raise HTTPException(status_code=400, detail={"message": "复测未通过，不能批准。", "test_result": test_result})

    skill_id = normalize_skill_id(record["skill_name"])
    if skill_id in load_skill_registry():
        raise HTTPException(status_code=400, detail="同名正式技能已注册，禁止覆盖已有 skill。")

    approved_path = skill_file_path(skill_id)
    approved_path.parent.mkdir(parents=True, exist_ok=True)
    if approved_path.exists():
        raise HTTPException(status_code=400, detail="同名正式技能文件已存在，禁止覆盖已有 skill。")

    shutil.move(str(skill_path), str(approved_path))
    register_skill(
        skill_id,
        approved_path,
        version="dev",
        source="local",
        description=record.get("description", ""),
        author="local",
        title=skill_id,
    )

    record["status"] = "approved"
    record["approved_file"] = to_record_path(approved_path, "local")
    record["reviewed_at"] = utc_now()
    record["reviewer"] = reviewer.strip() or "operator"
    record["review_note"] = note.strip()
    save_approvals(approvals)

    return {
        "status": "approved",
        "skill_name": skill_id,
        "file": record["approved_file"],
        "test_result": test_result,
    }


def reject_skill(skill_name: str, file: str | None = None, reviewer: str = "operator", note: str = "") -> dict[str, Any]:
    approvals, record = find_pending_record(skill_name, file)
    record["status"] = "rejected"
    record["reviewed_at"] = utc_now()
    record["reviewer"] = reviewer.strip() or "operator"
    record["review_note"] = note.strip()
    save_approvals(approvals)
    return {
        "status": "rejected",
        "skill_name": record["skill_name"],
        "file": record["file"],
    }


def list_approved_skills() -> list[str]:
    ensure_agent_dirs()
    return sorted(load_skill_registry())


def is_approved_skill(skill_name: str) -> bool:
    try:
        skill_id = normalize_skill_id(skill_name)
    except HTTPException:
        return False
    return skill_id in load_skill_registry()


def run_approved_skill(skill_name: str, params: dict[str, Any]) -> Any:
    import importlib.util

    skill_id = normalize_skill_id(skill_name)
    registry = load_skill_registry()
    record = registry.get(skill_id)
    if not record:
        raise HTTPException(status_code=404, detail="技能尚未注册或不存在。")

    skill_path = resolve_registered_skill_path(record)
    if not skill_path.exists():
        raise HTTPException(status_code=404, detail="技能文件不存在。")
    if record.get("source") == "community":
        assert_code_safe(skill_path.read_text(encoding="utf-8"))

    module_name = f"registered_skill_{skill_id.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, skill_path)
    if spec is None or spec.loader is None:
        raise HTTPException(status_code=500, detail="无法加载已注册技能。")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "run"):
        return module.run(params)

    simple_name = skill_simple_name(skill_id)
    if not hasattr(module, simple_name):
        raise HTTPException(status_code=400, detail=f"技能必须提供 run(params) 或 {simple_name}(...) 函数。")

    func = getattr(module, simple_name)
    if len(params) == 1 and "text" in params:
        return func(params["text"])
    return func(**params)
