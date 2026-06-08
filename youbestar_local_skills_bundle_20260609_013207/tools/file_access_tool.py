from agent_system.file_access import list_allowed_files, read_allowed_file, write_allowed_file


def list_files(params: dict) -> str:
    result = list_allowed_files(
        path=params.get("path"),
        recursive=bool(params.get("recursive", False)),
    )
    lines = [f"root: {result['root']}"]
    for item in result["items"]:
        size = "" if item["size"] is None else f" ({item['size']} bytes)"
        lines.append(f"- {item['type']}: {item['path']}{size}")
    if result["truncated"]:
        lines.append("结果已截断。")
    return "\n".join(lines)


def read_file(params: dict) -> str:
    result = read_allowed_file(params.get("path", ""))
    suffix = "\n\n[内容已截断]" if result["truncated"] else ""
    return f"file: {result['path']}\nsize: {result['size']} bytes\n\n{result['content']}{suffix}"


def write_project_file(params: dict) -> str:
    result = write_allowed_file(
        path=params.get("path", ""),
        content=str(params.get("content", "")),
        overwrite=bool(params.get("overwrite", False)),
    )
    return f"已写入项目文件：{result['path']} ({result['size']} bytes)"
