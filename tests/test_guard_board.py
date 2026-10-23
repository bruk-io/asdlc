import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, git, hook_payload, load, make_repo, run_script

load("hooks/decision_log.py")
guard = load("hooks/guard_board.py")
load("scripts/repo_slug.py")
asdlc = load("scripts/asdlc")

CODE = Path("/work/app")
BOARD = Path("/work/board")
PLAIN = Path("/work/plain")


def _repo(root: Path, **facts: object) -> object:
    values = {"is_board": False, "takes_board_work": False, "has_marker": False, "branch": "main", "protected": frozenset({"main", "master"})}
    return guard.Repo(root=root, **(values | facts))


WORKTREE = Path("/work/app.worktrees/task-1")
REPOS = {
    CODE: _repo(CODE, takes_board_work=True),
    WORKTREE: _repo(WORKTREE, takes_board_work=True, has_marker=True, branch="task-1-x"),
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

    def test_denies_an_agent_writing_the_persons_permissions(self) -> None:
        """I10: asdlc permissions --write changes the person's own Claude Code settings; printing them is fine."""
        for command in ("asdlc permissions --write", "asdlc --board ../b permissions --json --write"):
            with self.subTest(command=command):
                outcome = guard.decide_command(command, PLAIN, lookup)
                self.assertIs(outcome.verdict, guard.Verdict.DENY)
                self.assertIn("their own terminal", outcome.reason)
        self.assertIs(verdict("asdlc permissions --json"), guard.Verdict.ALLOW)

    def test_the_guards_never_ask(self) -> None:
        """I10: a hook that answered `ask` would add a permission prompt; the guards only deny or allow."""
        for hook in ("guard_board.py", "guard_test_edits.py", "load_rules.py"):
            with self.subTest(hook=hook):
                text = (ROOT / "hooks" / hook).read_text()
                self.assertNotRegex(text, r'"permissionDecision":\s*"ask"')
                self.assertNotIn("Outcome(Verdict.ASK", text)

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


class ReadOnlyTest(unittest.TestCase):
    """Second review, Important 1: status, label and assignee rules apply to changes, never to listings."""

    def test_listings_filtered_by_status_or_label_are_allowed(self) -> None:
        for command in ("asdlc board task list -s 'In Progress' --plain", "asdlc board task list --status 'In Review' --plain",
                        "backlog task list -s 'To Do' --plain", "asdlc board task list -l review-passed --plain",
                        "asdlc board search login -s 'In Review'", "backlog task list --status=Done --plain", "asdlc board task list -a @kyle.w1",
                        "asdlc board task view TASK-1 --plain", "backlog draft list --plain", "asdlc board task list -p TASK-1 -l contract-change --plain"):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.ALLOW)
        for command in ("asdlc board task edit 1 -s 'In Review'", "backlog task create X --draft -s Done", "asdlc board draft create X -s 'In Progress'"):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.DENY)


class SizeAndShortFlagsTest(unittest.TestCase):
    """Second review: Important 4 (an approved plan's size is fixed) and Minor 5 (attached short flags)."""

    def test_an_agent_cannot_resize_accepted_work(self) -> None:
        for command in ("asdlc board task edit 1 --remove-label size-3 --add-label size-1", "asdlc board task edit TASK-1 -l size-1",
                        "backlog task edit 1 --labels size-1,contract-change", "asdlc board task edit TASK-1 --clear-labels",
                        "asdlc board task edit TASK-1 --add-label=size-2", "asdlc board task edit TASK-1 -lsize-1"):
            with self.subTest(command=command):
                outcome = guard.decide_command(command, PLAIN, lookup)
                self.assertIs(outcome.verdict, guard.Verdict.DENY)
                self.assertIn("approve", outcome.reason)
        for command in ("asdlc board task create X --draft -p DRAFT-1 -l size-2", "asdlc board draft edit DRAFT-2 --add-label size-3",
                        "asdlc board task edit DRAFT-2 --remove-label size-3 --add-label size-2", "asdlc board task edit 1 --add-label contract-change"):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.ALLOW)

    def test_attached_short_flags(self) -> None:
        for command in ("asdlc board task edit TASK-1 -a@kyle.w2", "asdlc board task edit TASK-1 -lreview-passed", "backlog task edit 1 -s'In Review'"):
            with self.subTest(command=command):
                self.assertIs(verdict(command), guard.Verdict.DENY)


