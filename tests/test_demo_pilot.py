"""A scripted demonstration of pilot readiness: asdlc doctor on two machines, and asdlc stats.

It replays the cross-machine review story (test_demo_review) with one addition: ann's
orchestrator onboards acme/api the first time it claims work there, publishing the
repository's plugin to the tasks repository. Then `asdlc doctor` runs on kyle's machine,
which is ready, and on ann's, which has problems a developer really meets; and `asdlc
stats` reports the story's numbers from the board's history and ann's event log.

The machines' programs are what doctor looks for on PATH. `claude`, `gh` and `uv` are
small stand-ins, so each machine can have its own installed plugins and sign-in; `claude
plugin validate` is passed to the real CLI when it is installed. git, backlog, asdlc and
asdlc-plugin are the real ones.

Run it with ASDLC_DEMO=1 to print what doctor and stats say; the pull request quotes it.
"""

import json
import os
import shutil
import sys
import unittest
from pathlib import Path

from tests import test_demo_review as review
from tests.support import ROOT, run_script
from tests.test_asdlc import BACKLOG, needs_backlog

SAY = bool(os.environ.get("ASDLC_DEMO"))
REAL_CLAUDE = shutil.which("claude") or ""

CLAUDE = """#!{python}
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["plugin", "validate"]:
    if os.environ.get("REAL_CLAUDE"):
        os.execv(os.environ["REAL_CLAUDE"], [os.environ["REAL_CLAUDE"], *args])
    print("Validation passed")
    raise SystemExit(0)
state = json.load(open(os.environ["DEMO_CLAUDE_STATE"]))
if args == ["plugin", "marketplace", "list", "--json"]:
    print(json.dumps(state["marketplaces"]))
elif args == ["plugin", "list", "--json"]:
    print(json.dumps(state["plugins"]))
else:
    raise SystemExit(f"demo claude: {{args}} is not scripted")
"""
GH = """#!/bin/sh
case "$1" in
  --version) echo "gh version 2.80.0 (demo)";;
  auth) [ "$DEMO_GH_SIGNED_IN" = 1 ] || {{ echo "You are not logged into any GitHub hosts." >&2; exit 1; }};;
  *) exit 1;;
esac
"""
LAUNCH = '#!/bin/sh\nexec "{python}" "{script}" "$@"\n'
TESTING_RULE = """---
paths:
  - "**/*.py"
---
# Testing acme/api

Applies to every Python file in acme/api.

- There is no test suite yet: `python3 -c 'import login'` is the test command, so a change that breaks the import fails it.
"""
COMMANDS = """[build]
run = "python3 -c \\"import ast; ast.parse(open('login.py').read())\\""

[test]
run = "python3 -c 'import login'"

[lint]
run = "python3 -m py_compile login.py"
"""


def write(path: Path, text: str, mode: int = 0o644) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return path


