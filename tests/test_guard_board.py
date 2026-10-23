import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, git, hook_payload, load, make_repo, run_script

load("hooks/decision_log.py")
guard = load("hooks/guard_board.py")

CODE = Path("/work/app")
BOARD = Path("/work/board")
PLAIN = Path("/work/plain")


def _repo(root: Path, **facts: object) -> object:
    values = {"is_board": False, "takes_board_work": False, "has_marker": False, "branch": "main", "protected": frozenset({"main", "master"})}
    return guard.Repo(root=root, **(values | facts))


REPOS = {
    CODE: _repo(CODE, takes_board_work=True),
    CODE / "feature": _repo(CODE, takes_board_work=True, branch="task-1-x"),
    CODE / "trunk": _repo(CODE, takes_board_work=True, branch="trunk", protected=frozenset({"main", "master", "trunk"})),
    BOARD: _repo(BOARD, is_board=True),
    PLAIN: _repo(PLAIN),
}


def lookup(directory: Path) -> object:
    return REPOS.get(Path(os.path.normpath(directory)))


def verdict(command: str, cwd: Path = PLAIN) -> object:
    return guard.decide_command(command, cwd, lookup).verdict


class BoardStatusTest(unittest.TestCase):
    def test_denies_setting_a_persons_status(self) -> None:
        for command in (
            "backlog task edit TASK-1 -s Done",
            'backlog task edit TASK-1 -s "To Do"',
            "backlog task edit TASK-1 -s 'to do'",
            "backlog task edit TASK-1 --status=done",
            "backlog task edit TASK-1 --status todo",
            "backlog task edit TASK-1 -sDone",
            "backlog task create 'New' -s 'To Do'",
            "backlog draft promote DRAFT-1",
            "backlog task promote DRAFT-1",
            "asdlc board task edit 1 -s Done",
            "asdlc --board ../board board task edit 1 -s 'To Do'",
            "uv run --quiet --script /plugin/scripts/asdlc board task edit 1 --status Done",
            "python3.15 scripts/asdlc board draft promote DRAFT-2",
            "npx --yes backlog.md task edit 1 -s done",
            "cd /work/board && FOO=1 backlog task edit 1 -s Done",
            "env BACKLOG_CWD=/x backlog task edit 1 -s Done",
            "echo start; backlog task edit 1 -s Done | cat",
            "git pull && backlog task edit 1 -s Done 2>&1",
            "bash -c 'backlog task edit 1 -s Done'",
            "echo $(backlog task edit 1 -s Done)",
            "backlog task list\nbacklog task edit 1 -s Done",
        ):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.DENY)

    def test_allows_everything_else_on_the_board(self) -> None:
        for command in (
            "backlog task list --plain",
            "backlog task view TASK-1 --plain",
            "asdlc board task edit 1 --append-notes 'set -s Done later'",
            "asdlc release TASK-1 --as agent-1",
            "asdlc next --as agent-1",
            "backlog task create 'Draft it' --draft",
            'echo "backlog task edit 1 -s Done"',
            "git commit -m 'backlog task edit -s Done'",
            "grep -rn 'status: Done' backlog/",
        ):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.ALLOW)

    def test_denies_an_agent_changing_who_holds_a_task_or_where_it_is(self) -> None:
        """B1: a worker's state changes go through asdlc claim, finish, release and review-done, which check the holder."""
        for command, says in (
            ("asdlc board task edit 1 --add-ref task-1-add-login -s 'In Review' --append-notes built", "asdlc finish"),
            ("backlog task edit TASK-1 -s 'In Review' --notes 'Done with the parser'", "asdlc finish"),
            ("backlog task edit 1 --status=in-review", "asdlc finish"),
            ('backlog task edit TASK-1 -s "In Progress" -a @agent-1', "asdlc claim"),
            ("asdlc board task edit 1 -s 'In Progress' -a @kyle.w2", "asdlc claim"),
            ("asdlc board task create 'X' --draft -s 'In Progress'", "asdlc claim"),
            ("asdlc board task edit 1 -a @kyle.w2", "asdlc claim"),
            ("backlog task edit 1 --assignee @ann.w1", "asdlc claim"),
            ("asdlc board task archive 1", "person's"),
            ("backlog task demote 1", "person's"),
            ("asdlc board task edit 1 --add-label review-passed", "asdlc review-done"),
            ("asdlc board task edit 1 --remove-label changes-requested", "asdlc finish"),
        ):
            with self.subTest(command=command):
                outcome = guard.decide_command(command, PLAIN, lookup)
                self.assertIs(outcome.verdict, guard.Verdict.DENY)
                self.assertIn(says, outcome.reason)
        for command in (
            "asdlc board task create 'Child' --draft -p DRAFT-1 -a @kyle",
            "asdlc board task edit 1 --add-label contract-change --comment 'the field is wrong'",
            "asdlc board task edit 1 --remove-label contract-change",
            "asdlc finish 1 --as kyle.w1 --pr https://github.com/acme/api/pull/1 --notes built",
            "asdlc board task edit 1 --plan '1. do it'",
        ):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.ALLOW)

    def test_denies_creating_accepted_work(self) -> None:
        for command in (
            "backlog task create 'New'",
            "backlog task create 'New' --type task -l size-2",
            "asdlc board task create 'New' --priority high",
            "uv run --script /plugin/scripts/asdlc board task create 'New'",
        ):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.DENY)
        outcome = guard.decide_command("backlog task create 'New'", PLAIN, lookup)
        self.assertIn("--draft", outcome.reason)

    def test_allows_creating_drafts(self) -> None:
        for command in (
            "backlog task create 'New' --draft",
            "asdlc board task create 'New' --draft --type task",
            "backlog draft create 'New'",
        ):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.ALLOW)

    def test_denies_an_agent_accepting_work(self) -> None:
        for command in (
            "asdlc accept TASK-3",
            "asdlc --board ../board accept DRAFT-1 --json",
            "uv run --quiet --script /plugin/scripts/asdlc accept 3",
            "cd /work/board && asdlc accept DRAFT-1",
            "bash -c 'asdlc accept DRAFT-1'",
        ):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.DENY)
        reason = guard.decide_command("asdlc accept DRAFT-1", PLAIN, lookup).reason
        self.assertIn("person's decision", reason)
        self.assertIn("their own terminal", reason)

    def test_denies_an_agent_approving_a_plan(self) -> None:
        """I7: plan approval is the person's, recorded by asdlc approve."""
        for command in ("asdlc approve TASK-3", "asdlc --board ../board approve 3 4", "bash -c 'asdlc approve 3'"):
            with self.subTest(command=command):
                outcome = guard.decide_command(command, PLAIN, lookup)
                self.assertIs(outcome.verdict, guard.Verdict.DENY)
                self.assertIn("their own terminal", outcome.reason)

    def test_allows_the_orchestrators_commands(self) -> None:
        for command in (
            "asdlc lead DRAFT-1 --as kyle.lead --json",
            "asdlc lead-of TASK-3.1",
            "asdlc heartbeat TASK-3.1 --as kyle.w1",
            "asdlc reap --older-than 2h",
            "asdlc mine --as kyle --json",
            "asdlc register",
            "asdlc record-check TASK-1 --as kyle.w1 -- ./scripts/check",
            "asdlc board task create 'Child' --draft -p DRAFT-1",
            "echo 'asdlc accept DRAFT-1'",
        ):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.ALLOW)

    def test_judges_the_command_a_recorded_check_runs(self) -> None:
        self.assertIs(verdict("asdlc record-check TASK-1 --as kyle.w1 -- backlog task edit 1 -s Done"), guard.Verdict.DENY)
        self.assertIs(verdict("asdlc record-check 1 --as kyle.w1 -- sh -c 'asdlc accept DRAFT-1'"), guard.Verdict.DENY)
        self.assertIs(verdict("asdlc record-check TASK-1 --as kyle.w1 -- git push origin main", CODE), guard.Verdict.DENY)

    def test_the_reason_points_at_the_person_and_at_release(self) -> None:
        outcome = guard.decide_command("backlog task edit 1 -s Done", PLAIN, lookup)
        self.assertIn("person's decision", outcome.reason)
        self.assertIn("asdlc release", outcome.reason)

    def test_an_unparsable_command_that_may_touch_the_board_is_allowed_and_said(self) -> None:
        self.assertIs(verdict("backlog task edit 1 -s 'Done"), guard.Verdict.ERROR)
        self.assertIs(verdict("echo 'unbalanced"), guard.Verdict.ALLOW)


