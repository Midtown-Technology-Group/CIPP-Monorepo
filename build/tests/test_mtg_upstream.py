import base64
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("mtg_upstream", Path(__file__).resolve().parents[1] / "tools/mtg_upstream.py")
UPSTREAM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPSTREAM)


class UpstreamTests(unittest.TestCase):
    def git(self, *args):
        return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL).decode().strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def setUp(self):
        self.original = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        os.chdir(self.temp.name)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("config", "commit.gpgsign", "false")
        Path("config.txt").write_text("upstream=old\n" + "context\n" * 8 + "midtown=off\n")
        Path("obsolete.txt").write_text("old\n")
        self.baseline = self.commit()
        self.git("checkout", "-qb", "mtg-production")
        Path(UPSTREAM.MARKER).write_text(self.baseline + "\n")
        Path("config.txt").write_text(Path("config.txt").read_text().replace("midtown=off", "midtown=on"))
        self.production = self.commit()

    def tearDown(self):
        os.chdir(self.original)
        self.temp.cleanup()

    def advance(self):
        self.git("checkout", "-q", "main")
        Path("config.txt").write_text(Path("config.txt").read_text().replace("upstream=old", "upstream=new"))
        Path("obsolete.txt").unlink()
        self.source = self.commit()
        self.git("checkout", "-q", "mtg-production")

    def test_same_upstream_is_a_clean_noop_after_squash(self):
        self.assertEqual(UPSTREAM.prepare("main"), {"changed": False, "source_sha": self.baseline})
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_delta_preserves_patch_and_tracks_exact_upstream(self):
        self.advance()
        result = UPSTREAM.prepare("main")
        self.assertTrue(result["changed"])
        self.assertIn("upstream=new", Path("config.txt").read_text())
        self.assertIn("midtown=on", Path("config.txt").read_text())
        self.assertFalse(Path("obsolete.txt").exists())
        self.assertEqual(Path(UPSTREAM.MARKER).read_text().strip(), self.source)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.production)
        payload = UPSTREAM.commit_payload("owner/repo", result)["variables"]["input"]
        self.assertEqual(payload["expectedHeadOid"], self.production)
        self.assertEqual(payload["fileChanges"]["deletions"], [{"path": "obsolete.txt"}])
        additions = {row["path"]: base64.b64decode(row["contents"]) for row in payload["fileChanges"]["additions"]}
        self.assertEqual(additions["config.txt"], Path("config.txt").read_bytes())

    def test_conflict_does_not_advance_marker_or_production(self):
        self.advance()
        Path("config.txt").write_text(Path("config.txt").read_text().replace("upstream=old", "upstream=midtown"))
        head = self.commit()
        with self.assertRaises(RuntimeError):
            UPSTREAM.prepare("main")
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(Path(UPSTREAM.MARKER).read_text().strip(), self.baseline)

    def test_dirty_checkout_is_rejected(self):
        Path("unrelated.txt").write_text("preserve\n")
        with self.assertRaisesRegex(RuntimeError, "dirty"):
            UPSTREAM.prepare("main")
        self.assertEqual(Path("unrelated.txt").read_text(), "preserve\n")

    def test_bad_marker_is_rejected(self):
        Path(UPSTREAM.MARKER).write_text("main\n")
        self.commit()
        with self.assertRaisesRegex(RuntimeError, "Invalid recorded"):
            UPSTREAM.prepare("main")

    def test_upstream_rewind_is_rejected(self):
        self.advance()
        Path(UPSTREAM.MARKER).write_text(self.source + "\n")
        self.commit()
        with self.assertRaises(RuntimeError):
            UPSTREAM.prepare(self.baseline)

    def test_unverified_or_wrong_tree_never_opens_pr(self):
        self.advance()
        update = UPSTREAM.prepare("main")
        for verified, tree in [(False, update["tree_sha"]), (True, "0" * 40)]:
            responses = [[], {"commit": {"sha": self.production}}, [], {},
                         {"data": {"createCommitOnBranch": {"commit": {"oid": "a" * 40}}}},
                         {"verification": {"verified": verified}, "tree": {"sha": tree}, "parents": [{"sha": self.production}]}]
            with patch.object(UPSTREAM, "api", side_effect=responses) as provider:
                with self.assertRaisesRegex(RuntimeError, "did not verify"):
                    UPSTREAM.publish("owner/repo", update)
                self.assertEqual(provider.call_count, 6)

    def test_verified_tree_opens_ready_pr_then_dispatches_validation(self):
        self.advance()
        update = UPSTREAM.prepare("main")
        head = "a" * 40
        responses = [[], {"commit": {"sha": self.production}}, [], {},
                     {"data": {"createCommitOnBranch": {"commit": {"oid": head}}}},
                     {"verification": {"verified": True}, "tree": {"sha": update["tree_sha"]}, "parents": [{"sha": self.production}]},
                     {"html_url": "https://github.com/owner/repo/pull/1"}, {"workflow_runs": []}, {}]
        with patch.object(UPSTREAM, "api", side_effect=responses) as provider:
            result = UPSTREAM.publish("owner/repo", update)
        self.assertEqual(result["head_sha"], head)
        self.assertFalse(provider.call_args_list[6].args[1]["draft"])
        self.assertTrue(provider.call_args_list[-1].args[0].endswith("/dispatches"))

    def test_existing_pr_and_run_are_reused_without_writes(self):
        self.advance()
        update = UPSTREAM.prepare("main")
        responses = [[{"head": {"sha": "a" * 40}, "html_url": "https://github.com/owner/repo/pull/1"}],
                     {"content": base64.b64encode((self.source + "\n").encode()).decode()},
                     {"workflow_runs": [{"id": 1}]}]
        with patch.object(UPSTREAM, "api", side_effect=responses) as provider:
            self.assertTrue(UPSTREAM.publish("owner/repo", update)["existing"])
        self.assertTrue(all(len(call.args) == 1 for call in provider.call_args_list))

    def test_changed_production_cannot_create_branch(self):
        self.advance()
        update = UPSTREAM.prepare("main")
        with patch.object(UPSTREAM, "api", side_effect=[[], {"commit": {"sha": "a" * 40}}]) as provider:
            with self.assertRaisesRegex(RuntimeError, "Production advanced"):
                UPSTREAM.publish("owner/repo", update)
            self.assertEqual(provider.call_count, 2)

    def test_empty_dispatch_response_is_success(self):
        with patch.object(UPSTREAM, "command", return_value=b""):
            self.assertEqual(UPSTREAM.api("dispatches", {"ref": "branch"}), {})


if __name__ == "__main__":
    unittest.main()
