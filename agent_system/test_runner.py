import importlib.util
import sys
from pathlib import Path


def load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python -m agent_system.test_runner <skill_file> <test_file>", file=sys.stderr)
        return 2

    skill_path = Path(sys.argv[1]).resolve()
    test_path = Path(sys.argv[2]).resolve()
    skill_module = load_module("skill_under_test", skill_path)
    sys.modules[skill_path.stem] = skill_module

    test_module = load_module("skill_test_module", test_path)
    setattr(test_module, "skill_under_test", skill_module)

    tests = [
        getattr(test_module, name)
        for name in dir(test_module)
        if name.startswith("test_") and callable(getattr(test_module, name))
    ]
    if not tests:
        print("No test functions found.")
        return 1

    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
