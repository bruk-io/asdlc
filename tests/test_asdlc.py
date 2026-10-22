import json
import os
import random
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, git, load, run_script

asdlc = load("scripts/asdlc")

BACKLOG = os.environ.get("ASDLC_BACKLOG") or shutil.which("backlog")
# Tests that drive the real CLI skip on a machine without it, but never in CI, where a
# missing backlog must fail rather than pass by skipping.
needs_backlog = unittest.skipIf(BACKLOG is None and not os.environ.get("CI"), "the backlog CLI is not installed")

# Every git and backlog call in these tests: no global or system git config (no signing,
# no hooks path), and a fixed identity.
ISOLATED = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def task(task_id: str, **fields: object) -> object:
    values = {
        "title": "A task", "status": "To Do", "assignees": (), "labels": ("size-2",), "priority": "",
        "type": "task", "parent": "", "ordinal": None, "dependencies": (), "path": "",
    } | fields
    return asdlc.Task(id=task_id, **values)


# --- the logic -------------------------------------------------------------------------


class FrontmatterTest(unittest.TestCase):
    def test_reads_what_backlog_writes(self) -> None:
        text = (
            "---\nid: TASK-2\ntitle: >-\n  A very long title: with a colon, it's got quotes \"double\"\n"
            "  and more words\nstatus: In Progress\nassignee:\n  - '@someone'\n  - '@other'\n"
            "labels:\n  - size-2\n  - 'area: x'\ndependencies: []\nparent_task_id: TASK-1\n"
            "priority: high\ntype: task\nordinal: 3000\n---\n\n## Description\n"
        )
        found = asdlc.task_from("backlog/tasks/task-2 - x.md", text)
        self.assertEqual(found.id, "TASK-2")
        self.assertEqual(found.title, 'A very long title: with a colon, it\'s got quotes "double" and more words')
        self.assertEqual(found.assignees, ("@someone", "@other"))
        self.assertEqual(found.labels, ("size-2", "area: x"))
        self.assertEqual((found.status, found.parent, found.priority, found.ordinal), ("In Progress", "TASK-1", "high", 3000.0))
        self.assertEqual(found.dependencies, ())

    def test_quoted_scalars_and_flow_lists(self) -> None:
        fields = asdlc.frontmatter("---\ntitle: 'It''s 123'\nlabels: [\"size-1\", 'b, c']\nempty: []\nname: \"a\\\"b\"\n---\n")
        self.assertEqual(fields["title"], "It's 123")
        self.assertEqual(fields["labels"], ("size-1", "b, c"))
        self.assertEqual(fields["empty"], ())
        self.assertEqual(fields["name"], 'a"b')

    def test_no_frontmatter_is_no_task(self) -> None:
        self.assertIsNone(asdlc.task_from("x.md", "# just a heading\n"))
        self.assertIsNone(asdlc.task_from("x.md", "---\ntitle: no id\n---\n"))


class RouteTest(unittest.TestCase):
    def routed(self, subject: object, *others: object) -> object:
        return asdlc.route(subject, (subject, *others))

    def test_planning_work_goes_to_opus_high(self) -> None:
        for kind in ("intent", "spike"):
            with self.subTest(type=kind):
                chosen = self.routed(task("TASK-1", type=kind, labels=()))
                self.assertEqual((chosen.model, chosen.effort), ("opus", "high"))
        parent = self.routed(task("TASK-1", labels=("size-8",)), task("TASK-1.1", parent="TASK-1"))
        self.assertEqual((parent.model, parent.effort), ("opus", "high"))
        self.assertIn("child tasks", parent.reason)

    def test_sizes(self) -> None:
        for kind in ("task", "bug"):
            for size, expected in (("size-1", ("haiku", "default")), ("size-2", ("sonnet", "medium")),
                                   ("size-3", ("sonnet", "medium")), ("size-4", ("sonnet", "medium")),
                                   ("size-5", ("sonnet", "medium"))):
                with self.subTest(type=kind, size=size):
                    chosen = self.routed(task("TASK-1", type=kind, labels=(size, "area")))
                    self.assertIsInstance(chosen, asdlc.Route)
                    self.assertEqual((chosen.model, chosen.effort), expected)

    def test_size_1_says_its_plan_needs_numbered_steps(self) -> None:
        self.assertIn("numbered steps", self.routed(task("TASK-1", labels=("size-1",))).reason)

    def test_refusals(self) -> None:
        cases = {
            ("size-8",): "split it before it starts",
            (): "exactly one size label is needed",
            ("size-2", "size-3"): "exactly one size label is needed",
            ("size-13",): "isn't a size this board routes",
        }
        for labels, says in cases.items():
            with self.subTest(labels=labels):
                chosen = self.routed(task("TASK-1", labels=labels))
                self.assertIsInstance(chosen, asdlc.Refusal)
                self.assertIn(says, chosen.reason)

    def test_the_table_covers_every_configured_size(self) -> None:
        self.assertEqual(set(asdlc.SIZE_ROUTES), set(asdlc.SIZE_LABELS))