class PushTest(unittest.TestCase):
    def test_denies_pushing_a_code_repositorys_default_branch(self) -> None:
        for command, cwd in (
            ("git push origin main", CODE),
            ("git push", CODE),
            ("git push -u origin HEAD", CODE),
            ("git push origin HEAD:main", CODE / "feature"),
            ("git push origin +task-1-x:refs/heads/main", CODE / "feature"),
            ("git push --force origin master", CODE / "feature"),
            ("git push --all origin", CODE / "feature"),
            ("git push --mirror", CODE / "feature"),
            ("git -C /work/app push origin main", PLAIN),
            ("cd /work/app && git push origin main", PLAIN),
            ("git push origin trunk", CODE / "trunk"),
            ("git -c push.default=current push", CODE),
        ):
            with self.subTest(command=command, cwd=cwd):
                self.assertIs(verdict(command, cwd), guard.Verdict.DENY)

    def test_denies_force_pushing_a_task_branch(self) -> None:
        """B2: a task branch's history is under review; a worker rebases onto origin/<branch> and pushes, never forces."""
        for command in ("git push --force-with-lease origin HEAD", "git push -f origin HEAD", "git push --force", "git push origin +HEAD",
                        "git push origin +task-1-x:task-1-x", "git push --force-if-includes --force-with-lease origin HEAD"):
            with self.subTest(command=command):
                outcome = guard.decide_command(command, CODE / "feature", lookup)
                self.assertIs(outcome.verdict, guard.Verdict.DENY)
                self.assertIn("rebase", outcome.reason)
        self.assertIs(verdict("git push --force origin main", BOARD), guard.Verdict.ALLOW)
        self.assertIs(verdict("git push --force origin x", PLAIN), guard.Verdict.ALLOW)

    def test_allows_other_pushes(self) -> None:
        for command, cwd in (
            ("git push", CODE / "feature"),
            ("git push -u origin task-1-x", CODE / "feature"),
            ("git push origin HEAD", CODE / "feature"),
            ("git push --tags", CODE),
            ("git push --no-verify origin HEAD:main", BOARD),
            ("git push origin main", PLAIN),
            ("git push origin main", Path("/nowhere")),
            ("git status && git log origin/main", CODE),
        ):
            with self.subTest(command=command, cwd=cwd):
                self.assertIs(verdict(command, cwd), guard.Verdict.ALLOW)

    def test_the_reason_says_what_to_do_instead(self) -> None:
        reason = guard.decide_command("git push origin main", CODE, lookup).reason
        self.assertIn("pull request", reason)


