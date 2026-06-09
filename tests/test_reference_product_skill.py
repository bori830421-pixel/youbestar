import importlib
import unittest
from unittest.mock import patch

from agent_system.manager import run_approved_skill
from agent_system.skill_registry import canonical_skill_name


def load_reference_product_skill():
    try:
        return importlib.import_module("agent_system.skills.official.reference_product")
    except ModuleNotFoundError as exc:  # pragma: no cover - intentional contract failure until implemented
        raise AssertionError("Expected agent_system/skills/official/reference_product.py wrapper.") from exc


class ReferenceProductSkillTest(unittest.TestCase):
    def test_official_skill_wrapper_delegates_to_reference_product_tool(self):
        skill = load_reference_product_skill()
        expected = {
            "ok": True,
            "kind": "reference_product_cache_status",
            "title": "参考产品缓存状态",
            "data": {"cached_pages": 0},
        }

        with patch.object(skill, "run_reference_product", return_value=expected, create=True) as run_mock:
            result = skill.run({"operation": "cache_status"})

        self.assertEqual(result, expected)
        run_mock.assert_called_once_with({"operation": "cache_status"})

    def test_reference_product_is_registered_as_official_skill(self):
        self.assertEqual(canonical_skill_name("reference_product"), "official.reference_product")
        result = run_approved_skill("official.reference_product", {"operation": "cache_status"})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "reference_product_cache_status")


if __name__ == "__main__":
    unittest.main()