# Placeholders in the skills' and agents' commands, filled the way an agent would.
_FILLED = {
    "<task>": "TASK-1", "<task id>": "TASK-1", "<task-id>": "TASK-1", "<id>": "TASK-1", "<intent>": "TASK-3", "<intent-id>": "TASK-3",
    "<intent id>": "TASK-3", "<child-id>": "TASK-3.1", "<other child>": "TASK-3.2", "<engineer>": "kyle", "<worker>": "kyle.w1",
    "<reviewer>": "kyle.r1", "<N>": "1", "<n>": "1", "<worktree>": str(WORKTREE), "<repo>": str(CODE), "<review>": "/work/app.worktrees/review-task-1-kyle.r1",
    "<branch>": "task-1-x", "<default branch>": "main", "<doc-id>": "doc-1",
}
_COMMAND = re.compile(r"^(asdlc|asdlc-plugin|backlog|git|gh|cd|uv run) \S")
# What the skills name as a person's, or as never to do: the guard refuses these by design.
# Commands a skill gives for a person's own session: setting their identity, and checking this plugin's own artefacts.
_PERSONS_SESSION = re.compile(r"git config --global|scripts/artefacts\.py")
_REFUSED_BY_DESIGN = re.compile(r"asdlc (accept|approve)\b|permissions --write|-s Done|gh pr merge|--approve|--request-changes|"
                                r"--force|git push origin main|git (-C \S+ )?config (--global )?(--unset )?asdlc\.\w+ ?\S")


def skill_commands() -> list[tuple[str, str]]:
    """Every shell command the plugin's skills, agents, commands, team templates and guide give, with its placeholders filled."""
    files = [*ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("agents/*.md"), *ROOT.glob("commands/*.md"),
             *(ROOT / "templates" / "board" / "plugins" / "team").rglob("*.md"), ROOT / "docs" / "guide.md"]
    found = []
    for path in files:
        text = path.read_text()
        lines = []
        for block in re.findall(r"```(?:sh|bash)?\n(.*?)```", text, re.S):
            block = re.sub(r"\$\(cat <<'EOF'\n.*?\nEOF\n\)", '"x"', re.sub(r"\\\n\s*", " ", block), flags=re.S)
            lines += [line.strip() for line in block.splitlines()]
        lines += re.findall(r"`([^`\n]+)`", text)
        for line in lines:
            if _COMMAND.match(line):
                for placeholder, value in _FILLED.items():
                    line = line.replace(placeholder, value)
                found.append((path.relative_to(ROOT).as_posix(), re.sub(r"<[^<>]*>", "x", line)))
    return found


class SkillCommandsTest(unittest.TestCase):
    """Second review, Important 1: every command a skill or agent tells an agent to run passes the guard."""

    def test_every_command_passes_unless_it_is_a_persons(self) -> None:
        found = skill_commands()
        self.assertGreater(len(found), 150)
        for where, command in found:
            with self.subTest(where=where, command=command):
                outcome = guard.decide_command(command, BOARD, lookup)
                if _REFUSED_BY_DESIGN.search(command):
                    continue
                self.assertIsNot(outcome.verdict, guard.Verdict.DENY, outcome.reason)


    def test_the_commands_the_numbers_need_are_walked(self) -> None:
        """The worker's signed commits, the reviewer's recorded counts and the intent's start are among the commands checked."""
        found = skill_commands()
        for where, part in (("agents/worker.md", '--trailer "Asdlc-Worker: kyle.w1"'), ("agents/reviewer.md", "--findings important=1,nit=1"),
                            ("agents/reviewer.md", "--plan-matched yes"), ("skills/capture-intent/SKILL.md", "asdlc intent-started")):
            with self.subTest(where=where, part=part):
                self.assertTrue(any(w == where and part in command for w, command in found), f"{where} gives no command with {part}")