class PullRequestTest(unittest.TestCase):
    """Approving, requesting changes on and merging a pull request are a person's."""

    def reason(self, command: str) -> str:
        outcome = guard.decide_command(command, PLAIN, lookup)
        self.assertIs(outcome.verdict, guard.Verdict.DENY, command)
        return outcome.reason

    def test_denies_approving_or_requesting_changes(self) -> None:
        for command in (
            "gh pr review 12 --approve",
            "gh pr review https://github.com/acme/api/pull/12 -a -b 'Looks good'",
            "gh pr review 12 --request-changes --body 'x'",
            "gh pr review -r 12 -b x",
            "gh pr review 12 --approve=true",
            "cd /work/app && gh pr review 12 -R acme/api --approve",
            "sh -c 'gh pr review 12 --approve'",
        ):
            with self.subTest(command=command):
                self.assertIn("gh pr comment", self.reason(command))

    def test_denies_merging(self) -> None:
        for command in ("gh pr merge 12", "gh pr merge --squash --auto https://github.com/acme/api/pull/12", "env GH_TOKEN=x gh pr merge 12"):
            with self.subTest(command=command):
                self.assertIn("merging a pull request is a person's decision", self.reason(command))

    def test_denies_the_same_through_gh_api(self) -> None:
        cases = {
            "gh api -X PUT repos/acme/api/pulls/12/merge": "merging",
            "gh api --method=PUT /repos/{owner}/{repo}/pulls/12/merge -f merge_method=squash": "merging",
            "gh api repos/acme/api/pulls/12/merge -f commit_title=x": "merging",
            "gh api https://api.github.com/repos/acme/api/pulls/12/merge -XPUT": "merging",
            "gh api repos/acme/api/pulls/12/reviews -f event=APPROVE": "approving",
            "gh api repos/acme/api/pulls/12/reviews -F event=REQUEST_CHANGES -f body=x": "approving",
            "gh api repos/acme/api/pulls/12/reviews --field=event=approve": "approving",
            "gh api -X POST repos/acme/api/pulls/12/reviews/99/events -f event=APPROVE": "approving",
            "gh api graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"x\"}) { clientMutationId } }'": "merging",
            "gh api graphql -f query='mutation { addPullRequestReview(input: {pullRequestId: \"x\", event: APPROVE}) { clientMutationId } }'": "approving",
        }
        for command, says in cases.items():
            with self.subTest(command=command):
                self.assertIn(says, self.reason(command))

    def test_allows_comments_reads_and_everything_else(self) -> None:
        for command in (
            "gh pr review 12 --comment --body 'two findings'",
            "gh pr review 12 -c -b '-a is not a flag here'",
            "gh pr comment 12 --body 'Review by @kyle.r1'",
            "gh pr create --base main --head task-1-x --title t --body b",
            "gh pr view 12 --json state",
            "gh api repos/acme/api/pulls/12/merge",
            "gh api repos/acme/api/pulls/12/reviews",
            "gh api repos/acme/api/pulls/12/reviews -f event=COMMENT -f body=x",
            "gh api repos/acme/api/pulls/12/comments -f body=x",
            "gh api graphql -f query='query { viewer { login } }'",
            "gh auth status",
        ):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.ALLOW)

    def test_a_review_or_query_it_cannot_see_is_allowed_and_said(self) -> None:
        for command in ("gh api repos/acme/api/pulls/12/reviews --input review.json", "gh api graphql -F query=@mutation.graphql"):
            with self.subTest(command=command):
                outcome = guard.decide_command(command, PLAIN, lookup)
                self.assertIs(outcome.verdict, guard.Verdict.ERROR)
                self.assertIn("could not see", outcome.reason)

    def test_options(self) -> None:
        self.assertEqual(guard.options(["12", "-a", "-bbody", "--repo", "a/b", "--x=1", "--", "-r"], frozenset({"-b", "--repo"})),
                         (["12", "-r"], [("-a", ""), ("-b", "body"), ("--repo", "a/b"), ("--x", "1")]))


