import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from core.local_runtime import ensure_local_runtime_dirs, local_runtime_dir


DEFAULT_SERVICE_PORT = 8000
LOCAL_HOST = "127.0.0.1"
LAN_HOST = "0.0.0.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ServiceConfig(BaseModel):
    lan_share_enabled: bool = False
    port: int = Field(default=DEFAULT_SERVICE_PORT, ge=1, le=65535)


def service_config_file() -> Path:
    return local_runtime_dir() / "config" / "service.json"


def load_service_config() -> ServiceConfig:
    path = service_config_file()
    if not path.exists():
        return ServiceConfig()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"服务配置读取失败：{exc}") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="服务配置顶层结构必须是对象。")

    return ServiceConfig(**data)


def save_service_config(config: ServiceConfig) -> ServiceConfig:
    ensure_local_runtime_dirs()
    path = service_config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(config, "model_dump"):
        payload = config.model_dump()
    else:
        payload = config.dict()
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"服务配置写入失败：{exc}") from exc
    return config


def effective_host(config: ServiceConfig) -> str:
    return LAN_HOST if config.lan_share_enabled else LOCAL_HOST


def firewall_rule_name(port: int) -> str:
    return f"YouBestar LAN {port}"


def firewall_rule_command(port: int) -> str:
    return (
        f'New-NetFirewallRule -DisplayName "{firewall_rule_name(port)}" '
        f"-Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow"
    )


def _run_powershell(command: str, timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def detect_lan_ipv4() -> str:
    if sys.platform.startswith("win"):
        command = (
            "$ip = Get-NetIPConfiguration | "
            "Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' -and $_.IPv4Address } | "
            "Sort-Object InterfaceIndex | ForEach-Object { $_.IPv4Address.IPAddress } | Select-Object -First 1; "
            "if (-not $ip) { "
            "$ip = Get-NetIPAddress -AddressFamily IPv4 | "
            "Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' -and $_.InterfaceOperationalStatus -eq 'Up' } | "
            "Sort-Object InterfaceIndex | Select-Object -First 1 -ExpandProperty IPAddress "
            "}; "
            "$ip"
        )
        try:
            result = _run_powershell(command, timeout=4)
            ip = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
            if ip:
                return ip
        except (OSError, subprocess.TimeoutExpired):
            pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip and not ip.startswith(("127.", "169.254.")):
                return ip
    except OSError:
        pass

    return LOCAL_HOST


def check_firewall_rule(port: int) -> dict[str, Any]:
    name = firewall_rule_name(port)
    if not sys.platform.startswith("win"):
        return {
            "supported": False,
            "rule_name": name,
            "enabled": False,
            "allowed": False,
            "message": "当前系统不是 Windows，未检查防火墙规则。",
        }

    command = (
        f"$rule = Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue; "
        "if ($rule) { "
        "$rule | Select-Object -First 1 | ForEach-Object { "
        "Write-Output \"$($_.Enabled)|$($_.Direction)|$($_.Action)\" "
        "} "
        "}"
    )
    try:
        result = _run_powershell(command, timeout=4)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "supported": True,
            "rule_name": name,
            "enabled": False,
            "allowed": False,
            "message": f"防火墙规则检查失败：{exc}",
        }

    output = result.stdout.strip()
    if not output:
        return {
            "supported": True,
            "rule_name": name,
            "enabled": False,
            "allowed": False,
            "message": "未找到防火墙入站规则。",
        }

    enabled, direction, action = (output.split("|") + ["", "", ""])[:3]
    allowed = enabled.lower() == "true" and direction.lower() == "inbound" and action.lower() == "allow"
    return {
        "supported": True,
        "rule_name": name,
        "enabled": enabled.lower() == "true",
        "allowed": allowed,
        "message": "防火墙规则已允许入站 TCP。" if allowed else "防火墙规则存在，但不是启用的入站允许规则。",
    }


def ensure_firewall_rule(port: int) -> dict[str, Any]:
    current = check_firewall_rule(port)
    if current.get("allowed") or not current.get("supported"):
        return current

    command = (
        f"$name = '{firewall_rule_name(port)}'; "
        "if (-not (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue)) { "
        f"{firewall_rule_command(port)} | Out-Null "
        "}"
    )
    try:
        result = _run_powershell(command, timeout=8)
    except (OSError, subprocess.TimeoutExpired) as exc:
        current["message"] = f"防火墙规则创建失败：{exc}"
        return current

    if result.returncode != 0:
        current["message"] = (result.stderr or "防火墙规则创建失败。").strip()
        return current

    return check_firewall_rule(port)


def runtime_host() -> str:
    return os.getenv("YOUBESTAR_SERVICE_HOST", "")


def runtime_port() -> int | None:
    try:
        return int(os.getenv("YOUBESTAR_SERVICE_PORT", ""))
    except ValueError:
        return None


def service_status(config: ServiceConfig | None = None) -> dict[str, Any]:
    loaded_config = config or load_service_config()
    host = effective_host(loaded_config)
    port = loaded_config.port
    lan_ip = detect_lan_ipv4()
    current_host = runtime_host()
    current_port = runtime_port()
    restart_required = bool(
        current_host
        and current_port
        and (current_host != host or current_port != port)
    )
    return {
        "lan_share_enabled": loaded_config.lan_share_enabled,
        "host": host,
        "port": port,
        "runtime_host": current_host,
        "runtime_port": current_port,
        "restart_required": restart_required,
        "local_url": f"http://{LOCAL_HOST}:{port}",
        "lan_ip": lan_ip,
        "lan_url": f"http://{lan_ip}:{port}",
        "config_path": str(service_config_file()),
        "firewall": check_firewall_rule(port),
        "firewall_command": firewall_rule_command(port),
    }


def update_lan_share(enabled: bool) -> dict[str, Any]:
    config = load_service_config()
    config.lan_share_enabled = enabled
    save_service_config(config)
    firewall = ensure_firewall_rule(config.port) if enabled else check_firewall_rule(config.port)
    status = service_status(config)
    status["firewall"] = firewall
    status["saved"] = True
    return status


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def schedule_restart() -> dict[str, Any]:
    start_script = PROJECT_ROOT / "start.bat"
    if not start_script.exists():
        raise HTTPException(status_code=500, detail="未找到 start.bat，无法重启服务。")
    if not sys.platform.startswith("win"):
        raise HTTPException(status_code=400, detail="当前只支持通过 Windows start.bat 重启服务。")

    script = (
        "Start-Sleep -Seconds 1; "
        f"Stop-Process -Id {os.getpid()} -Force; "
        "Start-Sleep -Milliseconds 800; "
        "Start-Process -FilePath 'cmd.exe' "
        f"-ArgumentList '/c', {_ps_quote(str(start_script))} "
        f"-WorkingDirectory {_ps_quote(str(PROJECT_ROOT))}"
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", script],
            close_fds=True,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"重启任务创建失败：{exc}") from exc

    return {"ok": True, "message": "重启任务已创建。", "status": service_status()}