def compound_parts(command: str) -> list[str]:
    """The subcommands of a compound line, split outside quotes on the separators code.claude.com's permissions page
    names (`&&`, `||`, `;`, `|`, `|&`, `&` and newlines), each joined back as the shell would read it."""
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:  # unbalanced quotes: Claude Code can't parse it either, and asks
        return [command]
    parts: list[list[str]] = [[]]
    for token in tokens:
        if token and set(token) <= set(";&|"):
            parts.append([])
        else:
            parts[-1].append(token)
    return [shlex.join(words) if any(not re.fullmatch(r"[\w@%+=:,./<>*~-]+", w) for w in words) else " ".join(words) for words in parts]


def prompts_for_cd_with_git(command: str) -> bool:
    """Claude Code's rule that no allow rule overrides: a line that changes directory and runs git asks a person
    (code.claude.com/docs/en/permissions, Read-only commands), so a background agent's line is refused."""
    parts = compound_parts(command)
    return any(p == "cd" or p.startswith("cd ") for p in parts) and any(re.match(r"git(\s|$)", p) for p in parts)


def rule_matches(rule: str, command: str) -> bool:
    """A Bash allow rule against a simple command, as code.claude.com's permissions page describes it: a `*` matches any
    text; a trailing ` *` (or `:*`) that is the rule's only wildcard also matches the bare command; otherwise exact."""
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    pattern = rule[5:-1]
    if pattern.endswith(":*"):
        pattern = pattern[:-2] + " *"
    if pattern.count("*") == 1 and pattern.endswith(" *") and command == pattern[:-2]:
        return True
    return re.fullmatch(".*".join(re.escape(part) for part in pattern.split("*")), command) is not None