class ShellFormsTest(unittest.TestCase):
    """M2: the shell forms the review walked around the guard with."""

    def setUp(self) -> None:
        REPOS[Path.home() / "api"] = _repo(Path.home() / "api", takes_board_work=True)
        self.addCleanup(REPOS.pop, Path.home() / "api")

    def test_denied_through_home_dirs_loops_shells_and_xargs(self) -> None:
        for command in (
            "cd ~/api && git push origin main",
            "git -C ~/api push origin HEAD:main",
            "git -C ~/api/ push origin main",
            "for i in 1; do gh pr merge 3; done",
            "if true; then gh pr merge 3; fi",
            "if true; then echo; else gh pr merge 3; fi",
            "while true; do backlog task edit 1 -s Done; done",
            "until false; do asdlc accept DRAFT-1; done",
            "bash -lc 'gh pr merge 3'",
            "sh -ec 'asdlc approve 3'",
            "xargs gh pr merge < prs.txt",
            "xargs -n1 -I{} gh pr merge {} < prs.txt",
            "{ gh pr merge 3; }",
            "! gh pr merge 3",
        ):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.DENY)

    def test_an_unexpanded_directory_is_allowed_and_said(self) -> None:
        for command in ("WT=/work/app; git -C $WT push origin HEAD:main", 'cd "$WT" && git push origin main', "git -C ${REPO} push origin main"):
            with self.subTest(command=command):
                outcome = guard.decide_command(command, PLAIN, lookup)
                self.assertIs(outcome.verdict, guard.Verdict.ERROR)
                self.assertIn("can't tell", outcome.reason)
        self.assertIs(verdict("cd $WT && npm test"), guard.Verdict.ALLOW)
        self.assertIs(verdict("for f in *.py; do echo $f; done"), guard.Verdict.ALLOW)


