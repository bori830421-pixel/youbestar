from agent_system.manager import request_approval, write_test_file, write_to_sandbox


def write_skill(params: dict) -> str:
    filename = params.get("filename", "")
    code = params.get("code", "")
    result = write_to_sandbox(filename, code)
    return f"已写入 sandbox：{result['file']}"


def write_skill_test(params: dict) -> str:
    skill_name = params.get("skill_name", "")
    code = params.get("code", "")
    result = write_test_file(skill_name, code)
    return f"已写入测试：{result['file']}"


def request_skill_approval(params: dict) -> str:
    record = request_approval(
        skill_name=params.get("skill_name", ""),
        file=params.get("file", ""),
        description=params.get("description", ""),
        test_file=params.get("test_file"),
    )
    return f"已提交审批：{record['skill_name']} ({record['id']})"
