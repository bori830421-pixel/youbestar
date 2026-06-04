import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from agent_system import file_access
from tools.file_access_tool import write_project_file


class ProjectFileWriteTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.original_roots = list(file_access.ALLOWED_READ_ROOTS)
        file_access.ALLOWED_READ_ROOTS = [self.root]

    def tearDown(self):
        file_access.ALLOWED_READ_ROOTS = self.original_roots
        self.temp_dir.cleanup()

    def test_write_project_file_creates_plain_file_inside_allowed_root(self):
        target = self.root / "notes" / "todo.md"

        result = file_access.write_allowed_file(str(target), "hello", overwrite=False)

        self.assertEqual(result["path"], str(target.resolve()))
        self.assertEqual(result["size"], 5)
        self.assertTrue(result["created"])
        self.assertEqual(target.read_text(encoding="utf-8"), "hello")

    def test_write_project_file_requires_overwrite_for_existing_file(self):
        target = self.root / "todo.md"
        target.write_text("old", encoding="utf-8")

        with self.assertRaises(HTTPException) as ctx:
            file_access.write_allowed_file(str(target), "new", overwrite=False)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(target.read_text(encoding="utf-8"), "old")

        file_access.write_allowed_file(str(target), "new", overwrite=True)
        self.assertEqual(target.read_text(encoding="utf-8"), "new")

    def test_write_project_file_blocks_sensitive_config(self):
        with self.assertRaises(HTTPException) as ctx:
            file_access.write_allowed_file(str(self.root / "youbestar.json"), "{}", overwrite=True)

        self.assertEqual(ctx.exception.status_code, 403)

    def test_tool_wrapper_returns_written_file_message(self):
        target = self.root / "hello.txt"

        result = write_project_file({"path": str(target), "content": "hello", "overwrite": False})

        self.assertIn("已写入项目文件", result)
        self.assertIn(str(target.resolve()), result)


if __name__ == "__main__":
    unittest.main()