class DecideFileTest(unittest.TestCase):
    def test_board_files(self) -> None:
        board = REPOS[BOARD]
        denied = guard.decide_file(BOARD / "backlog" / "tasks" / "task-1 - x.md", board)
        self.assertIs(denied.verdict, guard.Verdict.DENY)
        self.assertIn("change the board with asdlc board, so it is committed and pushed", denied.reason)
        self.assertIs(guard.decide_file(BOARD / "backlog" / "config.yml", board).verdict, guard.Verdict.DENY)
        self.assertIs(guard.decide_file(BOARD / "README.md", board).verdict, guard.Verdict.ALLOW)

    def test_code_needs_a_claimed_worktree(self) -> None:
        denied = guard.decide_file(CODE / "src" / "app.py", REPOS[CODE])
        self.assertIs(denied.verdict, guard.Verdict.DENY)
        self.assertIn("claim a task first: asdlc next or asdlc claim", denied.reason)
        claimed = _repo(Path("/work/app.worktrees/task-1"), takes_board_work=True, has_marker=True)
        self.assertIs(guard.decide_file(claimed.root / "src" / "app.py", claimed).verdict, guard.Verdict.ALLOW)

    def test_everything_else_is_allowed(self) -> None:
        self.assertIs(guard.decide_file(PLAIN / "a.py", REPOS[PLAIN]).verdict, guard.Verdict.ALLOW)
        self.assertIs(guard.decide_file(Path("/tmp/x"), None).verdict, guard.Verdict.ALLOW)


class ParsingTest(unittest.TestCase):
    def test_simple_commands(self) -> None:
        self.assertEqual(
            guard.simple_commands("cd /x && A=1 backlog task list | head -2; echo 'a b' > out.txt 2>&1"),
            [["cd", "/x"], ["A=1", "backlog", "task", "list"], ["head", "-2"], ["echo", "a b", "2"]],
        )

    def test_unwrap(self) -> None:
        self.assertEqual(guard.unwrap(["uv", "run", "--quiet", "--script", "s/asdlc", "board"]), ["s/asdlc", "board"])
        self.assertEqual(guard.unwrap(["env", "A=1", "sudo", "backlog", "x"]), ["backlog", "x"])
        self.assertEqual(guard.unwrap(["npx", "-y", "backlog.md", "x"]), ["backlog.md", "x"])

    def test_push_destinations(self) -> None:
        self.assertEqual(guard.push_destinations(["origin"], "dev"), {"dev"})
        self.assertEqual(guard.push_destinations(["-o", "ci.skip", "origin", "a", "b:refs/heads/c"], "dev"), {"a", "c"})
        self.assertEqual(guard.push_destinations(["--all"], "dev"), {"*"})
        self.assertEqual(guard.push_destinations(["--tags", "origin"], "dev"), frozenset())


class BacklogMcpTest(unittest.TestCase):
    """I8: Backlog.md's MCP tools change the board with no push and no checks, so the guard allows their reads and refuses their writes."""

    def test_reads_are_allowed_and_writes_refused(self) -> None:
        for tool in ("mcp__backlog__task_view", "mcp__backlog__task_list", "mcp__Backlog_md__task_search", "mcp__backlog__document_view",
                     "mcp__backlog__document_list", "mcp__plugin_tasks_backlog__get_workflow_overview", "mcp__backlog__definition_of_done_defaults_get",
                     "mcp__backlog__milestone_list", "mcp__github__create_issue", "mcp__memory__write"):
            with self.subTest(tool=tool):
                self.assertIs(guard.decide_mcp(tool).verdict, guard.Verdict.ALLOW)
        for tool in ("mcp__backlog__task_create", "mcp__backlog__task_edit", "mcp__Backlog_md__task_archive", "mcp__backlog__task_delete",
                     "mcp__backlog__task_restore", "mcp__backlog__document_create", "mcp__backlog__document_update", "mcp__backlog__milestone_add",
                     "mcp__backlog__definition_of_done_defaults_upsert", "mcp__backlog__draft_promote", "mcp__BACKLOG__something_new"):
            with self.subTest(tool=tool):
                outcome = guard.decide_mcp(tool)
                self.assertIs(outcome.verdict, guard.Verdict.DENY)
                self.assertIn("asdlc board", outcome.reason)

    def test_hooks_json_sends_backlog_mcp_tools_to_the_guard(self) -> None:
        config = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        groups = [g for g in config["hooks"]["PreToolUse"] if any("guard_board.py" in h["command"] for h in g["hooks"])]
        for tool in ("mcp__backlog__task_edit", "mcp__Backlog_md__task_create", "mcp__plugin_tasks_backlog__task_edit"):
            with self.subTest(tool=tool):
                self.assertTrue(any(re.search(g["matcher"], tool) for g in groups if not re.fullmatch(r"[\w\s,|-]*", g["matcher"])), tool)
        self.assertFalse(any(re.search(g["matcher"], "mcp__github__create_issue") for g in groups if "mcp" in g["matcher"]))


