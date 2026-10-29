"""The world most cases start from: a tasks repository with its board, one code repository
(acme/api, a few lines of Python with tests), and the engineers' machines.

Everything here runs on the host, before the agent starts and outside its reach. Each
engineer's machine is a `Machine` (scripts/eval): its own git identity, registry, board
clone and code clone. The agent's engineer lives under the fixture's `agent/` folder,
everyone else under `others/`, which the agent never sees.
"""

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import asdlc_eval as ev

LOGIN = '''"""Logins for acme/api."""

PASSWORDS = {"ann": "s3cret", "kyle": "hunter2"}
FAILED: dict[str, int] = {}


def check(user: str, password: str) -> bool:
    return PASSWORDS.get(user) == password


def login(user: str, password: str) -> bool:
    return check(user, password)
'''

TESTS = '''import unittest

from login import login


class LoginTest(unittest.TestCase):
    def test_the_right_password_logs_in(self) -> None:
        self.assertTrue(login("ann", "s3cret"))

    def test_a_wrong_password_does_not(self) -> None:
        self.assertFalse(login("ann", "nope"))


if __name__ == "__main__":
    unittest.main()
'''

COMMANDS = """[build]
run = "python3 -m py_compile login.py"

[test]
run = "python3 -m unittest -q"

[lint]
run = "python3 -m py_compile login.py test_login.py"
"""

TESTING_RULE = """---
paths:
  - "**/*.py"
---
# Testing acme/api

Applies to every Python file in acme/api.

- Tests are `unittest` modules beside the code, `test_<module>.py`; run them all with `python3 -m unittest -q` from the repository's root.
"""


@dataclass(frozen=True)
class Spec:
    """A board item the seed creates directly, as accepted work (or a draft with draft=True)."""

    title: str
    type: str = "task"
    size: str = ""  # such as size-2
    project: str = ""  # acme-api for work in the code repository
    parent: str = ""
    ac: tuple[str, ...] = ("It works",)
    description: str = ""
    assignee: str = ""
    docs: tuple[str, ...] = ()  # document ids to link, created before the items
    draft: bool = False


@dataclass(frozen=True)
class Doc:
    title: str
    content: str
    type: str = "other"


@dataclass
class Team:
    fixture: ev.Fixture
    board_origin: Path
    api_origin: Path
    machines: dict[str, ev.Machine] = field(default_factory=dict)
    agent: str = ""

    @property
    def me(self) -> ev.Machine:
        return self.machines[self.agent]

    def facts(self, **extra: object) -> dict[str, object]:
        """What the runner, the prompts and the checks know about the fixture."""
        me = self.me
        return {"board_origin": self.board_origin, "board": me.board, "cwd": me.board, "env": me.env, "engineer": me.name,
                "code_origins": {"api": self.api_origin}, "clones": {"api": me.clones["api"]}, "api": me.clones["api"],
                "worktrees": Path(f"{me.clones['api']}.worktrees"), **extra}


