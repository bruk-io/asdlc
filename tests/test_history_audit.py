import json
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, commit_file, git, load, make_repo, run_script

audit = load("scripts/history_audit.py")


def commit(sha: str, time: int, *files: str):
    return audit.Commit(sha, time, tuple(files))


def pull(number: int = 10, commits=(), files=None, plan_status=None, plan_text="", changelog=True, checks=None, merged: int = 100000):
    return audit.Pull(number, "a change", merged, tuple(commits), files or {}, plan_status or {}, plan_text, changelog, checks)


APPROVED = {"plan/x.md": "approved by the owner"}
GOOD_FILES = {"plan/x.md": "A", "scripts/tool.py": "M", "tests/test_tool.py": "M", "CHANGELOG.md": "M"}
GOOD_COMMITS = (commit("aaaaaaa", 10, "plan/x.md"), commit("bbbbbbb", 20, "scripts/tool.py", "tests/test_tool.py", "CHANGELOG.md"))


def rules(p) -> list[str]:
    return [f.rule for f in audit.audit_pull(p)]


class RuleTest(unittest.TestCase):
    def test_a_pull_request_that_follows_every_rule_has_no_findings(self) -> None:
        self.assertEqual(rules(pull(commits=GOOD_COMMITS, files=GOOD_FILES, plan_status=APPROVED)), [])

    def test_h1_a_plugin_change_without_a_plan(self) -> None:
        found = audit.audit_pull(pull(files={"skills/a/SKILL.md": "M", "CHANGELOG.md": "M"}))
        self.assertEqual([f.rule for f in found], ["H1"])
        self.assertIn("carries no plan", found[0].message)

    def test_h1_is_quiet_for_documents_and_for_a_deleted_plan_only(self) -> None:
        self.assertEqual(rules(pull(files={"docs/guide.md": "M", "intent/a.md": "A"})), [])
        self.assertEqual(rules(pull(files={"skills/a/SKILL.md": "M", "plan/x.md": "D", "CHANGELOG.md": "M"})), ["H1"])

    def test_h2_the_plan_must_not_come_after_the_code(self) -> None:
        late = (commit("ccccccc", 10, "scripts/tool.py", "tests/test_tool.py", "CHANGELOG.md"), commit("ddddddd", 20, "plan/x.md"))
        found = audit.audit_pull(pull(commits=late, files=GOOD_FILES, plan_status=APPROVED))
        self.assertEqual([f.rule for f in found], ["H2"])
        self.assertIn("ccccccc", found[0].message)

    def test_h2_the_plan_and_the_code_in_one_commit_is_fine(self) -> None:
        one = (commit("eeeeeee", 10, "plan/x.md", "scripts/tool.py", "tests/test_tool.py", "CHANGELOG.md"),)
        self.assertEqual(rules(pull(commits=one, files=GOOD_FILES, plan_status=APPROVED)), [])

    def test_h2_and_h3_leave_alone_a_plan_that_was_already_on_main(self) -> None:
        files = {**GOOD_FILES, "plan/x.md": "M"}
        late = (commit("ccccccc", 10, "scripts/tool.py", "tests/test_tool.py", "CHANGELOG.md"), commit("ddddddd", 20, "plan/x.md"))
        self.assertEqual(rules(pull(commits=late, files=files, plan_status={"plan/x.md": "draft. Merging this file approves it"})), [])

    def test_h3_a_new_plan_still_a_draft_with_code(self) -> None:
        found = audit.audit_pull(pull(commits=GOOD_COMMITS, files=GOOD_FILES, plan_status={"plan/x.md": "draft. Merging approves"}))
        self.assertEqual([f.rule for f in found], ["H3"])

    def test_h3_a_plan_only_pull_request_may_be_a_draft(self) -> None:
        self.assertEqual(rules(pull(files={"plan/x.md": "A"}, plan_status={"plan/x.md": "draft"})), [])

    def test_h4_the_suite_and_the_plugin_together(self) -> None:
        files = {**GOOD_FILES, "evals/cases/a/case.toml": "A"}
        self.assertEqual(rules(pull(commits=GOOD_COMMITS, files=files, plan_status=APPROVED)), ["H4"])

    def test_h5_a_script_without_a_test(self) -> None:
        files = {"plan/x.md": "A", "scripts/tool.py": "M", "CHANGELOG.md": "M"}
        self.assertEqual(rules(pull(files=files, plan_status=APPROVED)), ["H5"])

    def test_h5_data_and_prose_under_scripts_need_no_test(self) -> None:
        files = {"plan/x.md": "A", "scripts/waivers.toml": "M", "hooks/hooks.json": "M", "CHANGELOG.md": "M"}
        self.assertEqual(rules(pull(files=files, plan_status=APPROVED)), [])

    def test_h6_a_plugin_change_without_a_changelog_line(self) -> None:
        files = {k: v for k, v in GOOD_FILES.items() if k != "CHANGELOG.md"}
        self.assertEqual(rules(pull(commits=GOOD_COMMITS, files=files, plan_status=APPROVED)), ["H6"])

    def test_h6_waits_for_a_changelog_to_exist(self) -> None:
        files = {k: v for k, v in GOOD_FILES.items() if k != "CHANGELOG.md"}
        self.assertEqual(rules(pull(commits=GOOD_COMMITS, files=files, plan_status=APPROVED, changelog=False)), [])

    def test_h7_a_required_check_that_was_not_green(self) -> None:
        checks = (("check", "failure"), ("protected-paths", "success"))
        found = audit.audit_pull(pull(commits=GOOD_COMMITS, files=GOOD_FILES, plan_status=APPROVED, checks=checks))
        self.assertEqual([f.rule for f in found], ["H7"])
        self.assertIn("check failure", found[0].message)

    def test_h7_says_nothing_without_an_export_or_for_a_pull_request_with_no_checks(self) -> None:
        self.assertEqual(rules(pull(commits=GOOD_COMMITS, files=GOOD_FILES, plan_status=APPROVED, checks=None)), [])
        self.assertEqual(rules(pull(commits=GOOD_COMMITS, files=GOOD_FILES, plan_status=APPROVED, checks=())), [])