class BackgroundPermissionsTest(unittest.TestCase):
    """Third review: every command the worker and reviewer agents run is covered by an allow rule asdlc permissions writes,
    so a background agent never stops at a prompt."""

    RULES = asdlc.permission_rules((("acme-app", CODE),), BOARD, {}, (ROOT,))

    def test_the_rule_matcher_follows_the_documented_wildcards(self) -> None:
        self.assertTrue(rule_matches("Bash(ls *)", "ls"))
        self.assertTrue(rule_matches("Bash(git log *)", "git log --oneline"))
        self.assertFalse(rule_matches("Bash(* --help *)", "npm --help"))
        self.assertFalse(rule_matches("Bash(git -C /w/* status *)", "git -C /w/task-1 status"), "two wildcards: no bare match")

    def test_bare_git_forms_and_worktree_housekeeping_are_allowed(self) -> None:
        for command in ("git -C /work/app.worktrees/task-1 status", "git -C /work/app.worktrees/task-1 diff", "git -C /work/app.worktrees/task-1 log",
                        "git -C /work/app.worktrees/task-1 mv a b", "git -C /work/app.worktrees/task-1 rm old.py", "git -C /work/app.worktrees/task-1 restore x",
                        "git -C /work/app.worktrees/task-1 stash", "git -C /work/app.worktrees/task-1 reset --hard HEAD~1", "git -C /work/app fetch"):
            with self.subTest(command=command):
                self.assertTrue(any(rule_matches(rule, command) for rule in self.RULES.allow), command)
        for command in ("git -C /work/app reset --hard", "git -C /work/app rm x", "git -C /work/board.worktrees/plugin-x reset --hard"):
            with self.subTest(command=command):
                self.assertFalse(any(rule_matches(rule, command) for rule in self.RULES.allow), command)

    def test_every_command_the_agents_and_the_orchestrator_give_is_allowed(self) -> None:
        """The first real eval run: background workers were refused `git -C <worktree> ls-files` and every `cd <worktree> && ...`
        line, so a planner wrote placeholder paths. Every part of every command the agents and the orchestrator's skills give
        is now covered by a rule, with no exemption for `cd`."""
        found = [(where, command) for where, command in skill_commands() if where.startswith(("agents/", "skills/"))]
        self.assertGreater(len(found), 120)
        for where, command in found:
            if _REFUSED_BY_DESIGN.search(command) or _PERSONS_SESSION.search(command):
                continue  # a person's, refused by design, or only in a person's session
            command = command.replace('"${CLAUDE_PLUGIN_ROOT}/scripts/', f"{ROOT}/scripts/").replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT))
            command = re.sub(rf"({re.escape(str(ROOT))}/scripts/[\w.-]+)\"", r"\1", command)
            for part in compound_parts(command):
                if not part or re.fullmatch(r"git -C \S+", part):
                    continue  # a bare `git -C <path>` is prose
                with self.subTest(where=where, command=part):
                    self.assertTrue(any(rule_matches(rule, part) for rule in self.RULES.allow), f"no allow rule covers: {part}")

    def test_no_command_an_agent_is_given_changes_directory(self) -> None:
        """Claude Code asks a person before a line that changes directory and runs git, whatever the rules allow, so a
        background agent's `cd <worktree> && git ...` is refused. The agents, skills and team templates give no `cd` at all."""
        found = [(where, command) for where, command in skill_commands() if where != "docs/guide.md"]  # the guide's are a person's
        for where, command in found:
            with self.subTest(where=where, command=command):
                self.assertFalse(any(part.startswith("cd ") or part == "cd" for part in compound_parts(command)), command)
                self.assertFalse(prompts_for_cd_with_git(command), command)

    def test_the_cd_with_git_model_flags_the_first_runs_refused_lines(self) -> None:
        for command in ("cd /work/app.worktrees/task-1 && cat .asdlc-task && asdlc board task view TASK-1 --plain && git ls-files | head -50",
                        "cd /work/app.worktrees/task-1 && git add login.py test_login.py && git commit -q -m x"):
            with self.subTest(command=command):
                self.assertTrue(prompts_for_cd_with_git(command))
        for command in ("git -C /work/app.worktrees/task-1 ls-files", "asdlc record-check TASK-1 --in /work/app.worktrees/task-1 --as kyle.w1 -- git status"):
            with self.subTest(command=command):
                self.assertFalse(prompts_for_cd_with_git(command))

    def test_the_deny_rules_catch_git_that_runs_a_program(self) -> None:
        """Deny beats allow, so these hold even where the `*` in an allow rule would match, and even without the guard."""
        for command in _GIT_PROGRAMS:
            if command.startswith(("GIT_", "FOO=", "sh -c", "asdlc ", "for ")) or ";" in command or command in ("git grep -nO pattern", "git rebase -ix make main"):
                continue  # an allow rule never matches past a GIT_* assignment, and a deny rule is matched against each part
            with self.subTest(command=command):
                self.assertTrue(any(rule_matches(rule, command) for rule in self.RULES.deny), command)
        spanned = "git -C /work/app.worktrees/task-1 config core.fsmonitor evil status"
        self.assertTrue(any(rule_matches(rule, spanned) for rule in self.RULES.allow), "the allow rule's * spans the config call")
        self.assertTrue(any(rule_matches(rule, spanned) for rule in self.RULES.deny), "and a deny rule catches it")

    def test_no_command_an_agent_is_given_is_denied(self) -> None:
        found = [(where, command) for where, command in skill_commands() if where.startswith(("agents/", "skills/"))]
        for where, command in found:
            if _REFUSED_BY_DESIGN.search(command) or _PERSONS_SESSION.search(command):
                continue
            for part in compound_parts(command):
                with self.subTest(where=where, command=part):
                    self.assertFalse([rule for rule in self.RULES.deny if rule_matches(rule, part)], part)
        for command in _PLAIN_GIT:
            if command.startswith("git config") or command.startswith("FOO=") or command in _DENY_RULE_FALSE_POSITIVES:
                continue  # git config is denied to agents outright (reads too): no agent needs it
            with self.subTest(command=command):
                self.assertFalse([rule for rule in self.RULES.deny if rule_matches(rule, command)], command)

    def test_the_deny_rules_known_limits(self) -> None:
        """A rule's `*` matches any text, so a deny rule also matches a flag's name inside a quoted message or a pattern; and a
        rule can't see inside a cluster of short options (`-nO`, `-ix`), which only the guard parses. Both are written down here."""
        for command in _DENY_RULE_FALSE_POSITIVES:
            with self.subTest(command=command):
                self.assertTrue(any(rule_matches(rule, command) for rule in self.RULES.deny), command)
                self.assertIs(guard.decide_command(command, WORKTREE, lookup).verdict, guard.Verdict.ALLOW)
        for command in ("git grep -nO pattern", "git rebase -ix make main"):
            with self.subTest(command=command):
                self.assertFalse(any(rule_matches(rule, command) for rule in self.RULES.deny), command)
                self.assertIs(guard.decide_command(command, WORKTREE, lookup).verdict, guard.Verdict.DENY)

    def test_the_read_only_git_agents_reach_for_is_allowed_in_worktrees_and_the_clone(self) -> None:
        for folder in ("/work/app.worktrees/task-1", "/work/app.worktrees/review-task-1-kyle.r1", "/work/app"):
            for sub in ("ls-files", "grep", "blame", "cat-file", "ls-tree", "merge-base", "rev-list", "describe", "show-ref", "remote get-url"):
                for command in (f"git -C {folder} {sub}", f"git -C {folder} {sub} x y"):
                    with self.subTest(command=command):
                        self.assertTrue(any(rule_matches(rule, command) for rule in self.RULES.allow), command)
        for command in ("git -C /work/app commit -m x", "git -C /work/app push origin x", "git -C /work/app remote add evil x",
                        "git -C /work/board ls-files"):
            with self.subTest(command=command):
                self.assertFalse(any(rule_matches(rule, command) for rule in self.RULES.allow), command)


