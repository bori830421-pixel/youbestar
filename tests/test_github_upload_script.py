import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GitHubUploadScriptTest(unittest.TestCase):
    def test_upload_commits_local_changes_and_never_pulls(self):
        script = (ROOT / "github_upload.bat").read_text(encoding="utf-8")

        add_position = script.index("git add .")
        commit_position = script.index('git commit -m "%COMMIT_MSG%"')
        push_position = script.index('git push -u --force-with-lease origin "%BRANCH%"')

        self.assertLess(add_position, push_position)
        self.assertLess(commit_position, push_position)
        self.assertIn(
            'git fetch origin "+%BRANCH%:refs/remotes/origin/%BRANCH%"',
            script,
        )
        self.assertNotIn("git pull", script)

    def test_sync_stops_for_local_changes_and_never_pushes(self):
        script = (ROOT / "github_sync.bat").read_text(encoding="utf-8")

        dirty_check_position = script.index("git status --porcelain")
        fetch_position = script.index('git fetch origin "%BRANCH%"')
        pull_position = script.index('git pull --ff-only origin "%BRANCH%"')

        self.assertLess(dirty_check_position, fetch_position)
        self.assertLess(fetch_position, pull_position)
        self.assertNotIn("git push", script)


if __name__ == "__main__":
    unittest.main()