class JudgementTest(unittest.TestCase):
    def test_a_pull_request_before_the_loop_is_listed_and_not_judged(self) -> None:
        found = audit.audit([pull(number=2, files={"scripts/a.py": "A"})])
        self.assertTrue(found and not any(f.judged for f in found))
        self.assertEqual(audit.failing(found), [])

    def test_a_waiver_keeps_the_finding_listed_and_stops_it_failing(self) -> None:
        waivers = [{"pr": 10, "rule": "H1", "reason": "a one-line fix", "accepted_by": "the owner"}]
        found = audit.audit([pull(files={"skills/a/SKILL.md": "M", "CHANGELOG.md": "M"})], waivers)
        self.assertEqual(len(found), 1)
        self.assertIn("a one-line fix (accepted by the owner)", found[0].waived)
        self.assertEqual(audit.failing(found), [])
        self.assertIn("[waived:", str(found[0]))

    def test_the_branch_audit_is_always_judged(self) -> None:
        self.assertEqual(len(audit.failing(audit.audit([pull(number=0, files={"skills/a/SKILL.md": "M", "CHANGELOG.md": "M"})]))), 1)


class IndicatorTest(unittest.TestCase):
    def test_lead_time_rework_and_plan_match(self) -> None:
        commits = (commit("a", 0, "plan/x.md"), commit("b", 3600, "scripts/tool.py"), commit("c", 7200, "plan/x.md"))
        i = audit.indicators(pull(commits=commits, files={"plan/x.md": "A", "scripts/tool.py": "M", "scripts/other.py": "M"},
                                  plan_status=APPROVED, plan_text="Changes scripts/tool.py", merged=10800))
        self.assertEqual((i.commits, i.lead_hours, i.plan_after_code), (3, 3.0, 1))
        self.assertEqual(i.plan_match, 0.5)

    def test_no_plan_means_no_match_figure(self) -> None:
        self.assertIsNone(audit.indicators(pull(commits=GOOD_COMMITS, files={"scripts/a.py": "M"})).plan_match)