# Git that runs a program the command doesn't name, or with configuration the command sets (the orchestrator's review of #26).
_GIT_PROGRAMS = (
    "git -c core.fsmonitor=evil status", "git -C /work/app.worktrees/task-1 -c core.pager=evil log", "git -ccore.pager=evil log",
    "git --config-env=core.pager=EVIL log", "git -C /work/app.worktrees/task-1 --config-env core.pager=EVIL log",
    "git --exec-path=/tmp/evil status", "git -C /work/app.worktrees/task-1 grep -Ovim pattern", "git grep -O pattern",
    "git grep -nO pattern", "git grep --open-files-in-pager=vim x", "git grep --open-files-in-pager x",
    "git fetch --upload-pack=evil origin", "git fetch --upload-pack evil origin", "git pull --upload-pack=evil origin main",
    "git push --receive-pack=evil origin HEAD", "git push --exec=evil origin HEAD", "git ls-remote --upload-pack=evil origin",
    "git clone -u evil https://x/y", "git clone -uevil https://x/y", "git ls-remote -u evil origin",
    "git diff --ext-diff", "git -C /work/app.worktrees/task-1 diff --ext-diff HEAD", "git show --textconv HEAD:x", "git log -p --ext-diff",
    "git clone -c core.hooksPath=/evil https://x/y", "git clone --config=core.hooksPath=/evil https://x/y", "git clone --template=/evil https://x/y",
    "git init --template=/evil x", "git rebase -x make origin/main", "git rebase --exec=make origin/main", "git rebase -ix make main",
    "git difftool", "git -C /work/app.worktrees/task-1 mergetool", "git submodule foreach ls", "git bisect run make",
    "git filter-branch --tree-filter x", "git instaweb", "git config core.fsmonitor evil",
    "git -C /work/app.worktrees/task-1 config core.fsmonitor evil status", "git config set core.pager evil", "git config --add alias.x '!evil'",
    "git config --global asdlc.engineer kyle",
    "GIT_PAGER=evil git log", "GIT_SSH_COMMAND=evil git -C /work/app.worktrees/task-1 fetch origin", "env GIT_EXTERNAL_DIFF=evil git diff",
    "env -u HOME GIT_EDITOR=evil git commit", "export GIT_CONFIG_COUNT=1", "GIT_CONFIG_KEY_0=core.pager GIT_CONFIG_VALUE_0=evil git log",
    "FOO=1 GIT_EDITOR=evil git commit", "GIT_DIR=/elsewhere/.git; git status", "sh -c 'git -c core.pager=evil log'",
    "asdlc record-check TASK-1 --in /work/app.worktrees/task-1 --as kyle.w1 -- git -c core.pager=evil log",
    "for f in a; do git -c core.pager=evil log; done",
)
# What workers, reviewers and people run, which must stay allowed.
_PLAIN_GIT = (
    "git push -u origin HEAD", "git -C /work/app.worktrees/task-1 push -u origin HEAD", "git grep -n pattern", "git grep -e -O",
    "git config asdlc.engineer", "git config --get asdlc.board", "git config --global --get asdlc.engineer", "git config get asdlc.board",
    "git config --list", "git diff --no-ext-diff", "git show --no-textconv HEAD:x", "git rebase origin/main", "git rebase -X ours origin/main",
    "git -C /work/app.worktrees/task-1 commit -m 'use -c and --exec in docs' --trailer 'Asdlc-Worker: kyle.w1'",
    "git log --grep=x -i", "git fetch origin", "git clone https://x/y", "git -C /work/app worktree add --detach /work/app.worktrees/r x",
    "FOO=1 make test", "git log -O orderfile", "git commit -c HEAD", "git fetch -u origin",
)