def _backlog(seed: Path, *args: str) -> str:
    env = {**os.environ, **ev.SEED_ENV, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null"}
    done = subprocess.run(["backlog", *args], cwd=seed, capture_output=True, text=True, env=env)
    if done.returncode != 0:
        raise RuntimeError(f"backlog {' '.join(args)}: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def team(fixture: ev.Fixture, *, agent: str, devs: dict[str, str], items: list[Spec], docs: list[Doc] = (),
         settings: str = 'stale_after = "2h"\nreview_fallback_after = "30m"\n', publish: bool = True) -> Team:
    """The tasks repository, acme/api and a machine for each engineer in `devs` (name -> devs/<name>.yaml)."""
    env = fixture.seed_env()
    board_origin = ev.bare(fixture.origins / "board.git")
    seed = fixture.others / "seed-board"
    done = subprocess.run([sys.executable, str(fixture.plugin / "scripts" / "asdlc"), "init-board", str(seed)],
                          capture_output=True, text=True, env={**env, "ASDLC_BACKLOG": "backlog"})
    if done.returncode != 0:
        raise RuntimeError(f"init-board: {done.stderr}")
    (seed / "devs").mkdir(exist_ok=True)
    for name, text in devs.items():
        (seed / "devs" / f"{name}.yaml").write_text(text)
    (seed / "asdlc.toml").write_text(settings)
    config = seed / "backlog" / "config.yml"
    config.write_text(config.read_text() + 'projects: ["acme-api"]\n')
    for doc in docs:
        created = _backlog(seed, "doc", "create", doc.title, "-t", doc.type)
        doc_id = created.split("Created document ")[1].split()[0]
        _backlog(seed, "doc", "update", doc_id, "--content", doc.content)
    for spec in items:
        args = ["task", "create", spec.title, "--type", spec.type]
        args += ["-l", spec.size] if spec.size else []
        args += ["--project", spec.project] if spec.project else []
        args += ["-p", spec.parent] if spec.parent else []
        args += ["-a", spec.assignee] if spec.assignee else []
        args += ["-d", spec.description] if spec.description else []
        args += [part for ac in spec.ac for part in ("--ac", ac)]
        args += ["--draft"] if spec.draft else []
        _backlog(seed, *args)
        if spec.docs:
            listing = sorted((seed / "backlog" / ("drafts" if spec.draft else "tasks")).glob("*.md"), key=lambda p: p.stat().st_mtime_ns)
            item = ev.board_item(str(listing[-1]), listing[-1].read_text())
            for doc_id in spec.docs:
                _backlog(seed, "task" if not spec.draft else "draft", "edit", item.id, "--add-doc", doc_id)
    ev._git(seed, "add", ".", env=env)
    ev._git(seed, "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "-m", "The team's board", env=env)
    ev._git(seed, "remote", "add", "origin", str(board_origin), env=env)
    ev._git(seed, "push", "--quiet", "origin", "main", env=env)

    api_origin = ev.bare(fixture.origins / "acme" / "api.git")
    work = fixture.others / "seed-api"
    subprocess.run(["git", "clone", "--quiet", str(api_origin), str(work)], check=True, capture_output=True, env=env)
    (work / "login.py").write_text(LOGIN)
    (work / "test_login.py").write_text(TESTS)
    ev._git(work, "add", ".", env=env)
    ev._git(work, "commit", "--quiet", "-m", "Logins", env=env)
    ev._git(work, "push", "--quiet", "origin", "main", env=env)

    found = Team(fixture, board_origin, api_origin, agent=agent)
    for name in devs:
        machine = ev.machine(fixture, name, board_origin, agent=name == agent)
        clone = machine.home / "api"
        machine.run("git", "clone", "--quiet", str(api_origin), str(clone), cwd=machine.home)
        machine.asdlc("register", "--board", str(machine.board), cwd=clone)
        machine.clones["api"] = clone
        found.machines[name] = machine
    if publish:
        publish_api_plugin(found.me)
    found.me.asdlc("permissions", "--write")
    return found


def publish_api_plugin(machine: ev.Machine) -> None:
    """acme/api's plugin in the tasks repository, onboarded the way the onboard-repo skill does it,
    so no case pays for an onboarding it isn't about."""
    repo = machine.clones["api"]
    status = json.loads(machine.plugin("status", str(repo), "--json").stdout)
    machine.plugin("scaffold", str(repo))
    board = Path(str(status["board"]))
    folder = board.parent / f"{board.name}.worktrees" / f"plugin-{status['slug']}" / "plugins" / status["slug"]
    (folder / "commands.toml").write_text(COMMANDS)
    (folder / "rules").mkdir(exist_ok=True)
    (folder / "rules" / "testing-python.md").write_text(TESTING_RULE)
    for name in ("build", "test", "lint"):
        machine.plugin("verify-command", str(repo), name)
    machine.plugin("publish", status["slug"], "--repo", str(repo))


def machine_from(fixture: ev.Fixture, facts: dict[str, object]) -> ev.Machine:
    """The agent's engineer's machine again, for a person step."""
    env = {str(k): str(v) for k, v in dict(facts["env"]).items()}
    found = ev.Machine(fixture, str(facts["engineer"]), Path(env["HOME"]), Path(str(facts["board"])), env)
    found.clones["api"] = Path(str(facts["api"]))
    return found


def build_and_push(machine: ev.Machine, worktree: Path, files: dict[str, str], message: str, worker: str) -> str:
    """A worker's commit on the task's branch, pushed: what an earlier round of work left behind."""
    for name, text in files.items():
        (worktree / name).write_text(text)
    machine.git(worktree, "add", *files)
    machine.git(worktree, "commit", "--quiet", "-m", message, "--trailer", f"Asdlc-Worker: {worker}")
    machine.git(worktree, "push", "--quiet", "-u", "origin", "HEAD")
    return machine.git(worktree, "rev-parse", "HEAD")


def item(machine: ev.Machine, item_id: str) -> ev.BoardItem:
    """An item as the board clone has it now, after pulling."""
    machine.git(machine.board, "pull", "--quiet", "--ff-only")
    for folder in ("tasks", "drafts"):
        for path in (machine.board / "backlog" / folder).glob("*.md"):
            found = ev.board_item(str(path.relative_to(machine.board)), path.read_text())
            if found and found.id == item_id.upper():
                return found
    raise RuntimeError(f"no {item_id} on {machine.name}'s board")


# What earlier rounds of work left on the board, done the way the worker and reviewer agents do it.

COUNTING = '''"""Logins for acme/api."""

PASSWORDS = {"ann": "s3cret", "kyle": "hunter2"}
FAILED: dict[str, int] = {}


def check(user: str, password: str) -> bool:
    return PASSWORDS.get(user) == password


def login(user: str, password: str) -> bool:
    FAILED[user] = FAILED.get(user, 0) + 1
    return check(user, password)
'''
"""Counts every login, successful ones too: the defect the review cases seed."""

COUNTING_FIXED = '''"""Logins for acme/api."""

PASSWORDS = {"ann": "s3cret", "kyle": "hunter2"}
FAILED: dict[str, int] = {}


def check(user: str, password: str) -> bool:
    return PASSWORDS.get(user) == password


def login(user: str, password: str) -> bool:
    ok = check(user, password)
    if not ok:
        FAILED[user] = FAILED.get(user, 0) + 1
    return ok
'''

COUNTING_TESTS = '''import unittest

from login import FAILED, login


class LoginTest(unittest.TestCase):
    def setUp(self) -> None:
        FAILED.clear()

    def test_the_right_password_logs_in(self) -> None:
        self.assertTrue(login("ann", "s3cret"))

    def test_a_wrong_password_does_not(self) -> None:
        self.assertFalse(login("ann", "nope"))

    def test_a_failed_login_is_counted(self) -> None:
        login("ann", "nope")
        self.assertEqual(FAILED["ann"], 1)
'''

COUNTING_TESTS_FIXED = COUNTING_TESTS + '''
    def test_a_successful_login_is_not_counted(self) -> None:
        login("ann", "s3cret")
        self.assertNotIn("ann", FAILED)
'''

COUNT_TASK = Spec(
    "Count failed logins", size="size-2", project="acme-api",
    ac=("A failed login adds one to FAILED[user]", "A successful login leaves FAILED unchanged", "Tests cover both"),
    description="Support wants to see who keeps failing to log in. Count failed logins per user in FAILED; successful logins don't count.",
)

COUNT_PLAN = """## Files that change
- `login.py`: count a failed login in FAILED[user]
- `test_login.py`: a test for a counted failure

## Order of work
1. Count in login().
2. Add the test.

## Risks
- None worth naming: one function.

## Proof
- `python3 -m unittest -q` passes."""


def claim(machine: ev.Machine, task: str, worker: str) -> dict[str, object]:
    return machine.json("claim", task, "--as", worker)


def plan_and_approve(machine: ev.Machine, task: str, plan: str = COUNT_PLAN) -> None:
    """The worker writes its plan; its engineer approves it, as a person."""
    machine.asdlc("board", "task", "edit", task, "--plan", plan)
    machine.asdlc("approve", task)


def build_round(machine: ev.Machine, task: str, worker: str, worktree: Path, commits: list[tuple[str, dict[str, str]]],
                pull: str | None) -> list[str]:
    """A worker's phase 2: a commit per step, the tests recorded, pushed, handed to review."""
    shas = []
    for message, files in commits:
        for name, text in files.items():
            (worktree / name).write_text(text)
        machine.git(worktree, "add", *files)
        machine.git(worktree, "commit", "--quiet", "-m", message, "--trailer", f"Asdlc-Worker: {worker}")
        shas.append(machine.git(worktree, "rev-parse", "HEAD"))
    machine.asdlc("record-check", task, "--as", worker, "--", "python3", "-m", "unittest", "-q", cwd=worktree)
    machine.git(worktree, "push", "--quiet", "-u", "origin", "HEAD")
    machine.asdlc("finish", task, "--as", worker, *(("--pr", pull) if pull else ()), "--notes", "Built; tests recorded above.")
    return shas


def review_scene(fixture: ev.Fixture, *, defect: bool, gh: bool = False) -> tuple[Team, dict[str, object]]:
    """ann's worker built "Count failed logins" and handed it to review; kyle's reviewer claimed the review.
    With `defect`, the change counts successful logins too, and its tests don't notice."""
    if gh:
        fixture.add_gh()
    found = team(fixture, agent="kyle", items=[COUNT_TASK],
                 devs={"kyle": "name: kyle\nworkers: 2\nreview: true\n", "ann": "name: ann\nworkers: 2\nreview: true\n"})
    ann = found.machines["ann"]
    claimed = claim(ann, "TASK-1", "ann.w1")
    plan_and_approve(ann, "TASK-1")
    files = {"login.py": COUNTING, "test_login.py": COUNTING_TESTS} if defect else \
        {"login.py": COUNTING_FIXED, "test_login.py": COUNTING_TESTS_FIXED}
    build_round(ann, "TASK-1", "ann.w1", Path(str(claimed["worktree"])), [("Count failed logins", files)],
                "https://github.com/acme/api/pull/7")
    review = found.me.json("review-next", "--as", "kyle.r1")
    if review.get("task") != "TASK-1":
        raise RuntimeError(f"kyle's review-next didn't claim TASK-1: {review}")
    return found, review


def reviewer_prompt(review: dict[str, object]) -> str:
    """What the orchestrate skill gives a reviewer it launches: every field the claim printed."""
    return ("Review the task your orchestrator claimed. These are the fields `asdlc review-next` printed:\n\n"
            + "\n".join(f"- {key}: {review[key]}" for key in ("task", "reviewer", "kind", "repo", "default_branch", "branch",
                                                              "pull_request", "policies")))


def reference_review(script: ev.Script, review: dict[str, object], verdict: str, findings: str, notes: str,
                     policies: tuple[str, ...] = ("review",)) -> None:
    """The reviewer agent's steps, scripted: read, diff in a detached worktree, record the verdict, clean up."""
    repo, branch, base, task, who = (str(review[k]) for k in ("repo", "branch", "default_branch", "task", "reviewer"))
    worktree = f"{repo}.worktrees/review-{task.lower()}-{who}"
    for policy in review["policies"]:
        script.read(Path(str(policy)))
    script.bash(f"asdlc board task view {task} --plain")
    script.bash(f"git -C {repo} fetch origin {branch} {base}")
    script.bash(f"git -C {repo} worktree add --detach {worktree} origin/{branch}")
    script.bash(f"git -C {worktree} diff origin/{base}...HEAD")
    script.read(Path(worktree) / "login.py")
    cited = " ".join(f"--policy {p}" for p in policies)
    script.bash(f"asdlc review-done {task} --as {who} --verdict {verdict} --findings {findings} {cited} --plan-matched yes "
                f"--notes {shlex.quote(notes)}")
    script.bash(f"git -C {repo} worktree remove --force {worktree}")


# One engineer, one repository, and a board that lives in it or nowhere: the world for the one-machine cases.

SOLO_README = "# acme/app\n\nLogins for acme.\n"
SOLO_CLAUDE = """# acme/app

## Commands
- Test: `python3 -m unittest -q`

## Conventions
- Python 3.12, standard library only.
- Tests are `unittest` modules beside the code, `test_<module>.py`.
"""


@dataclass
class Solo:
    fixture: ev.Fixture
    origin: Path
    machine: ev.Machine

    @property
    def clone(self) -> Path:
        return self.machine.clones["app"]

    def facts(self, **extra: object) -> dict[str, object]:
        """What the runner, the prompts and the checks know. The board, when there is one, is the repository itself."""
        return {"board_origin": self.origin, "board": self.clone, "cwd": self.clone, "env": self.machine.env, "engineer": self.machine.name,
                "code_origins": {"app": self.origin}, "clones": {"app": self.clone}, "app": self.clone, **extra}


def solo(fixture: ev.Fixture, *, agent: str = "kyle", board: bool = False, files: dict[str, str] | None = None,
         claude_md: str | None = SOLO_CLAUDE, branch: str = "") -> Solo:
    """acme/app, a few lines of Python with tests, cloned for one engineer. With `board`, `asdlc init-board --local`
    has been run in it and the board is committed there. `files` are added to the repository, `branch` is checked out
    in the clone."""
    env = fixture.seed_env()
    origin = ev.bare(fixture.origins / "acme" / "app.git")
    work = fixture.others / "seed-app"
    subprocess.run(["git", "clone", "--quiet", str(origin), str(work)], check=True, capture_output=True, env=env)
    contents = {"README.md": SOLO_README, "login.py": LOGIN, "test_login.py": TESTS, **({"CLAUDE.md": claude_md} if claude_md else {}), **(files or {})}
    for name, text in contents.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(text)
    ev._git(work, "add", ".", env=env)
    ev._git(work, "commit", "--quiet", "-m", "acme/app", env=env)
    if board:
        done = subprocess.run([sys.executable, str(fixture.plugin / "scripts" / "asdlc"), "init-board", "--local", str(work)],
                              capture_output=True, text=True, env={**env, "ASDLC_BACKLOG": "backlog"})
        if done.returncode != 0:
            raise RuntimeError(f"init-board --local: {done.stderr}")
    ev._git(work, "push", "--quiet", "origin", "main", env=env)
    machine = ev.machine(fixture, agent, origin, agent=True)  # clones the origin into <home>/tasks; here that is the repository
    clone = machine.home / "app"
    machine.board.rename(clone)
    machine.board = clone
    machine.clones["app"] = clone
    if branch:
        machine.git(clone, "switch", "--quiet", "-c", branch)
    allow_solo_work(clone, fixture.plugin)
    return Solo(fixture, origin, machine)


# What an engineer working alone in this repository allows without being asked: git for the work in
# the clone itself and the project's own tests. A headless session has no one to answer a prompt, so
# anything not allowed here is refused and a case would measure the missing permission, not the agent.
SOLO_ALLOW = ("Bash(asdlc *)", "Bash(asdlc-plugin *)", "Bash(backlog task list *)", "Bash(backlog task view *)", "Bash(backlog draft list *)",
              "Bash(backlog draft view *)", "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(git show*)", "Bash(git add*)", "Bash(git commit*)",
              "Bash(git switch*)", "Bash(git branch*)", "Bash(git checkout -b*)", "Bash(git stash*)", "Bash(git restore*)",
              "Bash(git rev-parse*)", "Bash(git ls-files*)", "Bash(git grep*)", "Bash(git check-ignore*)", "Bash(cat *)", "Bash(ls*)",
              "Bash(python3 -m unittest*)", "Bash(python3 test_*.py*)", "Bash(python -m unittest*)")


def allow_solo_work(clone: Path, plugin: Path) -> None:
    """Add SOLO_ALLOW to the clone's .claude/settings.local.json, keeping what is there, and keep
    that file out of the repository's status so no case sees it as the agent's change."""
    path = clone / ".claude" / "settings.local.json"
    data = json.loads(path.read_text()) if path.is_file() else {}
    allow = data.setdefault("permissions", {}).setdefault("allow", [])
    allow += [rule for rule in SOLO_ALLOW if rule not in allow]
    folders = data["permissions"].setdefault("additionalDirectories", [])
    if str(plugin) not in folders:
        folders.append(str(plugin))  # the skills copy their templates from the plugin
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    exclude = clone / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    seen = exclude.read_text() if exclude.is_file() else ""
    if ".claude/" not in seen.split():
        exclude.write_text(seen + ("" if seen.endswith("\n") or not seen else "\n") + ".claude/\n")


def machine_for(fixture: ev.Fixture, facts: dict[str, object]) -> ev.Machine:
    """The agent's engineer's machine again, for a solo case's `collect` or a person step."""
    env = {str(k): str(v) for k, v in dict(facts["env"]).items()}
    found = ev.Machine(fixture, str(facts["engineer"]), Path(env["HOME"]), Path(str(facts["board"])), env)
    found.clones["app"] = Path(str(facts["app"]))
    return found


def tree(clone: Path) -> dict[str, str]:
    """Every file in a working tree as it is now, uncommitted changes included, for a case's `collect`."""
    found = {}
    for path in sorted(clone.rglob("*")):
        relative = path.relative_to(clone)
        if path.is_file() and ".git" not in relative.parts and ".asdlc" not in relative.parts and "__pycache__" not in relative.parts:
            found[relative.as_posix()] = path.read_text(errors="replace")
    return found


def git_repos(fixture: ev.Fixture, *except_paths: Path) -> list[str]:
    """Every git repository under the agent's side of the fixture other than the origins and the paths given: what the agent made itself."""
    skip = {path.resolve() for path in except_paths}
    found = []
    for marker in sorted(fixture.agent.rglob(".git")):
        root = marker.parent.resolve()
        if root not in skip and fixture.origins.resolve() not in root.parents and "claude-config" not in root.parts:
            found.append(str(root))
    return found


# A bug to fix: accounts should lock after three failed logins, and lock after four.

LOCKOUT = '''"""Account lockout for acme/app."""

LIMIT = 3  # an account locks after this many failed logins


def locked(failures: int) -> bool:
    return failures > LIMIT
'''

LOCKOUT_FIXED = LOCKOUT.replace("failures > LIMIT", "failures >= LIMIT")

LOCKOUT_TESTS = '''import unittest

from lockout import locked


class LockoutTest(unittest.TestCase):
    def test_a_fresh_account_is_not_locked(self) -> None:
        self.assertFalse(locked(0))

    def test_many_failures_lock_it(self) -> None:
        self.assertTrue(locked(5))
'''

LOCKOUT_REPRO_TEST = '''import unittest

from lockout import locked


class LockoutLimitTest(unittest.TestCase):
    def test_three_failures_lock_the_account(self) -> None:
        self.assertTrue(locked(3))
'''

LOCKOUT_RED_TESTS = LOCKOUT_TESTS + '''
    def test_locks_after_three_failures(self) -> None:
        self.assertTrue(locked(3))
'''

BUG_CLAUDE = SOLO_CLAUDE + """
## Fixing bugs
- Reproduce the bug as a failing test and commit it before you change any code. Never edit an existing test to make it pass.
"""


def commit_history(machine: ev.Machine, clone: Path, base: str) -> list[dict[str, object]]:
    """Each commit after `base` on the clone's branch, oldest first: what it touched, and whether the tests pass at it.

    Run on the host after the agent stopped; each commit is exported to a scratch folder and `python3 -m unittest -q` run there."""
    import tempfile

    found = []
    for sha in machine.git(clone, "rev-list", "--reverse", f"{base}..HEAD").split():
        files = machine.git(clone, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha).split()
        with tempfile.TemporaryDirectory() as scratch:
            archive = subprocess.run(["git", "-C", str(clone), "archive", "--format=tar", sha], capture_output=True, check=True)
            subprocess.run(["tar", "-x", "-C", scratch], input=archive.stdout, check=True)
            done = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=scratch, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        found.append({"sha": sha, "subject": machine.git(clone, "log", "-1", "--format=%s", sha), "files": files, "passes": done.returncode == 0})
    return found


# Policy skills: what a case needs to read back from the repository after the agent wrote one.

ENDPOINTS = '''"""Endpoints for acme/app."""

from gateway import requires_jwt


@requires_jwt
def status(claim_id: str) -> dict[str, str]:
    return {"id": claim_id, "status": "received"}
'''

CHECK_ENDPOINTS = """#!/bin/sh
# Fails when an endpoint file has a route without the gateway JWT decorator.
for file in "$@"; do
  if grep -q '^def ' "$file" && ! grep -q '@requires_jwt' "$file"; then
    echo "$file: an endpoint without @requires_jwt" >&2
    exit 1
  fi
done
"""


def policy_files(clone: Path) -> dict[str, str]:
    """What a case reads back after a policy skill was written: the skill, the settings, hook scripts and workflows."""
    found = tree(clone)
    skills = {name: text for name, text in found.items() if name.startswith(".claude/skills/") and name.endswith("/SKILL.md")}
    first = sorted(skills)[0] if skills else ""
    return {
        "skill_path": first, "skill": skills.get(first, ""), "skills": str(len(skills)),
        "settings": found.get(".claude/settings.json", ""),
        "hook_scripts": "\n".join(name for name in found if name.startswith(".claude/hooks/")),
        "workflows": "\n".join(text for name, text in found.items() if name.startswith(".github/workflows/")),
        "new_scripts": "\n".join(name for name in found if name.startswith("scripts/") and name != "scripts/check-endpoints.sh"),
    }