class CandidatesTest(unittest.TestCase):
    def test_orders_by_priority_then_ordinal_then_id(self) -> None:
        tasks = (
            task("TASK-10", priority="low"),
            task("TASK-2"),
            task("TASK-9", priority="high", ordinal=2000.0),
            task("TASK-3", priority="high", ordinal=1000.0),
            task("TASK-4", priority="medium"),
            task("TASK-1.10", priority="medium"),
            task("TASK-1.2", priority="medium"),
        )
        ready, _ = asdlc.candidates(tasks)
        self.assertEqual([t.id for t in ready], ["TASK-3", "TASK-9", "TASK-1.2", "TASK-1.10", "TASK-4", "TASK-10", "TASK-2"])

    def test_skips_claimed_started_parent_waiting_and_unroutable_tasks(self) -> None:
        tasks = (
            task("TASK-1", assignees=("@agent-1",)),
            task("TASK-2", status="In Progress"),
            task("TASK-3", type="intent"),
            task("TASK-3.1", parent="TASK-3"),
            task("TASK-4", dependencies=("TASK-2",)),
            task("TASK-5", dependencies=("TASK-6",)),
            task("TASK-6", status="Done"),
            task("TASK-7", labels=("size-8",)),
            task("TASK-8", labels=()),
        )
        ready, skipped = asdlc.candidates(tasks)
        self.assertEqual([t.id for t in ready], ["TASK-3.1", "TASK-5"])
        self.assertEqual({t.id for t, _ in skipped}, {"TASK-4", "TASK-7", "TASK-8"})


class ClaimDecisionsTest(unittest.TestCase):
    def test_claim_refusal(self) -> None:
        open_task = task("TASK-1")
        self.assertIsNone(asdlc.claim_refusal(open_task, "TASK-1", (open_task,)))
        self.assertIn("not a task", asdlc.claim_refusal(None, "TASK-9", ()))
        held = task("TASK-1", status="In Progress", assignees=("@a",))
        self.assertIn("assigned to @a", asdlc.claim_refusal(held, "TASK-1", (held,)))
        done = task("TASK-1", status="Done")
        self.assertIn("not To Do", asdlc.claim_refusal(done, "TASK-1", (done,)))
        big = task("TASK-1", labels=("size-8",))
        self.assertIn("split it", asdlc.claim_refusal(big, "TASK-1", (big,)))

    def test_race_result(self) -> None:
        self.assertIs(asdlc.race_result(task("TASK-1"), "a"), asdlc.Race.OPEN)
        self.assertIs(asdlc.race_result(task("TASK-1", status="In Progress", assignees=("@b",)), "a"), asdlc.Race.LOST)
        self.assertIs(asdlc.race_result(task("TASK-1", status="In Progress", assignees=("@a",)), "a"), asdlc.Race.WON)
        self.assertIs(asdlc.race_result(task("TASK-1", status="Done"), "a"), asdlc.Race.LOST)
        self.assertIs(asdlc.race_result(None, "a"), asdlc.Race.LOST)

    def test_push_outcome(self) -> None:
        self.assertIs(asdlc.push_outcome(0, ""), asdlc.Push.PUSHED)
        for stderr in (" ! [rejected]        HEAD -> main (fetch first)", "error: cannot lock ref 'refs/heads/main'"):
            with self.subTest(stderr=stderr):
                self.assertIs(asdlc.push_outcome(1, stderr), asdlc.Push.RETRY)
        self.assertIs(asdlc.push_outcome(128, "fatal: could not read from remote repository"), asdlc.Push.FAILED)

    def test_backoff_grows_and_jitters(self) -> None:
        rng = random.Random(1)
        first, fourth = asdlc.backoff(1, rng), asdlc.backoff(4, rng)
        self.assertTrue(0.05 <= first <= 0.25 and 0.2 <= fourth <= 1.0)

    def test_duplicate_ids(self) -> None:
        self.assertEqual(asdlc.duplicate_ids((task("TASK-5"), task("TASK-5"), task("TASK-6"))), {"TASK-5"})