# Allowed by the guard but matched by a deny rule, since a rule's `*` also matches text inside quotes or a pattern.
_DENY_RULE_FALSE_POSITIVES = ("git grep -e -O", "git -C /work/app.worktrees/task-1 commit -m 'use -c and --exec in docs' --trailer 'Asdlc-Worker: kyle.w1'")


class GitProgramTest(unittest.TestCase):
    """The `*` in `git -C <worktree>/* <subcommand> *` lets options through: `-c core.fsmonitor=<cmd>`, `grep -O<program>` and the like
    would run any program without a prompt, under rules asdlc wrote. The guard refuses them, with why."""

    def test_denies_git_that_runs_a_program_or_sets_configuration(self) -> None:
        for command in _GIT_PROGRAMS:
            with self.subTest(command=command):
                outcome = guard.decide_command(command, WORKTREE, lookup)
                self.assertIs(outcome.verdict, guard.Verdict.DENY)
                self.assertIn("makes git run a program this command doesn't name", outcome.reason)
                self.assertIn("ask the person", outcome.reason)

    def test_the_reason_names_the_form(self) -> None:
        for command, says in (("git -c a=b log", "git -c"), ("git grep -Ovim x", "git grep -O"), ("GIT_PAGER=x git log", "setting GIT_PAGER"),
                              ("git rebase -x make main", "git rebase --exec"), ("git clone -u x y", "git clone -u"), ("git config a.b c", "git config")):
            with self.subTest(command=command):
                self.assertIn(says, guard.decide_command(command, WORKTREE, lookup).reason)

    def test_allows_plain_git(self) -> None:
        for command in _PLAIN_GIT:
            with self.subTest(command=command):
                self.assertIs(guard.decide_command(command, WORKTREE, lookup).verdict, guard.Verdict.ALLOW)

    def test_env_names(self) -> None:
        self.assertEqual(guard.env_names(["A=1", "B=2", "git", "log", "C=3"]), ["A", "B"])
        self.assertEqual(guard.env_names(["env", "-u", "HOME", "GIT_X=1", "git"]), ["GIT_X"])
        self.assertEqual(guard.env_names(["export", "GIT_Y=1", "Z=2"]), ["GIT_Y", "Z"])
        self.assertEqual(guard.env_names(["git", "log"]), [])


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