class GitShellTest(unittest.TestCase):
    """The shell, on a real throwaway history of two merged pull requests."""

    def merge(self, repo: Path, branch: str, number: int, files: dict[str, str]) -> None:
        git(repo, "switch", "-q", "-c", branch)
        for path, text in files.items():
            commit_file(repo, path, text)
        git(repo, "switch", "-q", "main")
        git(repo, "merge", "-q", "--no-ff", branch, "-m", f"Merge pull request #{number} from owner/{branch}")

    def test_the_history_is_read_as_pull_requests(self) -> None:
        handle, repo = make_repo()
        self.addCleanup(handle.cleanup)
        self.merge(repo, "plan/a", 4, {"plan/a.md": "# Plan\n\n- Status: approved by the owner\n"})
        self.merge(repo, "build/a", 5, {"scripts/tool.py": "x\n", "CHANGELOG.md": "x\n"})
        pulls = audit.read_history(repo, "main", {})
        self.assertEqual([p.number for p in pulls], [4, 5])
        self.assertEqual(pulls[0].files, {"plan/a.md": "A"})
        self.assertEqual(pulls[0].plan_status, {"plan/a.md": "approved by the owner"})
        self.assertEqual(pulls[1].title, "build/a")
        found = audit.audit(pulls)
        self.assertEqual(sorted(f.rule for f in found), ["H1", "H5"])  # a script with no plan and no test

    def test_the_branch_range_is_audited_as_one_pull_request(self) -> None:
        handle, repo = make_repo()
        self.addCleanup(handle.cleanup)
        git(repo, "switch", "-q", "-c", "work")
        commit_file(repo, "skills/a/SKILL.md", "x\n")
        done = run_script("scripts/history_audit.py", str(repo), "--range", "main..work")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("#0 H1", done.stdout)

    def test_the_command_reads_exported_checks_and_waivers(self) -> None:
        handle, repo = make_repo()
        self.addCleanup(handle.cleanup)
        self.merge(repo, "plan/a", 4, {"plan/a.md": "# Plan\n\n- Status: approved\n"})
        self.merge(repo, "build/a", 5, {"scripts/tool.py": "x\n", "tests/test_tool.py": "x\n", "plan/a.md": "# Plan\n\n- Status: approved\nmore\n", "CHANGELOG.md": "x\n"})
        (repo / "pulls.json").write_text(json.dumps([{"number": 5, "checks": [{"name": "check", "conclusion": "failure"}]}]))
        done = run_script("scripts/history_audit.py", str(repo), "--ref", "main", "--pulls", str(repo / "pulls.json"))
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("#5 H7", done.stdout)
        (repo / "scripts").mkdir(exist_ok=True)
        (repo / "scripts" / "history_waivers.toml").write_text('[[waiver]]\npr = 5\nrule = "H7"\nreason = "rerun green"\naccepted_by = "the owner"\n')
        done = run_script("scripts/history_audit.py", str(repo), "--ref", "main", "--pulls", str(repo / "pulls.json"))
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("1 waived", done.stdout)


class ShallowCloneTest(unittest.TestCase):
    def test_a_shallow_clone_is_refused_with_the_fix(self) -> None:
        handle, repo = make_repo()
        self.addCleanup(handle.cleanup)
        commit_file(repo, "a.txt")
        with tempfile.TemporaryDirectory() as folder:
            clone = Path(folder) / "shallow"
            git(repo, "clone", "-q", "--depth", "1", f"file://{repo}", str(clone))
            done = run_script("scripts/history_audit.py", str(clone))
            self.assertEqual(done.returncode, 2, done.stdout)
            self.assertIn("shallow", done.stdout)


class RealRepositoryTest(unittest.TestCase):
    @unittest.skipIf(git(ROOT, "rev-parse", "--is-shallow-repository") == "true", "CI checks out one commit; the audit needs the history")
    def test_this_repository_can_be_read(self) -> None:
        pulls = audit.read_history(ROOT, "HEAD", {})
        self.assertTrue(pulls)
        self.assertTrue(all(isinstance(f, audit.Finding) for f in audit.audit(pulls)))


if __name__ == "__main__":
    unittest.main()