@needs_backlog
class PilotReadinessTest(review.CrossMachineReviewTest):
    def setUp(self) -> None:
        super().setUp()
        self.onboarded = ""
        self.bin = self.root / "bin"
        write(self.bin / "claude", CLAUDE.format(python=sys.executable), 0o755)
        write(self.bin / "gh", GH.format(), 0o755)
        write(self.bin / "uv", "#!/bin/sh\necho 'uv 0.9.0 (demo)'\n", 0o755)
        for name in ("asdlc", "asdlc-plugin"):
            write(self.bin / name, LAUNCH.format(python=sys.executable, script=ROOT / "scripts" / name), 0o755)
        system = [str(Path(found).parent) for found in (shutil.which("git"), BACKLOG, shutil.which("node"), shutil.which("python3")) if found]
        path = os.pathsep.join(dict.fromkeys([str(self.bin), *system, "/usr/bin", "/bin"]))
        kit = self.root / "authoring-kit"
        for relative in ("skills/choosing-extension-types/SKILL.md", "skills/authoring-skills/SKILL.md", "skills/authoring-hooks/SKILL.md",
                         "agents/authoring-auditor.md"):
            write(kit / relative, "demo\n")
        market = json.loads((self.ann.board / ".claude-plugin" / "marketplace.json").read_text())["name"]
        states = {
            "kyle": {"marketplaces": [{"name": "asdlc", "source": "github"}, {"name": market, "source": "git", "autoUpdate": True}],
                     "plugins": [{"id": f"team@{market}", "enabled": True}, {"id": "asdlc@asdlc", "enabled": True},
                                 {"id": "authoring-kit@owner", "version": "0.7.0", "enabled": True, "installPath": str(kit)}]},
            "ann": {"marketplaces": [{"name": "asdlc", "source": "github"}, {"name": market, "source": "git"}],
                    "plugins": [{"id": "asdlc@asdlc", "enabled": True}]},
        }
        for machine in (self.ann, self.kyle):
            state = write(machine.home / "claude-state.json", json.dumps(states[machine.name]))
            machine.env |= {"PATH": path, "DEMO_CLAUDE_STATE": str(state), "REAL_CLAUDE": REAL_CLAUDE, "DEMO_GH_SIGNED_IN": "1"}

    def plugin(self, machine: review.demo.Machine, *args: str) -> str:
        done = run_script("scripts/asdlc-plugin", *args, env=machine.env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout

    def build(self, machine: review.demo.Machine, task_id: str, worktree: Path, text: str, message: str) -> str:
        """Before ann's first build in acme/api, her orchestrator onboards it (orchestrate step 5)."""
        repo = self.api[machine.name]
        if not self.onboarded:
            status = json.loads(self.plugin(machine, "status", str(repo), "--json"))
            self.assertEqual((status["published"], status["onboarding"]), (False, None))
            self.plugin(machine, "scaffold", str(repo))
            folder = Path(str(status["board"])).parent / f"{Path(str(status['board'])).name}.worktrees" / f"plugin-{status['slug']}" / "plugins" / status["slug"]
            write(folder / "commands.toml", COMMANDS)
            write(folder / "rules" / "testing-python.md", TESTING_RULE)
            for name in ("build", "test", "lint"):
                self.plugin(machine, "verify-command", str(repo), name)
            self.onboarded = self.plugin(machine, "publish", status["slug"], "--repo", str(repo))
            self.say(f"   (ann's orchestrator saw acme-api had no plugin and onboarded it before building: "
                     f"{self.onboarded.splitlines()[0]})")
        return super().build(machine, task_id, worktree, text, message)

    def doctor(self, machine: review.demo.Machine) -> tuple[int, dict[str, object], str]:
        done = machine.asdlc("doctor", ok=False)
        report = machine.asdlc("doctor", "--json", ok=False)
        return done.returncode, json.loads(report.stdout), done.stdout

    def test_review_across_machines_and_the_fallback(self) -> None:
        super().test_review_across_machines_and_the_fallback()
        self.assertIn("published plugins/acme-api", self.onboarded)

        # kyle's machine is ready.
        code, report, text = self.doctor(self.kyle)
        self.assertEqual((code, report["failed"], report["warnings"]), (0, 0, 0), text)
        self.assertIn("pass  plugin acme-api: asdlc-plugin check is clean", text)
        self.say(f"\n$ asdlc doctor            # on kyle's machine (exit {code})\n{text.rstrip()}")

        # ann's machine has problems.
        (self.ann.board / "asdlc.toml").write_text('stale_after = "2h"\nreview_fallback_after = "3h"\n')
        self.ann.git(self.api["ann"], "config", "--unset", "asdlc.board")
        self.ann.git(self.api["ann"], "worktree", "add", "--quiet", "--detach", str(self.ann.home / "api.worktrees" / "review-task-2-ann.r1"), "origin/main")
        self.ann.env["DEMO_GH_SIGNED_IN"] = "0"
        code, report, text = self.doctor(self.ann)
        failed = {f["area"] for f in report["findings"] if f["level"] == "fail"}
        warned = {f["area"] for f in report["findings"] if f["level"] == "warn"}
        self.assertEqual(code, 1)
        self.assertEqual(failed, {"board", "asdlc.toml", "repository acme-api", "team plugin"})
        self.assertEqual(warned, {"gh", "auto-update", "authoring kit", "leftover"})
        self.say(f"\n$ asdlc doctor            # on ann's machine (exit {code})\n{text.rstrip()}")

        # The story's numbers, from the board's history and ann's event log.
        stats = self.ann.asdlc("stats")
        numbers = json.loads(self.ann.asdlc("stats", "--json").stdout)
        self.assertEqual(numbers["tasks"], {"claimed": 2, "in_review": 2, "done": 0})
        self.assertEqual(numbers["claim_to_review"]["count"], 2)
        self.assertEqual(numbers["review_wait"]["count"], 3)
        self.assertEqual(numbers["changes_requested"]["by_task"], {"TASK-1": 1, "TASK-2": 0})
        self.assertEqual((numbers["reviews"]["total"], numbers["reviews"]["same_machine"]), (3, 1))
        self.assertEqual((numbers["races"]["claimed"], numbers["races"]["lost"]), (2, 0))
        self.assertEqual([o["plugin"] for o in numbers["onboardings"]], ["acme-api"])
        self.assertEqual(numbers["onboardings"][0]["task"], "TASK-1")
        self.say(f"\n$ asdlc stats             # on ann's machine, after the story, which runs in seconds\n{stats.stdout.rstrip()}")


if __name__ == "__main__":
    unittest.main()
