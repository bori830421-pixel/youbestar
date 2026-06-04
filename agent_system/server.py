from pydantic import BaseModel
from fastapi import APIRouter

from agent_system.manager import (
    approve_skill,
    list_approved_skills,
    load_approvals,
    reject_skill,
    request_approval,
    run_sandbox_tests,
    write_test_file,
    write_to_sandbox,
)
from agent_system.file_access import list_allowed_files, read_allowed_file, read_policy
from agent_system.skill_registry import list_skill_cards, set_skill_enabled


PERMISSION_PROMPT = """你是一个可进化Agent。

你可以：
1. 创建新的技能（skill）
2. 将代码写入 sandbox 目录
3. 提供测试用例验证技能
4. 提交审批请求
5. 使用 official.install_local_skill 直接安装或覆盖 local.* 技能

你不能：
- 操作系统文件
- 调用 ERP/微信
- 删除文件
- 执行未批准代码

所有技能必须：
- 有清晰输入输出
- 使用命名空间命名，例如 official.open_browser、community.user123.parse_order、local.my_parse_order
- local.* 技能可以由 Agent 直接进入 skills/local 并写入 skills/registry.json
- 注册后才会被 Agent 调用
"""


class SandboxWriteRequest(BaseModel):
    filename: str
    code: str


class TestWriteRequest(BaseModel):
    skill_name: str
    code: str


class TestRunRequest(BaseModel):
    file: str
    test_file: str | None = None


class ApprovalRequest(BaseModel):
    skill_name: str
    file: str
    description: str
    test_file: str | None = None


class ReviewRequest(BaseModel):
    skill_name: str
    file: str | None = None
    reviewer: str = "operator"
    note: str = ""


class FileListRequest(BaseModel):
    path: str | None = None
    recursive: bool = False


class FileReadRequest(BaseModel):
    path: str


class SkillToggleRequest(BaseModel):
    name: str
    enabled: bool


router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/prompt")
def skill_permission_prompt() -> dict[str, str]:
    return {"prompt": PERMISSION_PROMPT}


@router.get("/read-policy")
def file_read_policy() -> dict:
    return read_policy()


@router.post("/files/list")
def list_files(request: FileListRequest) -> dict:
    return list_allowed_files(request.path, request.recursive)


@router.post("/files/read")
def read_file(request: FileReadRequest) -> dict:
    return read_allowed_file(request.path)


@router.get("/approved")
def approved_skills() -> dict[str, list[str]]:
    return {"skills": list_approved_skills()}


@router.get("/registry")
def skill_registry() -> dict:
    return {"skills": list_skill_cards()}


@router.post("/toggle")
def toggle_skill(request: SkillToggleRequest) -> dict:
    return set_skill_enabled(request.name, request.enabled)


@router.get("/approvals")
def approvals() -> dict[str, list[dict]]:
    return {"approvals": load_approvals()}


@router.post("/sandbox/write")
def write_sandbox_file(request: SandboxWriteRequest) -> dict:
    return write_to_sandbox(request.filename, request.code)


@router.post("/tests/write")
def write_skill_test(request: TestWriteRequest) -> dict:
    return write_test_file(request.skill_name, request.code)


@router.post("/tests/run")
def run_skill_tests(request: TestRunRequest) -> dict:
    return run_sandbox_tests(request.file, request.test_file)


@router.post("/approval/request")
def create_approval_request(request: ApprovalRequest) -> dict:
    return request_approval(request.skill_name, request.file, request.description, request.test_file)


@router.post("/approve")
def approve(request: ReviewRequest) -> dict:
    return approve_skill(request.skill_name, request.file, request.reviewer, request.note)


@router.post("/reject")
def reject(request: ReviewRequest) -> dict:
    return reject_skill(request.skill_name, request.file, request.reviewer, request.note)