class GuardHookTest(unittest.TestCase):
    """The hook as Claude Code runs it, against real repositories."""

    def setUp(self) -> None:
        self.handle, self.code = make_repo()
        self.board_handle, self.board = make_repo()
        (self.board / "backlog").mkdir()
        (self.board / "backlog" / "config.yml").write_text('project_name: "b"\n')
        git(self.code, "config", "asdlc.board", str(self.board))
        self.worktree = Path(tempfile.mkdtemp()) / "task-1"
        git(self.code, "worktree", "add", "-q", "-b", "task-1-x", str(self.worktree))
        (self.worktree / ".asdlc-task").write_text('{"task": "TASK-1"}\n')

    def tearDown(self) -> None:
        git(self.code, "worktree", "remove", "--force", str(self.worktree))
        shutil.rmtree(self.worktree.parent, ignore_errors=True)
        self.handle.cleanup()
        self.board_handle.cleanup()

    def run_hook(self, cwd: Path, tool: str, **tool_input: str) -> subprocess.CompletedProcess[str]:
        return run_script("hooks/guard_board.py", stdin=hook_payload(cwd, tool, **tool_input), cwd=cwd, env={"CLAUDE_PROJECT_DIR": str(cwd)})

    def decision(self, done: subprocess.CompletedProcess[str]) -> str:
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"] if done.stdout else "allow"

    def log(self, project: Path) -> list[dict[str, str]]:
        return [json.loads(line) for line in (project / ".asdlc" / "hooks.jsonl").read_text().splitlines()]

    def test_denies_a_backlog_mcp_write_and_logs_it(self) -> None:
        done = self.run_hook(self.board, "mcp__backlog__task_edit", id="TASK-1", status="In Review")
        self.assertEqual(self.decision(done), "deny")
        self.assertEqual(self.log(self.board)[-1]["verdict"], "deny")
        self.assertEqual(self.decision(self.run_hook(self.board, "mcp__backlog__task_view", id="TASK-1")), "allow")

    def test_denies_a_hand_edit_of_the_board_and_logs_it(self) -> None:
        done = self.run_hook(self.board, "Edit", file_path=str(self.board / "backlog" / "tasks" / "task-1 - x.md"))
        self.assertEqual(self.decision(done), "deny")
        entry = self.log(self.board)[-1]
        self.assertEqual((entry["hook"], entry["verdict"], entry["tool"]), ("guard_board", "deny", "Edit"))

    def test_denies_code_outside_a_claimed_worktree(self) -> None:
        self.assertEqual(self.decision(self.run_hook(self.code, "Write", file_path="src/new.py")), "deny")
        self.assertEqual(self.decision(self.run_hook(self.code, "NotebookEdit", notebook_path=str(self.code / "n.ipynb"))), "deny")

    def test_allows_code_inside_a_claimed_worktree(self) -> None:
        self.assertEqual(self.decision(self.run_hook(self.worktree, "Write", file_path=str(self.worktree / "src" / "deep" / "new.py"))), "allow")

    def test_allows_any_edit_in_a_repository_without_a_board(self) -> None:
        handle, plain = make_repo()
        self.addCleanup(handle.cleanup)
        self.assertEqual(self.decision(self.run_hook(plain, "Edit", file_path=str(plain / "README.md"))), "allow")

    def test_denies_a_push_to_main_and_allows_the_task_branch_and_the_board(self) -> None:
        self.assertEqual(self.decision(self.run_hook(self.code, "Bash", command="git push origin main")), "deny")
        self.assertEqual(self.decision(self.run_hook(self.worktree, "Bash", command="git push -u origin task-1-x")), "allow")
        self.assertEqual(self.decision(self.run_hook(self.board, "Bash", command="git push --no-verify origin HEAD:main")), "allow")

    def test_denies_setting_done_from_the_shell(self) -> None:
        self.assertEqual(self.decision(self.run_hook(self.code, "Bash", command="backlog task edit 1 -s Done")), "deny")

    def test_denies_accepting_work_and_logs_it(self) -> None:
        done = self.run_hook(self.board, "Bash", command="asdlc accept DRAFT-1")
        self.assertEqual(self.decision(done), "deny")
        self.assertIn("asdlc accept", json.loads(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(self.log(self.board)[-1]["verdict"], "deny")

    def test_denies_approving_and_merging_and_logs_it(self) -> None:
        for command in ("gh pr review 3 --approve", "gh pr merge 3", "gh api -X PUT repos/a/b/pulls/3/merge"):
            with self.subTest(command=command):
                done = self.run_hook(self.worktree, "Bash", command=command)
                self.assertEqual(self.decision(done), "deny")
                self.assertIn("a person's decision", json.loads(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"])
                self.assertEqual(self.log(self.worktree)[-1]["verdict"], "deny")

    def test_says_so_when_it_cannot_parse(self) -> None:
        done = self.run_hook(self.code, "Bash", command="backlog task edit 1 -s 'Done")
        self.assertEqual(done.returncode, 0)
        self.assertIn("could not parse", json.loads(done.stdout)["systemMessage"])
        self.assertEqual(self.log(self.code)[-1]["verdict"], "error")

    def test_a_broken_payload_allows_says_so_and_logs_it(self) -> None:
        done = run_script("hooks/guard_board.py", stdin="not json", cwd=self.code, env={"CLAUDE_PROJECT_DIR": str(self.code)})
        self.assertEqual(done.returncode, 0)
        self.assertIn("failed and allowed the change", done.stderr)
        self.assertIn("failed and allowed the change", json.loads(done.stdout)["systemMessage"])
        self.assertEqual(self.log(self.code)[-1]["verdict"], "error")


class HookCommandTest(unittest.TestCase):
    """The board guard's shell command in hooks.json, which wraps uv like the test-edit guard's."""

    def command(self) -> str:
        config = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        group = config["hooks"]["PreToolUse"][0]
        self.assertEqual(group["matcher"], "Edit|Write|NotebookEdit|Bash")
        return next(hook["command"] for hook in group["hooks"] if "guard_board.py" in hook["command"])

    def run_with_fake_uv(self, exit_code: int) -> subprocess.CompletedProcess[str]:
        bin_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bin_dir)
        fake = bin_dir / "uv"
        fake.write_text(f"#!/bin/sh\nexit {exit_code}\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env = {**os.environ, "PATH": f"{bin_dir}:/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        return subprocess.run(["sh", "-c", self.command()], input="{}", text=True, capture_output=True, env=env)

    def test_uv_failing_to_start_never_blocks_and_says_so(self) -> None:
        done = self.run_with_fake_uv(2)
        self.assertEqual(done.returncode, 1)
        self.assertIn("board guard", done.stderr)

    def test_the_guard_exit_code_passes_through(self) -> None:
        self.assertEqual(self.run_with_fake_uv(0).returncode, 0)

    def test_missing_uv_never_blocks(self) -> None:
        env = {**os.environ, "PATH": "/nonexistent", "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        done = subprocess.run(["/bin/sh", "-c", self.command()], input="{}", text=True, capture_output=True, env=env)
        self.assertEqual(done.returncode, 1)
        self.assertIn("uv is not installed, so the board guard did not run", done.stderr)


if __name__ == "__main__":
    unittest.main()