class SmallPiecesTest(unittest.TestCase):
    def test_hooks_off_appends_to_existing_git_config(self) -> None:
        self.assertEqual(
            asdlc.hooks_off({"PATH": "/bin"}),
            {"PATH": "/bin", "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null"},
        )
        env = asdlc.hooks_off({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "a.b", "GIT_CONFIG_VALUE_0": "c"})
        self.assertEqual((env["GIT_CONFIG_COUNT"], env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_KEY_1"]), ("2", "a.b", "core.hooksPath"))

    def test_backlog_version(self) -> None:
        self.assertEqual(asdlc.backlog_version("1.55.2\n"), (1, 55, 2))
        self.assertLess(asdlc.backlog_version("1.54.0"), asdlc.MIN_BACKLOG)
        self.assertIsNone(asdlc.backlog_version("nope"))

    def test_board_config_sets_this_boards_keys_in_place(self) -> None:
        existing = 'project_name: "x"\ndefault_status: "To Do"\nstatuses: ["To Do", "Done"]\nlabels:\n  - old\nauto_commit: false\ntask_prefix: "task"\n'
        written = asdlc.board_config(existing, "team-board")
        fields = asdlc.frontmatter(f"---\n{written}---\n")
        self.assertEqual(fields["project_name"], "team-board")
        self.assertEqual(fields["statuses"], ("To Do", "In Progress", "In Review", "Done"))
        self.assertEqual(fields["types"], ("intent", "task", "bug", "spike"))
        self.assertEqual(fields["labels"], ("size-1", "size-2", "size-3", "size-4", "size-5", "size-8"))
        self.assertEqual(
            [fields[k] for k in ("default_status", "auto_commit", "bypass_git_hooks", "remote_operations", "check_active_branches")],
            ["To Do", "true", "true", "true", "false"],
        )
        self.assertEqual(fields["task_prefix"], "task")
        self.assertTrue(written.startswith('project_name: "team-board"\n'))
        self.assertNotIn("old", written)

    def test_names_and_paths(self) -> None:
        self.assertEqual(asdlc.normalise_id("3", "task"), "TASK-3")
        self.assertEqual(asdlc.normalise_id("task-1.2", "task"), "TASK-1.2")
        self.assertEqual(asdlc.slug("Fix: the login, it's broken!"), "fix-the-login-it-s-broken")
        self.assertLessEqual(len(asdlc.slug("word " * 30)), 40)
        self.assertEqual(asdlc.branch_name(task("TASK-1.2", title="Add the thing")), "task-1.2-add-the-thing")
        self.assertEqual(asdlc.worktree_path(Path("/src/app"), "TASK-3"), Path("/src/app.worktrees/task-3"))
        self.assertEqual(asdlc.with_exclude("# x", ".asdlc-task"), "# x\n.asdlc-task\n")
        self.assertIsNone(asdlc.with_exclude(".asdlc-task\n", ".asdlc-task"))
        self.assertEqual(asdlc.command_index(["--board", "board", "claim", "x"]), 2)
        with self.assertRaises(asdlc.AsdlcError):
            asdlc.worker_name("agent 1; rm")
        self.assertEqual(asdlc.worker_name("@agent-1"), "agent-1")


# --- the script, against real git repositories and the backlog CLI --------------------


def _asdlc(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return run_script("scripts/asdlc", *args, cwd=cwd, env={**ISOLATED, "ASDLC_BACKLOG": BACKLOG or "backlog", **(env or {})})


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env={**os.environ, **ISOLATED})
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout.strip()


class Boards:
    """A bare board origin with tasks on it, and clones of it, in a temporary folder."""

    def __init__(self, test: unittest.TestCase, tasks: list[list[str]]) -> None:
        handle = tempfile.TemporaryDirectory()
        test.addCleanup(handle.cleanup)
        self.root = Path(handle.name).resolve()
        self.origin = self.root / "board-origin.git"
        _git(self.root, "init", "--quiet", "--bare", "-b", "main", str(self.origin))
        seed = self.root / "seed"
        done = _asdlc("init-board", str(seed))
        test.assertEqual(done.returncode, 0, done.stderr)
        env = {**os.environ, **ISOLATED, **asdlc.hooks_off({})}
        for arguments in tasks:
            created = subprocess.run([BACKLOG, "task", "create", *arguments], cwd=seed, capture_output=True, text=True, env=env)
            test.assertEqual(created.returncode, 0, created.stderr)
        _git(seed, "remote", "add", "origin", str(self.origin))
        _git(seed, "push", "--quiet", "origin", "main")
        self.seed = seed

    def clone(self, name: str) -> Path:
        path = self.root / name
        _git(self.root, "clone", "--quiet", str(self.origin), str(path))
        return path

    def on_origin(self) -> dict[str, object]:
        """Every task as it is on origin/main, read from a fresh clone."""
        fresh = Path(tempfile.mkdtemp(dir=self.root))
        _git(fresh, "clone", "--quiet", str(self.origin), str(fresh / "c"))
        tasks = {}
        for path in sorted((fresh / "c" / "backlog" / "tasks").glob("*.md")):
            found = asdlc.task_from(path.name, path.read_text())
            tasks.setdefault(found.id, []).append(found)
        return tasks


def _sized(title: str, size: str = "size-2", *extra: str) -> list[str]:
    return [title, "--type", "task", "-l", size, *extra]


def _interfering_backlog(folder: Path, other_clone: Path, command: str, before: bool = False) -> dict[str, str]:
    """A backlog wrapper that lets another clone push once while this command runs.

    It stands in for another agent on another machine, at the exact moment that makes
    this clone's push be rejected. `before` runs the other agent's change first.
    """
    wrapper = folder / "backlog-wrapper"
    flag = folder / "interfered"
    other = f'(cd "$OTHER" && git pull -q --rebase origin main && sh -c "$OTHER_COMMAND" && git push -q origin HEAD:main) >&2'
    wrapper.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then exec "$REAL_BACKLOG" "$@"; fi\n'
        + (f'if [ ! -e "$FLAG" ]; then : > "$FLAG"; {other}; fi\n' if before else "")
        + '"$REAL_BACKLOG" "$@"; status=$?\n'
        + ("" if before else f'if [ ! -e "$FLAG" ]; then : > "$FLAG"; {other}; fi\n')
        + 'exit $status\n'
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
    return {"ASDLC_BACKLOG": str(wrapper), "REAL_BACKLOG": BACKLOG, "OTHER": str(other_clone), "OTHER_COMMAND": command, "FLAG": str(flag)}


@needs_backlog
class InitBoardTest(unittest.TestCase):
    def test_writes_the_config_and_commits_with_every_hook_off(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            board = Path(folder) / "board"
            board.mkdir()
            _git(board, "init", "--quiet", "-b", "main")
            touched = Path(folder) / "a-hook-ran"
            for hook in ("pre-commit", "prepare-commit-msg", "commit-msg", "post-commit"):
                script = board / ".git" / "hooks" / hook
                script.write_text(f"#!/bin/sh\necho {hook} >> '{touched}'\nexit 1\n")
                script.chmod(0o755)
            done = _asdlc("init-board", str(board))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertFalse(touched.exists(), "a git hook ran")
            fields = asdlc.frontmatter(f"---\n{(board / 'backlog' / 'config.yml').read_text()}---\n")
            self.assertEqual(fields["statuses"], ("To Do", "In Progress", "In Review", "Done"))
            self.assertEqual(fields["default_status"], "To Do")
            self.assertEqual(fields["types"], ("intent", "task", "bug", "spike"))
            self.assertEqual(fields["labels"], ("size-1", "size-2", "size-3", "size-4", "size-5", "size-8"))
            self.assertEqual(
                [fields[k] for k in ("auto_commit", "bypass_git_hooks", "remote_operations", "check_active_branches")],
                ["true", "true", "true", "false"],
            )
            self.assertEqual(_git(board, "log", "--format=%s"), "Initialise the asdlc board")
            self.assertEqual(_git(board, "status", "--porcelain"), "")

    def test_refuses_an_old_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder) / "backlog"
            fake.write_text("#!/bin/sh\necho 1.54.0\n")
            fake.chmod(0o755)
            done = _asdlc("init-board", str(Path(folder) / "board"), env={"ASDLC_BACKLOG": str(fake)})
            self.assertEqual(done.returncode, 1)
            self.assertIn("backlog 1.54.0 is too old", done.stderr)
            self.assertIn("1.55.1", done.stderr)


@needs_backlog
class BoardCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.boards = Boards(self, [_sized("First")])
        self.mine = self.boards.clone("mine")
        self.theirs = self.boards.clone("theirs")

    def test_a_change_is_committed_and_pushed(self) -> None:
        done = _asdlc("--board", str(self.mine), "board", "task", "create", *_sized("Second"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("TASK-2", done.stdout)
        self.assertEqual(sorted(self.boards.on_origin()), ["TASK-1", "TASK-2"])

    def test_the_board_comes_from_git_config_in_the_code_repository(self) -> None:
        code = self.boards.root / "code"
        _git(self.boards.root, "init", "--quiet", "-b", "main", str(code))
        _git(code, "config", "asdlc.board", "../mine")
        done = _asdlc("board", "task", "list", "--plain", cwd=code)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("TASK-1", done.stdout)

    def test_a_rejected_push_is_rebased_and_retried(self) -> None:
        env = _interfering_backlog(self.boards.root, self.theirs, f'"$REAL_BACKLOG" task edit TASK-1 --notes "theirs"')
        done = _asdlc("--board", str(self.mine), "board", "task", "create", *_sized("Mine"), env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        on_origin = self.boards.on_origin()
        self.assertEqual(sorted(on_origin), ["TASK-1", "TASK-2"])
        self.assertEqual(_git(self.mine, "rev-parse", "HEAD"), _git(self.mine, "rev-parse", "origin/main"))
        self.assertIn("theirs", (self.mine / "backlog" / "tasks" / "task-1 - First.md").read_text())

    def test_two_creates_at_once_never_share_an_id(self) -> None:
        env = _interfering_backlog(self.boards.root, self.theirs, f'"$REAL_BACKLOG" task create "Theirs" --type task -l size-2')
        done = _asdlc("--board", str(self.mine), "board", "task", "create", *_sized("Mine"), env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("running the command again", done.stderr)
        on_origin = self.boards.on_origin()
        self.assertTrue(all(len(copies) == 1 for copies in on_origin.values()), on_origin)
        self.assertEqual(sorted(t[0].title for t in on_origin.values()), ["First", "Mine", "Theirs"])
        self.assertIn("TASK-3", done.stdout)

    def test_a_conflicting_change_is_dropped_and_names_the_file(self) -> None:
        env = _interfering_backlog(self.boards.root, self.theirs, f'"$REAL_BACKLOG" task edit TASK-1 --notes "theirs"')
        done = _asdlc("--board", str(self.mine), "board", "task", "edit", "TASK-1", "--notes", "mine", env=env)
        self.assertEqual(done.returncode, 1)
        self.assertIn("task-1 - First.md", done.stderr)
        self.assertIn("run the command again", done.stderr)
        self.assertEqual(_git(self.mine, "rev-parse", "HEAD"), _git(self.mine, "rev-parse", "origin/main"))
        self.assertIn("theirs", (self.mine / "backlog" / "tasks" / "task-1 - First.md").read_text())

    def test_refuses_a_dirty_board(self) -> None:
        (self.mine / "backlog" / "config.yml").write_text("changed: true\n")
        done = _asdlc("--board", str(self.mine), "board", "task", "list", "--plain")
        self.assertEqual(done.returncode, 1)
        self.assertIn("uncommitted changes", done.stderr)


@needs_backlog
class ClaimTest(unittest.TestCase):
    def setUp(self) -> None:
        self.boards = Boards(self, [_sized("Add the login page"), _sized("Second", "size-1"), _sized("Too big", "size-8")])
        self.mine = self.boards.clone("mine")
        self.theirs = self.boards.clone("theirs")

    def test_claims_on_the_board_only_outside_a_code_repository(self) -> None:
        done = _asdlc("--board", str(self.mine), "claim", "1", "--as", "agent-1", cwd=self.boards.root)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("on the board only", done.stdout)
        claimed = self.boards.on_origin()["TASK-1"][0]
        self.assertEqual((claimed.status, claimed.assignees), ("In Progress", ("@agent-1",)))

    def test_refuses_a_claimed_task_and_one_that_cant_start(self) -> None:
        self.assertEqual(_asdlc("--board", str(self.mine), "claim", "TASK-1", "--as", "agent-1").returncode, 0)
        again = _asdlc("--board", str(self.theirs), "claim", "TASK-1", "--as", "agent-2")
        self.assertEqual(again.returncode, 1)
        self.assertIn("assigned to @agent-1", again.stderr)
        big = _asdlc("--board", str(self.theirs), "claim", "TASK-3", "--as", "agent-2")
        self.assertEqual(big.returncode, 1)
        self.assertIn("split it before it starts", big.stderr)

    def test_losing_at_the_push_undoes_the_claim(self) -> None:
        env = _interfering_backlog(self.boards.root, self.theirs, '"$REAL_BACKLOG" task edit TASK-1 -s "In Progress" -a @agent-2')
        done = _asdlc("--board", str(self.mine), "claim", "TASK-1", "--as", "agent-1", env=env)
        self.assertEqual(done.returncode, 1)
        self.assertIn("Another agent claimed TASK-1 first. Run asdlc next for another task.", done.stderr)
        self.assertEqual(self.boards.on_origin()["TASK-1"][0].assignees, ("@agent-2",))
        self.assertEqual(_git(self.mine, "rev-parse", "HEAD"), _git(self.mine, "rev-parse", "origin/main"))

    def test_a_push_rejected_for_another_task_is_retried(self) -> None:
        env = _interfering_backlog(self.boards.root, self.theirs, '"$REAL_BACKLOG" task edit TASK-2 -s "In Progress" -a @agent-2')
        done = _asdlc("--board", str(self.mine), "claim", "TASK-1", "--as", "agent-1", env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        on_origin = self.boards.on_origin()
        self.assertEqual(on_origin["TASK-1"][0].assignees, ("@agent-1",))
        self.assertEqual(on_origin["TASK-2"][0].assignees, ("@agent-2",))

    def test_the_race(self) -> None:
        """Two clones claim the same task at once, ten times: exactly one wins each time."""
        boards = Boards(self, [_sized(f"Task {n}") for n in range(1, 11)])
        first, second = boards.clone("first"), boards.clone("second")
        lost_at_push = 0
        for number in range(1, 11):
            env = {**os.environ, **ISOLATED, "ASDLC_BACKLOG": BACKLOG}
            racers = [
                subprocess.Popen([sys.executable, str(ROOT / "scripts" / "asdlc"), "--board", str(clone), "claim", f"TASK-{number}", "--as", worker],
                                 cwd=boards.root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for clone, worker in ((first, "agent-1"), (second, "agent-2"))
            ]
            results = [(racer.wait(timeout=120), *racer.communicate()) for racer in racers]
            codes = sorted(code for code, _, _ in results)
            self.assertEqual(codes, [0, 1], results)
            loser = next(err for code, _, err in results if code == 1)
            self.assertRegex(loser, r"Another agent claimed TASK-\d+ first|assigned to @agent-")
            lost_at_push += "first" in loser
            claimed = boards.on_origin()[f"TASK-{number}"]
            self.assertEqual(len(claimed), 1)
            self.assertEqual(len(claimed[0].assignees), 1, claimed)
            self.assertEqual(claimed[0].status, "In Progress")
            for clone in (first, second):
                self.assertEqual(_git(clone, "status", "--porcelain", "--untracked-files=no"), "")
        print(f"\n  race: 10 of 10 had exactly one winner; {lost_at_push} were lost at the push", flush=True)


@needs_backlog
class WorktreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.boards = Boards(self, [_sized("Add the login page", "size-2", "--priority", "low"), _sized("Second", "size-1", "--priority", "high")])
        self.board = self.boards.clone("board")
        origin = self.boards.root / "app-origin.git"
        _git(self.boards.root, "init", "--quiet", "--bare", "-b", "main", str(origin))
        self.code = self.boards.root / "app"
        _git(self.boards.root, "clone", "--quiet", str(origin), str(self.code))
        (self.code / "README.md").write_text("app\n")
        _git(self.code, "add", ".")
        _git(self.code, "commit", "--quiet", "-m", "start")
        _git(self.code, "push", "--quiet", "origin", "main")
        _git(self.code, "config", "asdlc.board", str(self.board))

    def test_a_claim_makes_a_worktree_with_its_marker(self) -> None:
        done = _asdlc("claim", "TASK-1", "--as", "agent-1", cwd=self.code)
        self.assertEqual(done.returncode, 0, done.stderr)
        path = self.boards.root / "app.worktrees" / "task-1"
        self.assertEqual(done.stdout.strip().splitlines()[-1], str(path))
        self.assertEqual(json.loads((path / ".asdlc-task").read_text()), {"task": "TASK-1", "worker": "agent-1", "board": str(self.board)})
        self.assertEqual(_git(path, "branch", "--show-current"), "task-1-add-the-login-page")
        self.assertEqual(_git(path, "rev-parse", "HEAD"), _git(self.code, "rev-parse", "origin/main"))
        self.assertIn(".asdlc-task", (self.code / ".git" / "info" / "exclude").read_text().splitlines())
        self.assertEqual(_git(path, "status", "--porcelain"), "")
        no_upstream = subprocess.run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "@{upstream}"], capture_output=True)
        self.assertNotEqual(no_upstream.returncode, 0, "the task branch must not track main, or a bare git push could reach it")

    def test_next_takes_the_highest_priority_and_skips_claimed_tasks(self) -> None:
        first = _asdlc("next", "--as", "agent-1", cwd=self.code)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("claimed TASK-2", first.stdout)
        second = _asdlc("next", "--as", "agent-2", cwd=self.code)
        self.assertIn("claimed TASK-1", second.stdout)
        third = _asdlc("next", "--as", "agent-3", cwd=self.code)
        self.assertEqual((third.returncode, third.stdout.strip()), (0, "no work available"))

    def test_release_puts_the_task_back_and_leaves_the_worktree(self) -> None:
        self.assertEqual(_asdlc("claim", "TASK-1", "--as", "agent-1", cwd=self.code).returncode, 0)
        refused = _asdlc("release", "TASK-1", "--as", "agent-2", cwd=self.code)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("only @agent-2's own", refused.stderr)
        done = _asdlc("release", "TASK-1", "--as", "agent-1", cwd=self.code)
        self.assertEqual(done.returncode, 0, done.stderr)
        released = self.boards.on_origin()["TASK-1"][0]
        self.assertEqual((released.status, released.assignees), ("To Do", ()))
        path = self.boards.root / "app.worktrees" / "task-1"
        self.assertIn(str(path), done.stdout)
        self.assertTrue((path / ".asdlc-task").exists())
        again = _asdlc("claim", "TASK-1", "--as", "agent-2", cwd=self.code)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads((path / ".asdlc-task").read_text())["worker"], "agent-2")

    def test_the_default_branch_comes_from_origin_head(self) -> None:
        _git(self.code, "push", "--quiet", "origin", "main:trunk")
        _git(self.code, "remote", "set-head", "origin", "trunk")
        self.assertEqual(asdlc.default_branch(self.code), "trunk")
        _git(self.code, "remote", "set-head", "origin", "--delete")
        self.assertEqual(asdlc.default_branch(self.code), "main")


@needs_backlog
class RouteCommandTest(unittest.TestCase):
    def test_prints_json_or_refuses(self) -> None:
        boards = Boards(self, [_sized("Small", "size-1"), _sized("Big", "size-8"), ["Why", "--type", "intent"]])
        done = _asdlc("--board", str(boards.seed), "route", "1")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual({k: v for k, v in json.loads(done.stdout).items() if k != "reason"}, {"task": "TASK-1", "model": "haiku", "effort": "default"})
        self.assertEqual(json.loads(_asdlc("--board", str(boards.seed), "route", "3").stdout)["model"], "opus")
        refused = _asdlc("--board", str(boards.seed), "route", "2")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("split it before it starts", refused.stderr)


if __name__ == "__main__":
    unittest.main()
