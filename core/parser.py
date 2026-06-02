import json
import re


def parse_agent_output(response_text: str) -> dict:
    """
    Parse the model's structured agent output.

    Expected format:
    Thought: short decision summary
    Action: official.open_browser
    Params: {"url": "https://www.baidu.com"}
    Response: optional natural-language response
    """
    thought_match = re.search(r"Thought:\s*(.*?)(?=\n\s*Action:|\Z)", response_text, re.DOTALL)
    thought = thought_match.group(1).strip() if thought_match else ""

    action_match = re.search(r"Action:\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)", response_text)
    action = action_match.group(1) if action_match else "none"
    if action.lower() == "none":
        action = "none"

    response_match = re.search(r"Response:\s*(.*)\s*\Z", response_text, re.DOTALL)
    user_response = response_match.group(1).strip() if response_match else ""

    params_label = re.search(r"Params:\s*", response_text)
    if not params_label:
        return {"thought": thought, "action": action, "params": {}, "response": user_response}

    params_start = response_text.find("{", params_label.end())
    if params_start < 0:
        return {"thought": thought, "action": action, "params": {}, "response": user_response}

    try:
        params, _ = json.JSONDecoder().raw_decode(response_text[params_start:])
    except json.JSONDecodeError:
        params = {}

    return {
        "thought": thought,
        "action": action,
        "params": params if isinstance(params, dict) else {},
        "response": user_response,
    }


def parse_action(response_text: str) -> tuple[str, dict]:
    """
    Parse an action from model text.

    Expected format:
    Thought: ...
    Action: open_browser
    Params: {"url": "https://www.baidu.com"}
    """
    parsed = parse_agent_output(response_text)
    return parsed["action"], parsed["params"]
