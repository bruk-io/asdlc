import json
import os
import random
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.support import ROOT, git, load, run_script

load("scripts/repo_slug.py")  # scripts/asdlc imports it from beside itself
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
        "type": "task", "parent": "", "ordinal": None, "dependencies": (), "path": "", "project": "app",
    } | fields
    return asdlc.Task(id=task_id, **values)


PICKER = asdlc.Picker(engineer="kyle", worker="kyle.w1", registered=frozenset({"app"}))


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
        ready, _ = asdlc.candidates(tasks, PICKER)
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
        ready, skipped = asdlc.candidates(tasks, PICKER)
        self.assertEqual([t.id for t in ready], ["TASK-3.1", "TASK-5"])
        self.assertEqual({t.id for t, _ in skipped}, {"TASK-4", "TASK-7", "TASK-8"})


class ClaimDecisionsTest(unittest.TestCase):
    def test_claim_refusal(self) -> None:
        open_task = task("TASK-1")
        self.assertIsNone(asdlc.claim_refusal(open_task, "TASK-1", (open_task,), "kyle.w1"))
        self.assertIn("not a task", asdlc.claim_refusal(None, "TASK-9", (), "kyle.w1"))
        held = task("TASK-1", status="In Progress", assignees=("@a",))
        self.assertIn("assigned to @a", asdlc.claim_refusal(held, "TASK-1", (held,), "kyle.w1"))
        done = task("TASK-1", status="Done")
        self.assertIn("not To Do", asdlc.claim_refusal(done, "TASK-1", (done,), "kyle.w1"))
        big = task("TASK-1", labels=("size-8",))
        self.assertIn("split it", asdlc.claim_refusal(big, "TASK-1", (big,), "kyle.w1"))

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
        self.assertEqual(fields["labels"], ("size-1", "size-2", "size-3", "size-4", "size-5", "size-8", "changes-requested", "review-passed"))
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


class IdentityTest(unittest.TestCase):
    def test_engineers_and_their_workers(self) -> None:
        self.assertEqual(asdlc.engineer_name("@kyle"), "kyle")
        for bad in ("kyle.w1", "", "a b"):
            with self.subTest(name=bad), self.assertRaises(asdlc.AsdlcError):
                asdlc.engineer_name(bad)
        self.assertEqual(asdlc.worker_for("@kyle.w1", "kyle"), "kyle.w1")
        for bad in ("kyle", "kyle.", "ann.w1", "kyleb.w1"):
            with self.subTest(worker=bad), self.assertRaisesRegex(asdlc.AsdlcError, "not one of kyle's workers"):
                asdlc.worker_for(bad, "kyle")
        self.assertEqual(asdlc.owner_of("@kyle.w1"), "kyle")

    def test_people_and_workers_in_the_assignee_list(self) -> None:
        assignees = ("@kyle", "@kyle.w1", "@ann")
        self.assertEqual(asdlc.people(assignees), ("@kyle", "@ann"))
        self.assertEqual(asdlc.workers(assignees), ("@kyle.w1",))
        self.assertTrue(asdlc.reserved_for(task("TASK-1", assignees=("@kyle",)), "kyle"))
        self.assertFalse(asdlc.reserved_for(task("TASK-1", assignees=("@kyle.w1",)), "kyle"))


class ReservationTest(unittest.TestCase):
    def test_reserved_work_goes_only_to_its_owners_workers(self) -> None:
        reserved = task("TASK-1", assignees=("@kyle",))
        self.assertIsNone(asdlc.claim_refusal(reserved, "TASK-1", (reserved,), "kyle.w2"))
        self.assertIn("reserved for @kyle", asdlc.claim_refusal(reserved, "TASK-1", (reserved,), "ann.w1"))
        claimed = task("TASK-1", assignees=("@kyle", "@kyle.w1"))
        self.assertIn("assigned to @kyle, @kyle.w1", asdlc.claim_refusal(claimed, "TASK-1", (claimed,), "kyle.w2"))

    def test_race_result_with_a_reservation(self) -> None:
        self.assertIs(asdlc.race_result(task("TASK-1", assignees=("@kyle",)), "kyle.w1"), asdlc.Race.OPEN)
        self.assertIs(asdlc.race_result(task("TASK-1", assignees=("@kyle",)), "ann.w1"), asdlc.Race.LOST)
        won = task("TASK-1", status="In Progress", assignees=("@kyle", "@kyle.w1"))
        self.assertIs(asdlc.race_result(won, "kyle.w1"), asdlc.Race.WON)


class PickingTest(unittest.TestCase):
    def picker(self, worker: str = "kyle.w1", **fields: object) -> object:
        values = {"engineer": asdlc.owner_of(worker), "worker": worker, "registered": frozenset({"acme-api", "acme-web", "acme-docs"})} | fields
        return asdlc.Picker(**values)

    def test_eligible_only_in_registered_repositories(self) -> None:
        tasks = (task("TASK-1", project="acme-api"), task("TASK-2", project="acme-ios"), task("TASK-3", project=""))
        ready, skipped = asdlc.candidates(tasks, self.picker())
        self.assertEqual([t.id for t in ready], ["TASK-1"])
        reasons = dict((t.id, why) for t, why in skipped)
        self.assertIn("acme-ios, which is not registered on this machine", reasons["TASK-2"])
        self.assertIn("has no project", reasons["TASK-3"])

    def test_reserved_work_is_eligible_only_for_its_owner_and_comes_first(self) -> None:
        tasks = (
            task("TASK-1", project="acme-api", priority="high"),
            task("TASK-2", project="acme-api", priority="low", assignees=("@kyle",)),
            task("TASK-3", project="acme-api", priority="high", assignees=("@ann",)),
        )
        self.assertEqual([t.id for t in asdlc.candidates(tasks, self.picker("kyle.w1"))[0]], ["TASK-2", "TASK-1"])
        self.assertEqual([t.id for t in asdlc.candidates(tasks, self.picker("ann.w1"))[0]], ["TASK-3", "TASK-1"])
        self.assertEqual([t.id for t in asdlc.candidates(tasks, self.picker("bo.w1"))[0]], ["TASK-1"])

    def test_preferences_then_priority(self) -> None:
        tasks = (
            task("TASK-1", project="acme-api", priority="high"),
            task("TASK-2", project="acme-web", priority="low"),
            task("TASK-3", project="acme-docs", priority="high"),
        )
        plain = asdlc.rank(tasks, self.picker())
        self.assertEqual([t.id for t in plain], ["TASK-1", "TASK-3", "TASK-2"])
        preferring = asdlc.rank(tasks, self.picker(prefer=("acme-web", "acme-docs")))
        self.assertEqual([t.id for t in preferring], ["TASK-2", "TASK-3", "TASK-1"])

    def test_avoided_repositories_only_for_reserved_work(self) -> None:
        tasks = (task("TASK-1", project="acme-api"), task("TASK-2", project="acme-api", assignees=("@kyle",)), task("TASK-3", project="acme-web"))
        ready, skipped = asdlc.candidates(tasks, self.picker(avoid=("acme-api",)))
        self.assertEqual([t.id for t in ready], ["TASK-2", "TASK-3"])
        self.assertIn("which devs/kyle.yaml avoids", dict((t.id, why) for t, why in skipped)["TASK-1"])

    def test_workers_start_at_different_places_in_the_best_tier(self) -> None:
        tasks = tuple(task(f"TASK-{n}", project="acme-api", priority="medium") for n in range(1, 5)) + (task("TASK-9", project="acme-api", priority="low"),)
        firsts = [asdlc.rank(tasks, self.picker(f"kyle.w{n}"))[0].id for n in range(1, 5)]
        self.assertEqual(firsts, ["TASK-1", "TASK-2", "TASK-3", "TASK-4"])
        self.assertEqual(asdlc.rank(tasks, self.picker("kyle.w5"))[0].id, "TASK-1")
        for n in range(1, 6):
            self.assertEqual(asdlc.rank(tasks, self.picker(f"kyle.w{n}"))[-1].id, "TASK-9", "only the best tier rotates")
        self.assertEqual(asdlc.spread("kyle.helper"), asdlc.spread("kyle.helper"))

    def test_active_workers_count_against_the_cap(self) -> None:
        tasks = (
            task("TASK-1", status="In Progress", assignees=("@kyle.w1",)),
            task("TASK-2", status="In Progress", assignees=("@kyle", "@kyle.w2")),
            task("TASK-3", status="In Review", assignees=("@kyle.w3",)),
            task("TASK-4", status="In Progress", assignees=("@ann.w1",)),
        )
        self.assertEqual([t.id for t in asdlc.active_workers(tasks, "kyle")], ["TASK-1", "TASK-2"])


class PrefsTest(unittest.TestCase):
    def test_reads_the_flat_subset(self) -> None:
        text = "# kyle's preferences\nname: kyle\nprefer: [Acme-API, 'acme-web']\navoid: [acme-docs]\nworkers: 4  # at most\nreview: false\n"
        self.assertEqual(asdlc.parse_prefs(text, "kyle"), asdlc.Prefs("kyle", ("acme-api", "acme-web"), ("acme-docs",), 4, False))
        self.assertEqual(asdlc.parse_prefs("name: kyle\n", "kyle"), asdlc.Prefs("kyle", (), (), 3, True))

    def test_refuses_anything_else(self) -> None:
        cases = {
            "name: kyle\nteams:\n  a: b\n": "unknown key 'teams'",
            "name: kyle\nprefer:\n  - acme-api\n": "in brackets, on one line",
            "prefer: [a]\n  nested: x\n": "not 'key: value'",
            "workers: 2\n": "name is required",
            "workers: 0\n": "at least 1",
            "workers: many\n": "whole number",
            "review: yes\n": "true or false",
            "name: ann\n": "must match",
            "prefer: [a, [b]]\n": "in brackets",
            "prefer: acme-api\n": "in brackets",
            "prefer: [a]\navoid: [a]\n": "both preferred and avoided",
            "workers: 2\nworkers: 3\n": "given twice",
            "workers: &anchor 2\n": "plain value",
        }
        for text, says in cases.items():
            named = text if text.startswith("name:") or says == "name is required" else f"name: kyle\n{text}"
            with self.subTest(text=named), self.assertRaisesRegex(asdlc.AsdlcError, re.escape(says)):
                asdlc.parse_prefs(named, "kyle")


class SettingsTest(unittest.TestCase):
    def test_durations(self) -> None:
        self.assertEqual(asdlc.parse_duration("2h"), timedelta(hours=2))
        self.assertEqual(asdlc.parse_duration("1h30m"), timedelta(minutes=90))
        self.assertEqual(asdlc.parse_duration("1d"), timedelta(days=1))
        for bad in ("", "2 hours", "h", "-1h"):
            with self.subTest(raw=bad), self.assertRaises(asdlc.AsdlcError):
                asdlc.parse_duration(bad)
        self.assertEqual(asdlc.human(timedelta(hours=3, minutes=5)), "3h 5m")

    def test_the_boards_asdlc_toml(self) -> None:
        self.assertEqual(asdlc.parse_settings(""), asdlc.Settings(timedelta(0)))
        self.assertEqual(asdlc.parse_settings('stale_after = "45m"\nother = 1\n'), asdlc.Settings(timedelta(0)), "keys an older asdlc wrote are ignored")
        self.assertEqual(asdlc.parse_settings('review_fallback_after = "1h"\n').review_fallback_after, timedelta(hours=1))
        with self.assertRaisesRegex(asdlc.AsdlcError, "in quotes"):
            asdlc.parse_settings("review_fallback_after = 2\n")
        with self.assertRaisesRegex(asdlc.AsdlcError, "not valid TOML"):
            asdlc.parse_settings("review_fallback_after = \n")


class RegistryTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        entries = (asdlc.Registered("acme-web", Path('/src/we "b"'), Path("/src/board")), asdlc.Registered("acme-api", Path("/src/api"), Path("/src/board")))
        parsed = asdlc.parse_registry(asdlc.registry_text(entries))
        self.assertEqual(list(parsed), ["acme-api", "acme-web"])
        self.assertEqual(parsed["acme-web"].path, Path('/src/we "b"'))

    def test_board_projects(self) -> None:
        config = 'project_name: "b"\nprojects:\n  - acme-api\ntask_prefix: "task"\n'
        updated = asdlc.with_project(config, "acme-web")
        fields = asdlc.frontmatter(f"---\n{updated}---\n")
        self.assertEqual(fields["projects"], ("acme-api", "acme-web"))
        self.assertEqual(fields["task_prefix"], "task")
        self.assertIsNone(asdlc.with_project(updated, "acme-web"))
        self.assertEqual(asdlc.frontmatter(f"---\n{asdlc.with_project('a: 1', 'x')}---\n")["projects"], ("x",))


class FrontmatterKeyTest(unittest.TestCase):
    TEXT = "---\nid: TASK-1\nlabels:\n  - a\nstatus: To Do\n---\n\n## Description\nlabels: not this\n"

    def test_sets_replaces_and_removes_a_key(self) -> None:
        added = asdlc.with_key(self.TEXT, "asdlc_reserved_for_author", "kyle")
        self.assertEqual(asdlc.task_from("x", added).reserved_for_author, "kyle")
        replaced = asdlc.with_key(asdlc.with_key(added, "labels", "[b]"), "asdlc_reserved_for_author", "ann")
        self.assertEqual(asdlc.task_from("x", replaced).labels, ("b",))
        self.assertEqual(asdlc.task_from("x", replaced).reserved_for_author, "ann")
        self.assertIn("labels: not this", replaced)
        self.assertEqual(asdlc.with_key(added, "asdlc_reserved_for_author", None), self.TEXT)
        with self.assertRaises(asdlc.AsdlcError):
            asdlc.with_key("no frontmatter", "a", "b")

    def test_reads_project_and_the_reservation(self) -> None:
        found = asdlc.task_from("backlog/drafts/draft-1 - x.md", "---\nid: DRAFT-1\nproject: Acme-API\nasdlc_reserved_for_author: kyle\n---\n")
        self.assertEqual((found.project, found.reserved_for_author), ("acme-api", "kyle"))
        self.assertEqual(asdlc.task_from("x", "---\nid: TASK-1\nasdlc_lead: '@kyle.lead'\nasdlc_heartbeat: now\n---\n").id, "TASK-1", "keys written by an older asdlc are ignored")
        self.assertTrue(asdlc.is_draft(found))


class MineReportTest(unittest.TestCase):
    NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)

    def test_mine_report(self) -> None:
        items = (
            task("TASK-1", status="In Progress", assignees=("@kyle", "@kyle.w1")),
            task("TASK-2", status="In Review", assignees=("@kyle.w2",)),
            task("TASK-3", status="Done", assignees=("@kyle.w3",)),
            task("TASK-4", assignees=("@kyle",)),
            task("TASK-6", status="In Progress", assignees=("@ann.w1",)),
        )
        report = asdlc.mine_report(items, "kyle", asdlc.Prefs("kyle", workers=3))
        self.assertEqual((report["active"], report["workers_cap"]), (1, 3))
        self.assertEqual([(r["id"], r["workers"]) for r in report["tasks"]], [("TASK-1", ["kyle.w1"]), ("TASK-2", ["kyle.w2"])])
        self.assertNotIn("leads", report)
        self.assertEqual([r["id"] for r in report["reserved"]], ["TASK-4"])


class ReviewLogicTest(unittest.TestCase):
    NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)

    def reviewing(self, engineer: str = "kyle", **fields: object) -> object:
        values = {"registered": frozenset({"app"}), "now": self.NOW, "fallback_after": timedelta(minutes=30)} | fields
        return asdlc.Reviewing(engineer, f"{engineer}.r1", **values)

    def test_reviewer_names(self) -> None:
        self.assertEqual(asdlc.reviewer_for("@kyle.r2", "kyle"), "kyle.r2")
        for raw in ("kyle.w1", "ann.r1", "kyle", "kyle.r"):
            with self.subTest(raw=raw), self.assertRaises(asdlc.AsdlcError):
                asdlc.reviewer_for(raw, "kyle")

    def test_reads_the_review_keys_and_references(self) -> None:
        found = asdlc.task_from("x", "---\nid: TASK-1\nreferences:\n  - task-1-x\n  - https://github.com/a/b/pull/3\n"
                                     "asdlc_reviewer: kyle.r1\nasdlc_review_kind: cross-machine\n---\n")
        self.assertEqual((found.reviewer, found.review_kind, found.references), ("kyle.r1", "cross-machine", ("task-1-x", "https://github.com/a/b/pull/3")))
        self.assertEqual(asdlc.review_refs(found.references), ("task-1-x", "https://github.com/a/b/pull/3"))
        self.assertEqual(asdlc.review_refs(("https://example.com/notes", "b", "https://git.example.com/a/b/-/merge_requests/4")),
                         ("b", "https://git.example.com/a/b/-/merge_requests/4"))
        self.assertEqual(asdlc.review_refs(()), (None, None))

    def test_authors_are_the_engineers_of_the_workers(self) -> None:
        self.assertEqual(asdlc.authors(task("TASK-1", assignees=("@ann", "@ann.w1"))), {"ann"})
        self.assertEqual(asdlc.authors(task("TASK-1", assignees=("@lee",))), {"lee"})
        self.assertEqual(asdlc.review_kind(task("TASK-1", assignees=("@ann.w1",)), "ann"), asdlc.ReviewKind.SAME_MACHINE)
        self.assertEqual(asdlc.review_kind(task("TASK-1", assignees=("@ann.w1",)), "kyle"), asdlc.ReviewKind.CROSS_MACHINE)

    def test_who_may_claim_a_review(self) -> None:
        ready = task("TASK-1", status="In Review", assignees=("@ann.w1",))
        entered = self.NOW - timedelta(minutes=5)
        self.assertIsNone(asdlc.review_refusal(ready, self.reviewing(), entered))
        cases = {
            "not In Review": task("TASK-1", status="In Progress", assignees=("@ann.w1",)),
            "being reviewed by @lee.r1": task("TASK-1", status="In Review", assignees=("@ann.w1",), reviewer="lee.r1"),
            "passed review": task("TASK-1", status="In Review", assignees=("@ann.w1",), labels=("size-2", "review-passed")),
            "not registered on this machine": task("TASK-1", status="In Review", assignees=("@ann.w1",), project="elsewhere"),
            "no project": task("TASK-1", status="In Review", assignees=("@ann.w1",), project=""),
        }
        for says, subject in cases.items():
            with self.subTest(says=says):
                self.assertIn(says, asdlc.review_refusal(subject, self.reviewing(), entered))
        self.assertIsNone(asdlc.review_refusal(task("TASK-1", status="In Review", assignees=("@ann.w1",), labels=("changes-requested",)), self.reviewing(), entered))

    def test_the_author_reviews_only_with_fallback_after_the_timeout(self) -> None:
        own = task("TASK-1", status="In Review", assignees=("@kyle", "@kyle.w1"))
        thirty_one = self.NOW - timedelta(minutes=31)
        self.assertIn("--fallback", asdlc.review_refusal(own, self.reviewing(), thirty_one))
        self.assertIn("waited 29m", asdlc.review_refusal(own, self.reviewing(fallback=True), self.NOW - timedelta(minutes=29)))
        self.assertIn("waited 30m", asdlc.review_refusal(own, self.reviewing(fallback=True), self.NOW - timedelta(minutes=30)))
        self.assertIn("waited 0m", asdlc.review_refusal(own, self.reviewing(fallback=True), None))
        self.assertIsNone(asdlc.review_refusal(own, self.reviewing(fallback=True), thirty_one))
        self.assertIsNone(asdlc.review_refusal(own, self.reviewing(fallback=True, fallback_after=timedelta(hours=1)), self.NOW - timedelta(minutes=61)))
        self.assertIn("review_fallback_after (1h 0m)", asdlc.review_refusal(own, self.reviewing(fallback=True, fallback_after=timedelta(hours=1)), thirty_one))

    def test_candidates_oldest_first_and_own_work_last(self) -> None:
        tasks = (
            task("TASK-1", status="In Review", assignees=("@ann.w1",), path="a"),
            task("TASK-2", status="In Review", assignees=("@ann.w2",), path="b"),
            task("TASK-3", status="In Review", assignees=("@kyle.w1",), path="c"),
            task("TASK-4", status="In Review", assignees=("@lee.w1",), path="d", reviewer="lee.r1"),
            task("TASK-5", status="In Progress", assignees=("@ann.w3",), path="e"),
        )
        entered = {"a": self.NOW - timedelta(minutes=10), "b": self.NOW - timedelta(minutes=20), "c": self.NOW - timedelta(hours=2)}
        ready, skipped = asdlc.review_candidates(tasks, self.reviewing(), entered)
        self.assertEqual([t.id for t in ready], ["TASK-2", "TASK-1"])
        self.assertEqual({t.id for t, _ in skipped}, {"TASK-3", "TASK-4"})
        ready, _ = asdlc.review_candidates(tasks, self.reviewing(fallback=True), entered)
        self.assertEqual([t.id for t in ready], ["TASK-2", "TASK-1", "TASK-3"])

    def test_only_the_claiming_reviewer_finishes(self) -> None:
        held = task("TASK-1", status="In Review", assignees=("@ann.w1",), reviewer="kyle.r1")
        self.assertIsNone(asdlc.review_done_refusal(held, "TASK-1", "kyle.r1"))
        self.assertIn("@kyle.r1 holds its review", asdlc.review_done_refusal(held, "TASK-1", "lee.r1"))
        self.assertIn("nobody holds its review", asdlc.review_done_refusal(task("TASK-1", status="In Review"), "TASK-1", "kyle.r1"))
        self.assertIn("not In Review", asdlc.review_done_refusal(task("TASK-1", status="Done", reviewer="kyle.r1"), "TASK-1", "kyle.r1"))
        self.assertIn("not a task", asdlc.review_done_refusal(None, "TASK-9", "kyle.r1"))

    def test_earlier_citations_are_other_tasks_whose_last_review_cited_the_policy(self) -> None:
        tasks = (
            task("TASK-1", review_policies=("testing", "review")),
            task("TASK-2", review_policies=("testing",)),
            task("TASK-3", review_policies=()),
            task("TASK-10", review_policies=("testing",)),
            task("TASK-4", review_policies=("security",)),
        )
        self.assertEqual(asdlc.earlier_citations(tasks, "TASK-2", ("testing", "review", "naming")),
                         {"testing": ("TASK-1", "TASK-10"), "review": ("TASK-1",)})
        self.assertEqual(asdlc.earlier_citations(tasks, "TASK-4", ("security",)), {})
        self.assertEqual(asdlc.earlier_citations(tasks, "TASK-3", ()), {})

    def test_review_comment(self) -> None:
        text = asdlc.review_comment("kyle.r1", "same-machine", asdlc.ReviewVerdict.CHANGES, "  [Bugs, Important] x  ")
        self.assertTrue(text.startswith("Review by @kyle.r1 (same-machine): changes requested."))
        self.assertTrue(text.endswith("\n\n[Bugs, Important] x"))
        self.assertIn("stays In Review for a person to merge", asdlc.review_comment("kyle.r1", "", asdlc.ReviewVerdict.CLEAN, "No findings."))

    def test_the_cap_counts_workers_and_reviews(self) -> None:
        items = (
            task("TASK-1", status="In Review", assignees=("@ann.w1",), reviewer="kyle.r1", path="a"),
            task("TASK-2", status="In Progress", assignees=("@kyle.w1",), path="b"),
        )
        self.assertEqual(asdlc.busy(items, "kyle"), 2)
        report = asdlc.mine_report(items + (task("TASK-3", status="In Progress", assignees=("@kyle.w2",), labels=("size-2", "changes-requested")),),
                                   "kyle", asdlc.Prefs("kyle"))
        self.assertEqual((report["active"], report["reviewing"]), (2, 1))
        self.assertEqual([(r["id"], r["reviewer"]) for r in report["reviews"]], [("TASK-1", "kyle.r1")])
        self.assertEqual([r["id"] for r in report["changes_requested"]], ["TASK-3"])
        self.assertEqual(sorted(r["id"] for r in report["tasks"]), ["TASK-2", "TASK-3"])

    def test_board_setting_is_explicit_then_environment_then_configuration(self) -> None:
        self.assertEqual(asdlc.board_setting("/a", {"ASDLC_BOARD": "/b"}, "/c\n"), ("/a", "--board"))
        self.assertEqual(asdlc.board_setting(None, {"ASDLC_BOARD": "/b"}, "/c\n"), ("/b", "ASDLC_BOARD"))
        self.assertEqual(asdlc.board_setting("", {"ASDLC_BOARD": " "}, "/c\n"), ("/c", "git config asdlc.board"))
        self.assertIsNone(asdlc.board_setting(None, {}, ""))

    def test_review_route(self) -> None:
        self.assertEqual((asdlc.REVIEW.model, asdlc.REVIEW.effort), ("sonnet", "medium"))


class CheckNoteTest(unittest.TestCase):
    NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)

    def test_records_command_code_and_the_tail(self) -> None:
        output = "".join(f"line {n}\n" for n in range(1, 51))
        note = asdlc.check_note(["./scripts/check", "--all"], 1, output, self.NOW, tail=3)
        self.assertTrue(note.startswith("Check FAILED: `./scripts/check --all` exited 1 at 2026-10-22T15:00:00+00:00, last 3 of 50 lines:"))
        self.assertIn("line 48\nline 49\nline 50\n```", note)
        self.assertNotIn("line 47", note)
        self.assertIn("Check passed", asdlc.check_note(["true"], 0, "", self.NOW))

    def test_output_with_a_fence_gets_a_longer_one(self) -> None:
        note = asdlc.check_note(["cat"], 0, "```python\nx\n```\n", self.NOW)
        self.assertIn("````text\n```python", note)


class DraftParentTest(unittest.TestCase):
    def test_a_draft_parent_is_taken_out_for_asdlc_to_record(self) -> None:
        self.assertEqual(asdlc.draft_parent(["task", "create", "A", "--draft", "-p", "draft-2", "-l", "size-1"]),
                         (("task", "create", "A", "--draft", "-l", "size-1"), "DRAFT-2"))
        self.assertEqual(asdlc.draft_parent(["draft", "create", "A", "--parent=DRAFT-3"]), (("draft", "create", "A"), "DRAFT-3"))

    def test_anything_else_is_left_to_backlog(self) -> None:
        self.assertIsNone(asdlc.draft_parent(["task", "create", "A", "--draft", "-p", "TASK-2"]))
        self.assertIsNone(asdlc.draft_parent(["task", "create", "A", "-p", "DRAFT-2"]))
        self.assertIsNone(asdlc.draft_parent(["task", "edit", "TASK-1", "-p", "DRAFT-2"]))


class EventLogTest(unittest.TestCase):
    def test_one_attempt_is_one_json_line(self) -> None:
        line = asdlc.event_line(datetime(2026, 10, 22, 15, 0, tzinfo=UTC), "next", "kyle.w1", "TASK-3", asdlc.Attempt.LOST, "Another agent claimed TASK-3 first.")
        self.assertEqual(json.loads(line), {"time": "2026-10-22T15:00:00+00:00", "command": "next", "engineer": "kyle", "worker": "kyle.w1",
                                            "task": "TASK-3", "outcome": "lost", "reason": "Another agent claimed TASK-3 first."})

    def test_unreadable_lines_are_skipped(self) -> None:
        text = '{"time": "2026-10-22T15:00:00+00:00", "outcome": "claimed"}\nnot json\n[1]\n{"outcome": "lost"}\n'
        self.assertEqual([e["outcome"] for e in asdlc.parse_events(text)], ["claimed"])


COMMANDS_TOML = ('[build]\nrun = "npm ci && npm run build"\nverified = 2026-10-20\n\n[test]\nrun = "npm test"\ncwd = "web"\nverified = 2026-10-20\n\n'
                 '[lint]\nrun = "npm run lint -- src/*.ts | tee lint.txt"\nverified = 2026-10-20\n\n[typecheck]\nrun = "npx tsc --noEmit"\nverified = 2026-10-20\n')
ASDLC_ROOT = Path("/home/kyle/src/asdlc")
RULES = asdlc.permission_rules((("acme-api", Path("/home/kyle/api")),), Path("/home/kyle/tasks"), {"acme-api": COMMANDS_TOML}, (ASDLC_ROOT,))


def facts(**changes: object) -> object:
    """A machine where every check passes; each test breaks one thing."""
    board = Path("/home/kyle/tasks")
    healthy = asdlc.Facts(
        git=asdlc.Tool("/usr/bin/git", "git version 2.43.0"), uv=asdlc.Tool("/usr/bin/uv", "uv 0.9.0"), python=(3, 15),
        backlog=asdlc.Tool("/usr/bin/backlog", "1.55.2"), asdlc=asdlc.Tool("/usr/bin/asdlc"), asdlc_plugin=asdlc.Tool("/usr/bin/asdlc-plugin"),
        gh=asdlc.Tool("/usr/bin/gh", "gh version 2.80.0"), gh_signed_in=True, claude=asdlc.Tool("/usr/bin/claude"), npx=asdlc.Tool(None),
        engineer="kyle", board=board, devs="name: kyle\nreview: true\n", branch="main", origin="git@github.com:acme/tasks.git",
        settings='stale_after = "2h"\nreview_fallback_after = "30m"\n',
        repos=(asdlc.RepoFacts("acme-api", Path("/home/kyle/api"), board, True, "acme-api", str(board)),),
        marketplace="tasks",
        plugins=asdlc.PluginFacts(
            marketplaces=(frozendict({"name": "tasks", "autoUpdate": True}),),
            installed=(frozendict({"id": "team@tasks", "enabled": True}), frozendict({"id": "asdlc@asdlc", "enabled": True}),
                       frozendict({"id": "authoring-kit@synced", "enabled": True, "version": "0.7.0"})),
            kit_files=frozenset(asdlc.AUTHORING_KIT)),
        published=(asdlc.PublishedCheck("acme-api", 0, "acme-api: clean"),),
        home=Path("/home/kyle"),
        plugin_commands=(("acme-api", COMMANDS_TOML),), plugin_roots=(ASDLC_ROOT,),
        claude_settings=(("/home/kyle/tasks/.claude/settings.local.json", json.dumps({"permissions": RULES.as_settings()})),),
        mcp_configs=(("/home/kyle/.claude.json", json.dumps({"mcpServers": {"github": {"command": "gh-mcp"}}})),),
    )
    return asdlc.replace(healthy, **changes)


def settings(**permissions: object) -> tuple[tuple[str, str], ...]:
    return (("/home/kyle/tasks/.claude/settings.local.json", json.dumps({"permissions": permissions})),)


class DoctorTest(unittest.TestCase):
    def levels(self, found: object) -> dict[str, list[str]]:
        by_level: dict[str, list[str]] = {}
        for finding in asdlc.diagnose(found):
            by_level.setdefault(str(finding.level), []).append(finding.area)
        return by_level

    def only(self, level: str, found: object) -> list[object]:
        return [f for f in asdlc.diagnose(found) if str(f.level) == level]

    def test_a_healthy_machine_passes_everything(self) -> None:
        self.assertEqual(set(self.levels(facts())), {"pass"})
        lines = asdlc.doctor_lines(asdlc.diagnose(facts()))
        self.assertEqual(lines[0], "pass  git: git version 2.43.0")
        self.assertRegex(lines[-1], r"^\d+ passed, 0 warning\(s\), 0 failed$")

    def test_tools(self) -> None:
        cases = {
            "git": (facts(git=asdlc.Tool(None)), "fail", "not installed"),
            "uv": (facts(uv=asdlc.Tool(None)), "fail", "docs.astral.sh/uv"),
            "backlog": (facts(backlog=asdlc.Tool("/b", "1.54.0")), "fail", "older than 1.55.1"),
            "asdlc-plugin": (facts(asdlc_plugin=asdlc.Tool(None)), "fail", "not on PATH"),
            "gh": (facts(gh_signed_in=False), "warn", "gh auth setup-git"),
            "claude": (facts(claude=asdlc.Tool(None)), "warn", "neither claude nor npx"),
        }
        for area, (found, level, says) in cases.items():
            with self.subTest(area=area):
                (finding,) = [f for f in self.only(level, found) if f.area == area]
                self.assertIn(says, finding.message)
        self.assertEqual(set(self.levels(facts(gh=asdlc.Tool(None)))), {"pass", "warn"}, "gh is a warning only")
        self.assertEqual(set(self.levels(facts(claude=asdlc.Tool(None), npx=asdlc.Tool("/usr/bin/npx")))), {"pass"})

    def test_identity_and_preferences(self) -> None:
        cases = {
            "unset": (facts(engineer=""), "git config --global asdlc.engineer"),
            "not a name": (facts(engineer="kyle.w1"), "not an engineer's name"),
            "no devs file": (facts(devs=None), "devs/kyle.yaml is not in the tasks repository"),
            "malformed": (facts(devs="name: kyle\nreview: maybe\n"), "review is true or false"),
            "review unset": (facts(devs="name: kyle\nworkers: 2\n"), "add review: true (or false)"),
        }
        for case, (found, says) in cases.items():
            with self.subTest(case=case):
                self.assertIn(says, " ".join(f.message for f in self.only("fail", found)))

    def test_the_board(self) -> None:
        cases = {
            "missing": (facts(board=None, board_error="no board: pass --board <path>"), "no board"),
            "dirty": (facts(dirty=" M asdlc.toml"), "uncommitted changes"),
            "off main": (facts(branch="other"), "switch main"),
            "no origin": (facts(origin=""), "no origin remote"),
            "unreachable": (facts(origin_error="fatal: could not read Username"), "can't be reached without a prompt"),
        }
        for case, (found, says) in cases.items():
            with self.subTest(case=case):
                self.assertIn(says, " ".join(f.message for f in self.only("fail", found) if f.area == "board"))

    def test_settings(self) -> None:
        self.assertIn("not valid TOML", self.only("fail", facts(settings="review_fallback_after = \n"))[0].message)
        self.assertTrue([f for f in asdlc.diagnose(facts(settings='review_fallback_after = "0m"\n')) if f.area == "asdlc.toml" and "review_fallback_after 0m" in f.message])
        self.assertIn("defaults apply", self.only("warn", facts(settings=None))[0].message)

    def test_registered_repositories(self) -> None:
        board = Path("/home/kyle/tasks")
        repo = lambda **c: facts(repos=(asdlc.replace(asdlc.RepoFacts("acme-api", Path("/home/kyle/api"), board, True, "acme-api", str(board)), **c),))  # noqa: E731
        cases = {
            "gone": (repo(exists=False), "fail", "is gone"),
            "no origin": (repo(remote_slug=None), "fail", "no origin remote"),
            "renamed": (repo(remote_slug="acme-api-v2"), "fail", "origin is acme-api-v2 now"),
            "no board": (repo(board=""), "fail", "asdlc.board is not set"),
            "another board": (repo(board="/elsewhere"), "warn", "registered for /home/kyle/tasks"),
        }
        for case, (found, level, says) in cases.items():
            with self.subTest(case=case):
                self.assertIn(says, " ".join(f.message for f in self.only(level, found) if f.area == "repository acme-api"))
        self.assertIn("run asdlc register", self.only("warn", facts(repos=()))[0].message)
        self.assertEqual(self.only("fail", facts(registry_error="the registry is not valid TOML"))[0].area, "repositories")

    def test_plugins(self) -> None:
        plugins = facts().plugins
        cases = {
            "cannot check": (facts(plugins=asdlc.PluginFacts(error="claude is not on PATH")), "warn", "plugins", "/plugin"),
            "no marketplace file": (facts(marketplace=None), "fail", "marketplace", "asdlc init-board"),
            "not added": (facts(plugins=asdlc.replace(plugins, marketplaces=())), "fail", "marketplace", "claude plugin marketplace add git@github.com:acme/tasks.git"),
            "auto-update off": (facts(plugins=asdlc.replace(plugins, marketplaces=(frozendict({"name": "tasks"}),))), "warn", "auto-update", "gh auth setup-git"),
            "team missing": (facts(plugins=asdlc.replace(plugins, installed=plugins.installed[1:])), "fail", "team plugin", "claude plugin install team@tasks"),
            "asdlc missing": (facts(plugins=asdlc.replace(plugins, installed=(plugins.installed[0], plugins.installed[2]))), "warn", "asdlc plugin", "--plugin-dir"),
            "kit missing": (facts(plugins=asdlc.replace(plugins, installed=plugins.installed[:2])), "warn", "authoring kit", "unaudited"),
            "kit short": (facts(plugins=asdlc.replace(plugins, kit_files=frozenset(asdlc.AUTHORING_KIT[:3]))), "warn", "authoring kit", "agents/authoring-auditor.md"),
        }
        for case, (found, level, area, says) in cases.items():
            with self.subTest(case=case):
                self.assertIn(says, " ".join(f.message for f in self.only(level, found) if f.area == area))
        disabled = asdlc.replace(plugins, installed=(frozendict({"id": "team@tasks", "enabled": False}), *plugins.installed[1:]))
        self.assertEqual([f.area for f in self.only("fail", facts(plugins=disabled))], ["team plugin"])
        self.assertIn("auto-update is off for tasks, the default for a marketplace you add yourself",
                      self.only("warn", facts(plugins=asdlc.replace(plugins, marketplaces=(frozendict({"name": "tasks"}),))))[0].message)

    def test_permissions_for_background_workers(self) -> None:
        """I10: no permission prompts during normal work, so doctor checks the rules asdlc permissions writes."""
        self.assertEqual([f.level for f in asdlc.diagnose(facts()) if f.area == "permissions"], [asdlc.Level.PASS])
        broad = ["Bash(asdlc:*)", "Bash(asdlc-plugin:*)", "Bash(git:*)", "Bash(gh pr *)", "Bash(uv run:*)", "Bash(backlog *)", "Bash(npm *)", "Bash(npx *)",
                 "Bash(/home/kyle/src/asdlc/scripts/asdlc *)", "Bash(/home/kyle/src/asdlc/scripts/asdlc-plugin *)", "Edit(//home/kyle/*.worktrees/**)"]
        self.assertNotIn("warn", self.levels(facts(claude_settings=settings(allow=broad, deny=list(asdlc.GIT_DENY), additionalDirectories=["~"]))))
        (undenied,) = [f for f in self.only("warn", facts(claude_settings=settings(allow=broad, additionalDirectories=["~"]))) if f.area == "permissions"]
        self.assertIn("Bash(git -C * -c*)", undenied.message, "broad allow rules without the git deny rules let -c through")
        (missing,) = [f for f in self.only("warn", facts(claude_settings=settings(allow=["Bash(asdlc *)", "Bash(git push *)"]))) if f.area == "permissions"]
        for named in ("asdlc permissions --write", "Bash(asdlc-plugin *)", "Bash(git -C /home/kyle/api.worktrees/* push *)", "Bash(gh pr create *)",
                      "Bash(npm test)", "Edit(//home/kyle/api.worktrees/**)", "/home/kyle/tasks.worktrees"):
            with self.subTest(named=named):
                self.assertIn(named, missing.message)
        self.assertNotIn("Bash(asdlc *),", missing.message)
        broken = self.only("warn", facts(claude_settings=(("/home/kyle/tasks/.claude/settings.local.json", "{not json"),)))
        self.assertTrue(any("not valid JSON" in f.message for f in broken))

    def test_a_backlog_mcp_server_is_reported(self) -> None:
        """I8: asdlc works through the backlog CLI only, so doctor warns when Backlog.md's MCP server is configured."""
        configured = facts(mcp_configs=(("/home/kyle/.claude.json", json.dumps({"projects": {"/home/kyle/tasks": {"mcpServers": {
            "backlog": {"command": "backlog", "args": ["mcp", "start"]}}}}})), ("/home/kyle/tasks/.mcp.json", "{}")))
        (found,) = [f for f in self.only("warn", configured) if f.area == "backlog mcp"]
        self.assertIn("CLI only", found.message)
        self.assertIn("claude mcp remove backlog", found.message)


    def test_leftovers_say_how_to_remove_them(self) -> None:
        found = facts(leftovers=(Path("/home/kyle/tasks.worktrees/plugin-acme-api"), Path("/home/kyle/api.worktrees/asdlc-verify"),
                                 Path("/home/kyle/api.worktrees/review-task-7-kyle.r1")))
        messages = [f.message for f in self.only("warn", found)]
        self.assertIn("onboarding of acme-api that was never published", messages[0])
        self.assertIn("git -C /home/kyle/tasks worktree remove --force /home/kyle/tasks.worktrees/plugin-acme-api", messages[0])
        self.assertIn("git -C /home/kyle/api worktree remove --force /home/kyle/api.worktrees/asdlc-verify", messages[1])
        self.assertIn("reviewer's worktree", messages[2])

    def test_published_plugins_must_pass_their_check(self) -> None:
        found = facts(published=(asdlc.PublishedCheck("acme-api", 1, "plugins/acme-api/commands.toml: [lint] is not verified"),))
        (finding,) = self.only("fail", found)
        self.assertEqual(finding.area, "plugin acme-api")
        self.assertIn("[lint] is not verified", finding.message)
        self.assertEqual(self.only("pass", facts(published=()))[-1].message, "none published yet")


T0 = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
# The structured record every review-done now carries, for a clean review and for one that asks for changes.
CLEAN = ("--findings", "important=0,nit=0", "--plan-matched", "yes")
CHANGES = ("--findings", "important=1", "--plan-matched", "yes")


class PermissionRulesTest(unittest.TestCase):
    """I10, and the second review's Important 3: the narrow allow rules normal work needs, and merging them in."""

    def test_deny_rules_for_git_that_runs_a_program(self) -> None:
        """The orchestrator's review of #26: deny beats allow, so git with -c, grep -O, --upload-pack and the like is refused even
        where an allow rule's `*` would match it."""
        for rule in ("Bash(git -c*)", "Bash(git -C * -c*)", "Bash(git *grep* -O*)", "Bash(git * --upload-pack*)", "Bash(git * --ext-diff*)",
                     "Bash(git -C * config *)", "Bash(env GIT_*)", "Bash(export GIT_*)"):
            with self.subTest(rule=rule):
                self.assertIn(rule, RULES.deny)
        self.assertEqual(RULES.as_settings()["deny"], list(RULES.deny))
        merged, added = asdlc.merge_permissions({"permissions": {"deny": ["Bash(rm *)"]}}, RULES)
        self.assertEqual(merged["permissions"]["deny"], ["Bash(rm *)", *RULES.deny])
        self.assertTrue(set(RULES.deny) <= set(added))
        full = json.dumps({"permissions": RULES.as_settings()})
        self.assertEqual(asdlc.missing_permissions([("local", full)], RULES, Path("/home/kyle")), ([], []))
        without = json.dumps({"permissions": {**RULES.as_settings(), "deny": [], "defaultMode": "bypassPermissions"}})
        self.assertEqual(asdlc.missing_permissions([("local", without)], RULES, Path("/home/kyle"))[0], list(RULES.deny),
                         "deny rules are needed in every mode")

    def test_the_read_only_git_workers_and_reviewers_reach_for(self) -> None:
        """The first eval run: `git -C <worktree> ls-files` had no rule, so a background planner couldn't list its files."""
        for sub in ("ls-files", "grep", "blame", "cat-file", "ls-tree", "merge-base", "rev-list", "describe", "show-ref", "remote get-url"):
            for folder in ("/home/kyle/api.worktrees/*", "/home/kyle/api"):
                for rule in (f"Bash(git -C {folder} {sub} *)", f"Bash(git -C {folder} {sub})"):
                    with self.subTest(rule=rule):
                        self.assertIn(rule, RULES.allow)
        for write in ("commit", "push", "reset", "rm", "remote add"):
            with self.subTest(write=write):
                self.assertNotIn(f"Bash(git -C /home/kyle/api {write} *)", RULES.allow)

    def test_the_rules(self) -> None:
        for rule in ("Bash(asdlc *)", "Bash(asdlc-plugin *)", "Bash(/home/kyle/src/asdlc/scripts/asdlc *)",
                     "Bash(uv run --script /home/kyle/src/asdlc/scripts/asdlc *)", "Bash(backlog task list *)", "Bash(backlog task view *)",
                     "Bash(git -C /home/kyle/api.worktrees/* fetch *)", "Bash(git -C /home/kyle/api.worktrees/* push *)",
                     "Bash(git -C /home/kyle/api.worktrees/* checkout -b *)", "Bash(git -C /home/kyle/api fetch *)", "Bash(git -C /home/kyle/api worktree *)",
                     "Bash(gh pr create *)", "Bash(gh pr view *)", "Bash(gh pr comment *)", "Bash(npm test)", "Bash(npx tsc --noEmit)",
                     "Edit(//home/kyle/api.worktrees/**)", "Edit(//home/kyle/tasks.worktrees/**)"):
            with self.subTest(rule=rule):
                self.assertIn(rule, RULES.allow)
        for broad in ("Bash(git *)", "Bash(uv run *)", "Bash(npm ci && npm run build)", "Bash(npm ci)"):
            with self.subTest(broad=broad):
                self.assertNotIn(broad, RULES.allow)
        self.assertFalse([r for r in RULES.allow if "|" in r or "&&" in r or "lint" in r])
        self.assertEqual(len(RULES.allow), len(set(RULES.allow)))
        self.assertEqual(RULES.directories, ("/home/kyle/api.worktrees", "/home/kyle/tasks.worktrees"))
        self.assertEqual([(slug, name) for slug, name, _, _ in RULES.skipped], [("acme-api", "build"), ("acme-api", "lint")])
        self.assertIn("&&", RULES.skipped[0][3])
        self.assertIn("*", RULES.skipped[1][3])

    def test_merging_keeps_everything_and_adds_only_what_is_missing(self) -> None:
        existing = {"model": "opus", "permissions": {"allow": ["Read(~/notes/**)", "Bash(asdlc *)"], "deny": ["Bash(rm *)"],
                                                     "additionalDirectories": ["/home/kyle/api.worktrees"]}}
        merged, added = asdlc.merge_permissions(existing, RULES)
        self.assertEqual((merged["model"], merged["permissions"]["deny"]), ("opus", ["Bash(rm *)", *RULES.deny]), "the person's deny rules kept, first")
        self.assertEqual(merged["permissions"]["allow"][:2], ["Read(~/notes/**)", "Bash(asdlc *)"])
        self.assertEqual(set(merged["permissions"]["allow"]), {"Read(~/notes/**)", *RULES.allow})
        self.assertEqual(merged["permissions"]["additionalDirectories"], ["/home/kyle/api.worktrees", "/home/kyle/tasks.worktrees"])
        self.assertNotIn("Bash(asdlc *)", added)
        self.assertIn("/home/kyle/tasks.worktrees", added)
        self.assertEqual(asdlc.merge_permissions(merged, RULES)[1], [])
        self.assertEqual(existing["permissions"]["allow"], ["Read(~/notes/**)", "Bash(asdlc *)"], "the input is not changed")

    def test_settings_of_the_wrong_shape_are_refused_not_crashed_on(self) -> None:
        for settings, says in (({"permissions": None}, "permissions"), ({"permissions": {"allow": "Bash(ls)"}}, "allow"),
                               ({"permissions": {"additionalDirectories": {"a": 1}}}, "additionalDirectories"), ([], "object")):
            with self.subTest(settings=settings):
                with self.assertRaisesRegex(asdlc.AsdlcError, says):
                    asdlc.merge_permissions(settings, RULES)


def minute(m: float) -> datetime:
    return T0 + timedelta(minutes=m)


def check(passed: bool, m: float, commit: str, dirty: bool = False, since: tuple[int, int] | None = None) -> object:
    return asdlc.Check(passed, 0 if passed else 1, minute(m).isoformat(), commit, dirty, since)


def seen(folder: str, task_id: str, *, substance: str = "", checks: tuple = (), noted: bool = False, **fields: object) -> object:
    path = f"backlog/{folder}/{task_id.lower()} - x.md"
    return asdlc.Change(path, asdlc.Item(task(task_id, path=path, **fields), substance, checks, noted))


def gone(folder: str, task_id: str) -> object:
    return asdlc.Change(f"backlog/{folder}/{task_id.lower()} - x.md", None)


def doc(doc_id: str, title: str = "Spec: Rate limit logins", kind: str = "specification") -> object:
    return asdlc.Change(f"backlog/docs/{doc_id} - x.md", asdlc.DocItem(doc_id, title, kind))


def commit(m: float, *changes: object) -> object:
    return asdlc.Commit(f"c{m}", minute(m), tuple(changes))


INTENT = {"type": "intent", "labels": (), "project": "", "status": "Draft", "title": "Rate limit logins"}
T2 = {"parent": "TASK-1", "labels": ("size-2",), "project": "app"}
T2_CHECKS = (check(True, 21, "aaa"), check(True, 30, "bbb"))
T3 = {"parent": "TASK-1", "labels": ("size-1",), "project": "app", "assignees": ("@ann.w2",)}
T3_CHECKS = (check(True, 24, "c1"), check(False, 25, "c2"))

# One intent, accepted with two children, built, reviewed and partly merged; another intent archived; a bug against
# a Done task. Each commit is the state each file was left in, as the board's history holds it.
HISTORY = (
    commit(0, seen("drafts", "DRAFT-1", substance="a", intent_started=(T0 - timedelta(minutes=10)).isoformat(), **INTENT)),
    commit(2, seen("drafts", "DRAFT-2", substance="z", **INTENT | {"title": "Doomed"})),
    commit(5, doc("doc-1"), seen("drafts", "DRAFT-1", substance="a", documentation=("doc-1",), **INTENT)),
    commit(6, seen("drafts", "DRAFT-1", substance="b", documentation=("doc-1",), **INTENT)),
    commit(8, seen("drafts", "DRAFT-3", status="Draft", **T2 | {"parent": "DRAFT-1"}),
           seen("drafts", "DRAFT-4", status="Draft", **T3 | {"parent": "DRAFT-1", "assignees": ()})),
    commit(10, gone("drafts", "DRAFT-1"), gone("drafts", "DRAFT-3"), gone("drafts", "DRAFT-4"),
           seen("tasks", "TASK-1", substance="b", documentation=("doc-1",), accepted_from="DRAFT-1", **INTENT | {"status": "To Do"}),
           seen("tasks", "TASK-2", accepted_from="DRAFT-3", **T2),
           seen("tasks", "TASK-3", accepted_from="DRAFT-4", **T3 | {"assignees": ()})),
    commit(11, gone("drafts", "DRAFT-2"), seen("archive/drafts", "DRAFT-2", **INTENT | {"title": "Doomed"})),
    commit(12, seen("tasks", "TASK-2", status="In Progress", assignees=("@ann.w1",), **T2)),
    commit(13, seen("tasks", "TASK-3", status="In Progress", **T3)),
    commit(15, seen("tasks", "TASK-2", status="In Progress", assignees=("@ann.w1",), plan_hash="p1", **T2)),
    commit(16, doc("doc-1")),
    commit(20, seen("tasks", "TASK-2", status="In Progress", assignees=("@ann.w1",), plan_hash="p1", plan_approved_by="ann", approved_hash="p1", **T2)),
    commit(21, seen("tasks", "TASK-2", status="In Progress", assignees=("@ann.w1",), plan_hash="p1", plan_approved_by="ann", approved_hash="p1",
                    checks=T2_CHECKS[:1], **T2)),
    commit(25, seen("tasks", "TASK-3", status="In Review", checks=T3_CHECKS, noted=True, **T3)),
    commit(30, seen("tasks", "TASK-2", status="In Review", assignees=("@ann.w1",), plan_hash="p1", plan_approved_by="ann", approved_hash="p1",
                    checks=T2_CHECKS, **T2)),
    commit(35, seen("tasks", "TASK-2", status="In Review", assignees=("@ann.w1",), reviewer="kyle.r1", review_kind="cross-machine", checks=T2_CHECKS, **T2)),
    commit(40, seen("tasks", "TASK-2", status="In Progress", assignees=("@ann.w1",), review_kind="cross-machine", checks=T2_CHECKS,
                    review_findings="important=1,nit=2", review_policies=("testing",), plan_matched="yes", **T2 | {"labels": ("size-2", "changes-requested")})),
    commit(50, seen("tasks", "TASK-2", status="In Review", assignees=("@ann.w1",), review_kind="cross-machine",
                    checks=(*T2_CHECKS, check(True, 50, "ccc", since=(2, 2))), **T2)),
    commit(55, seen("tasks", "TASK-2", status="In Review", assignees=("@ann.w1",), reviewer="kyle.r1", review_kind="cross-machine",
                    checks=(*T2_CHECKS, check(True, 50, "ccc", since=(2, 2))), **T2)),
    commit(60, seen("tasks", "TASK-2", status="In Review", assignees=("@ann.w1",), review_kind="cross-machine", review_findings="important=0,nit=0",
                    plan_matched="yes", checks=(*T2_CHECKS, check(True, 50, "ccc", since=(2, 2))), **T2 | {"labels": ("size-2", "review-passed")})),
    commit(70, seen("tasks", "TASK-2", status="Done", assignees=("@ann.w1",), checks=(*T2_CHECKS, check(True, 50, "ccc", since=(2, 2))),
                    references=("task-2-x", "https://github.com/acme/app/pull/7"), **T2 | {"labels": ("size-2", "review-passed")})),
    commit(80, seen("tasks", "TASK-4", type="bug", references=("TASK-2",), labels=("size-1",))),
    commit(90, seen("tasks", "TASK-3", status="In Review", reviewer="ann.r1", review_kind="same-machine", checks=T3_CHECKS, noted=True, **T3)),
    commit(95, seen("tasks", "TASK-3", status="In Review", review_kind="same-machine", checks=T3_CHECKS, noted=True, review_findings="important=0,nit=1",
                    review_policies=("testing", "naming"), plan_matched="no", **T3 | {"labels": ("size-1", "review-passed")})),
)
LEDGER = asdlc.replay(HISTORY)
ALL = asdlc.Window(None, minute(100))


def metrics(stage: dict[str, object]) -> dict[str, dict[str, object]]:
    return stage["metrics"]


class CheckNotesTest(unittest.TestCase):
    """What stats reads back from record-check's notes."""

    def test_a_check_note_reads_back(self) -> None:
        output = "Check passed: `fake` exited 0 at 2026-10-22T15:00:00+00:00:\n```\nstill output\n"
        where = asdlc.Where("/w/app.worktrees/task-1", "task-1-x", "0123456789abcdef", True)
        notes = "\n\n".join([
            asdlc.check_note(["./check"], 0, "fine\n", T0, where=where),
            "A worker's own note.",
            asdlc.check_note(["./check"], 1, output, T0 + timedelta(minutes=5), since_review=(1, 3)),
            asdlc.check_note(["./check"], 0, "", T0 + timedelta(minutes=9), since_review=(2, 2)),
            asdlc.check_note(["./check"], 0, "", T0 + timedelta(minutes=9), since_review=(0, 0)),
        ])
        found = asdlc.parse_checks(f"---\nid: TASK-1\n---\n<!-- SECTION:NOTES:BEGIN -->\n{notes}\n<!-- SECTION:NOTES:END -->\n")
        self.assertEqual([(c.passed, c.code, c.commit, c.dirty, c.since_review) for c in found],
                         [(True, 0, "0123456789ab", True, None), (False, 1, "", False, (1, 3)), (True, 0, "", False, (2, 2)), (True, 0, "", False, (0, 0))])
        self.assertEqual(found[1].at, "2026-10-22T09:05:00+00:00")
        self.assertIn("Commits since the review: 3, 2 without the Asdlc-Worker trailer.", notes)

    def test_worker_commits_count_the_trailer(self) -> None:
        log = "Fix it\n\nAsdlc-Worker: ann.w1\n\x01Tweak by hand\n\x01Again\n\nAsdlc-Worker: ann.w1\nOther: x\n\x01"
        self.assertEqual(asdlc.worker_commits(log), (2, 3))
        self.assertEqual(asdlc.worker_commits(""), (0, 0))

    def test_substance_ignores_ticked_boxes_and_comments(self) -> None:
        body = "<!-- SECTION:DESCRIPTION:BEGIN -->\nWhy\n<!-- SECTION:DESCRIPTION:END -->\n<!-- AC:BEGIN -->\n- [ ] #1 works\n<!-- AC:END -->\n"
        self.assertEqual(asdlc.substance("T", body), asdlc.substance("T", body.replace("[ ]", "[x]") + "\n## Comments\nhi\n"))
        self.assertNotEqual(asdlc.substance("T", body), asdlc.substance("T", body.replace("Why", "Why not")))


class ReviewRecordTest(unittest.TestCase):
    def test_findings_parse_and_fit_the_verdict(self) -> None:
        self.assertEqual(asdlc.parse_findings("important=1,nit=2"), (1, 2))
        self.assertEqual(asdlc.parse_findings("nit=3"), (0, 3))
        self.assertEqual(asdlc.parse_findings(" Important = 2 "), (2, 0))
        for bad in ("blocker=1", "important=x", "important"):
            with self.subTest(bad=bad), self.assertRaises(asdlc.AsdlcError):
                asdlc.parse_findings(bad)
        none = asdlc.ReviewRecord(0, 1, (), True)
        some = asdlc.ReviewRecord(1, 0, ("testing",), False)
        self.assertIn("at least one Important", asdlc.review_record_refusal(asdlc.ReviewVerdict.CHANGES, none))
        self.assertIn("the verdict is changes", asdlc.review_record_refusal(asdlc.ReviewVerdict.CLEAN, some))
        self.assertIsNone(asdlc.review_record_refusal(asdlc.ReviewVerdict.CLEAN, none))
        text = asdlc.review_comment("kyle.r1", "cross-machine", asdlc.ReviewVerdict.CHANGES, "[Bugs, Important] x", some)
        self.assertIn("Findings: 1 Important, 0 nit. Cites: testing. The diff does not match the plan.", text)


class ReplayTest(unittest.TestCase):
    def test_lives_drafts_and_documents(self) -> None:
        lives = LEDGER.lives
        self.assertEqual(lives["DRAFT-1#1"].end, asdlc.End(5, minute(10), "accepted", "TASK-1"))
        self.assertEqual(lives["DRAFT-2#1"].end.how, "archived")
        self.assertEqual(LEDGER.docs["doc-1"].commits, ((2, minute(5)), (10, minute(16))))
        self.assertEqual([i.id for i in asdlc.intents(LEDGER)], ["TASK-1", "DRAFT-2"])
        self.assertEqual(sorted(life.id for life in asdlc.family(LEDGER, asdlc.intents(LEDGER)[0])), ["TASK-2", "TASK-3"])
        self.assertEqual(LEDGER.stories["TASK-4"].first_when, minute(80))
        self.assertEqual(LEDGER.stories["TASK-2"].first_when, minute(8), "a task begins when its draft was written")

    def test_a_reused_draft_id_is_a_new_life(self) -> None:
        again = asdlc.replay((*HISTORY, commit(99, seen("drafts", "DRAFT-1", **INTENT | {"title": "Another"}))))
        self.assertEqual(again.lives["DRAFT-1#2"].seen[0].item.task.title, "Another")
        self.assertEqual(again.lives["DRAFT-1#1"].end.how, "accepted")

    def test_a_task_story(self) -> None:
        story = LEDGER.stories["TASK-2"]
        self.assertEqual(story.claims, (minute(12),))
        self.assertEqual([w for w, _, _ in story.entered_review], [minute(30), minute(50)])
        self.assertEqual([(v.clean, v.important, v.nit, v.policies, v.plan_matched) for v in story.verdicts],
                         [(False, 1, 2, ("testing",), True), (True, 0, 0, (), True)])
        self.assertEqual((story.plan_written, story.approvals, story.done), (minute(15), (minute(20),), minute(70)))
        self.assertEqual(story.held, (("ann", minute(12), minute(30)), ("ann", minute(40), minute(50))))
        self.assertEqual(story.pull, "https://github.com/acme/app/pull/7")


class StageTest(unittest.TestCase):
    """Each stage's numbers over the fixed history above."""

    def test_plan(self) -> None:
        found = metrics(asdlc.plan_stage(LEDGER, ALL))
        self.assertEqual((found["conversation_to_intent"]["count"], found["conversation_to_intent"]["median"]), (1, 600.0))
        self.assertEqual(found["conversation_to_intent"]["unrecorded"], ["DRAFT-2"])
        self.assertEqual((found["survival_rate"]["count"], found["survival_rate"]["of"], found["survival_rate"]["archived"]), (1, 2, 1))
        self.assertEqual(found["post_spec_churn"]["by_intent"], {"TASK-1": 1})
        self.assertEqual(found["accept_wait"]["median"], 600.0)
        self.assertEqual(found["conversation_to_intent"]["playbook"], "Conversation to committed intent (leading)")

    def test_design(self) -> None:
        found = metrics(asdlc.design_stage(LEDGER, ALL))
        self.assertEqual((found["intent_to_spec"]["count"], found["intent_to_spec"]["median"]), (1, 300.0))
        self.assertEqual(found["spec_rework"]["by_intent"], {"TASK-1": 1})

    def test_build(self) -> None:
        found = metrics(asdlc.build_stage(LEDGER, {}, ALL))
        self.assertEqual((found["claim_to_review"]["median"], found["claim_to_review"]["p90"]), (720.0, 1080.0))
        self.assertEqual((found["first_pass_merge"]["count"], found["first_pass_merge"]["of"]), (0, 1))
        self.assertEqual((found["approval_to_merge"]["median"], found["approval_to_merge"]["sources"]), (3000.0, {"Done commit": 1}))
        self.assertEqual(found["rework_cycles"]["by_task"], {"TASK-2": 1, "TASK-3": 0})
        self.assertEqual((found["plan_matched"]["count"], found["plan_matched"]["of"]), (2, 3))
        self.assertEqual(found["approval_wait"]["median"], 300.0)
        self.assertEqual(found["size1_skipped_approval"]["tasks"], [{"id": "TASK-3", "noted": True}])
        self.assertEqual(found["parallel_claims"]["by_engineer"], {"ann": {"peak": 2, "median": 1}})
        self.assertEqual(found["throughput"]["by_engineer"]["ann"], {"weeks": {"2026-W43": 1}, "reviewed": 2, "round_trips": 1, "rework_rate": 0.5})
        merged = metrics(asdlc.build_stage(LEDGER, {"TASK-2": minute(65)}, ALL))["approval_to_merge"]
        self.assertEqual((merged["median"], merged["sources"]), (2700.0, {"gh": 1}))

    def test_test(self) -> None:
        found = metrics(asdlc.test_stage(LEDGER, ALL))
        self.assertEqual((found["first_pass_checks"]["count"], found["first_pass_checks"]["of"]), (1, 2))
        self.assertEqual(found["first_pass_checks"]["baseline"]["count"], 2)
        self.assertEqual((found["checks_per_task"]["median"], found["checks_per_task"]["max"]), (2, 3))
        self.assertEqual((found["failed_checks"]["count"], found["failed_checks"]["of"]), (1, 5))
        self.assertFalse(found["eval_pass_rate"]["measured"])
        self.assertIn("no eval suite", found["eval_pass_rate"]["needs"])

    def test_deploy(self) -> None:
        decisions = ({"time": minute(30).isoformat(), "hook": "guard_board", "verdict": "deny", "reason": the_guard().FORCE_REFUSAL},
                     {"time": minute(31).isoformat(), "hook": "guard_board", "verdict": "deny", "reason": "backlog/x.md is on the board: change the board with asdlc board, ..."},
                     {"time": minute(32).isoformat(), "hook": "guard_board", "verdict": "allow", "reason": "nothing"})
        found = metrics(asdlc.deploy_stage(LEDGER, decisions, {}, ALL))
        self.assertEqual((found["time_to_first_review"]["count"], found["time_to_first_review"]["median"], found["time_to_first_review"]["p90"]),
                         (3, 300.0, 3900.0))
        self.assertEqual(found["review_duration"]["median"], 300.0)
        self.assertEqual((found["worker_only_fixes"]["count"], found["worker_only_fixes"]["of"]), (1, 1))
        self.assertEqual((found["defects_caught"]["important"], found["defects_caught"]["nits"], found["defects_caught"]["tasks"]), (1, 3, 2))
        self.assertEqual(found["findings_by_policy"]["by_policy"], {"naming": {"2026-W43": 1}, "testing": {"2026-W43": 2}})
        self.assertEqual(found["defects_escaped"]["bugs"], [{"id": "TASK-4", "refs": ["TASK-2"], "week": "2026-W43"}])
        self.assertEqual((found["same_machine_reviews"]["count"], found["same_machine_reviews"]["of"]), (1, 3))
        self.assertEqual(found["review_to_done"]["median"], 2400.0)
        self.assertEqual({k: v["median"] for k, v in found["gate_waits"].items() if isinstance(v, dict) and "median" in v},
                         {"accept": 600.0, "approval": 300.0, "merge": 600.0})
        self.assertEqual(found["guard_refusals"]["by_rule"], {"force push": 1, "board file edited by hand": 1})

    def test_maintain_and_what_the_board_cant_measure(self) -> None:
        self.assertIn("play 12", metrics(asdlc.maintain_stage())["closing_the_loop"]["needs"])
        report = asdlc.stats_report(LEDGER, (), (), (), {}, ALL)
        self.assertEqual(list(report["stages"]), list(asdlc.STAGES))
        self.assertEqual([m["metric"] for m in report["not_measurable"]],
                         ["Change failure rate", "CI versus production regressions", "DORA metrics", "Pipeline failures triaged without paging"])
        self.assertTrue(all("data" in m["needs"] for m in report["not_measurable"]))
        self.assertEqual(report["tasks"], {"claimed": 2, "in_review": 1, "done": 1})

    def test_coordination(self) -> None:
        subjects = ((minute(14), "Add the app plugin"), (minute(42), "Release TASK-8 from @ann.w1"))
        event = lambda m, command, outcome: {"time": minute(m).isoformat(), "command": command, "outcome": outcome}  # noqa: E731
        events = (event(1, "next", "claimed"), event(2, "next", "lost"), event(3, "next", "claimed"), event(4, "claim", "refused"),
                  event(5, "review-next", "claimed"), event(6, "review-next", "lost"))
        found = metrics(asdlc.coordination_stage(LEDGER, subjects, events, ALL))
        self.assertEqual((found["lost_races"]["claimed"], found["lost_races"]["lost"], found["lost_races"]["lost_per_claim"]), (2, 1, 0.5))
        self.assertEqual(found["lost_races"]["by_command"]["review-next"], {"claimed": 1, "lost": 1})
        self.assertNotIn("reaped", found)
        self.assertEqual(found["released"]["count"], 1)
        self.assertEqual(found["onboardings"]["onboardings"], [{"plugin": "app", "published": minute(14).isoformat(), "task": "TASK-3", "seconds": 60.0}])
        later = metrics(asdlc.coordination_stage(LEDGER, subjects, events, asdlc.Window(minute(3), minute(100))))
        self.assertEqual((later["lost_races"]["claimed"], later["onboardings"]["onboardings"]), (1, [{"plugin": "app", "published": minute(14).isoformat(), "task": "TASK-3", "seconds": 60.0}]))

    def test_since_leaves_out_what_came_before(self) -> None:
        window = asdlc.Window(minute(50), minute(100))
        report = asdlc.stats_report(LEDGER, (), (), (), {}, window)
        self.assertEqual(report["tasks"], {"claimed": 0, "in_review": 1, "done": 1})
        self.assertEqual(metrics(report["stages"]["deploy"])["time_to_first_review"]["count"], 1)
        self.assertEqual(metrics(report["stages"]["plan"])["survival_rate"]["of"], 0)
        self.assertEqual(metrics(report["stages"]["build"])["parallel_claims"]["by_engineer"], {"ann": {"peak": 0, "median": None}})

    def test_lines(self) -> None:
        lines = asdlc.stats_lines(asdlc.stats_report(LEDGER, (), (), (), {}, ALL))
        self.assertIn("tasks: 2 claimed, 1 in review now, 1 done", lines)
        self.assertIn("Plan (play 01, 10)", lines)
        self.assertIn("  conversation to committed intent: median 10m, p90 10m (1); 1 intent(s) with no start recorded (DRAFT-2) "
                      "[play 01: Conversation to committed intent (leading)]", lines)
        self.assertIn("  claim to In Review: median 12m, p90 18m (2) [play 03: Claim to In Review]", lines)
        self.assertIn("  eval pass rate: not measured: there is no eval suite yet; it needs eval results recorded per change, which play 08's eval gate "
                      "will add [play 08: Eval pass rate]", lines)
        self.assertIn("Not measurable from the board", lines)
        only = asdlc.stats_lines(asdlc.stats_report(LEDGER, (), (), (), {}, ALL, ("test",)))
        self.assertNotIn("Plan (play 01, 10)", only)
        self.assertNotIn("Not measurable from the board", only)

    def test_refusal_rules_name_every_guard_refusal(self) -> None:
        guard = the_guard()  # the guard's own reasons, so the two can't drift apart
        for name in ("MERGE_REFUSAL", "APPROVAL_REFUSAL", "ACCEPT_REFUSAL", "APPROVE_REFUSAL", "PERMISSIONS_REFUSAL", "IN_PROGRESS_REFUSAL",
                     "IN_REVIEW_REFUSAL", "ASSIGNEE_REFUSAL", "REVIEW_LABEL_REFUSAL", "SIZE_REFUSAL", "FORCE_REFUSAL"):
            with self.subTest(name=name):
                self.assertNotIn("other", asdlc.refusal_rule("guard_board", getattr(guard, name)))
        for command in ("backlog task edit 1 -s Done", "backlog draft promote 2", "backlog task archive 1", "backlog task create X -l size-1"):
            with self.subTest(command=command):
                self.assertNotIn("other", asdlc.refusal_rule("guard_board", guard.backlog_refusal(command.split()[1:])))
        self.assertEqual(asdlc.refusal_rule("guard_x", "something new"), "guard_x: other")

    def test_percentile_and_the_pieces(self) -> None:
        self.assertIsNone(asdlc.percentile([], 0.5))
        self.assertEqual(asdlc.percentile([5, 1, 3, 2, 4], 0.5), 3)
        self.assertEqual(asdlc.percentile(list(range(1, 11)), 0.9), 9)
        self.assertEqual([asdlc._duration(v) for v in (None, 42.7, 60, 5400)], ["-", "42s", "1m", "1h 30m"])
        self.assertEqual(asdlc.published_plugins([(T0, "Add the acme-api plugin"), (T0, "Update the acme-api plugin"), (T0, "Claim TASK-1")]),
                         ((T0, "acme-api"),))
        self.assertEqual(asdlc.batch_objects(b"abc blob 3\nxyz\nmain:gone missing\ndef blob 0\n\n"), ["xyz", None, ""])

    def test_the_cache_round_trips(self) -> None:
        for found in HISTORY:
            for change in found.changes:
                with self.subTest(path=change.path):
                    self.assertEqual(asdlc.change_from_json(json.loads(json.dumps(asdlc.change_json(change)))), change)


def the_guard() -> object:
    load("hooks/decision_log.py")
    return load("hooks/guard_board.py")


# --- the script, against real git repositories and the backlog CLI --------------------


def as_engineer(name: str) -> dict[str, str]:
    """`git config asdlc.engineer <name>` through the environment, the way one machine sets it once."""
    return {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "asdlc.engineer", "GIT_CONFIG_VALUE_0": name}


# A machine with nothing registered: tests that register pass their own XDG_CONFIG_HOME. Its
# event log goes to a folder of its own, never the real ~/.local/state.
_STATE = tempfile.TemporaryDirectory()
NO_MACHINE_CONFIG = {"XDG_CONFIG_HOME": "/nonexistent/asdlc-tests", "XDG_STATE_HOME": _STATE.name, "ASDLC_GH": ""}  # no gh calls to GitHub


def _asdlc(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None, engineer: str = "agent") -> subprocess.CompletedProcess[str]:
    return run_script("scripts/asdlc", *args, cwd=cwd, env={
        **ISOLATED, **NO_MACHINE_CONFIG, **as_engineer(engineer), "ASDLC_BACKLOG": BACKLOG or "backlog", **(env or {}),
    })


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env={**os.environ, **ISOLATED})
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout.strip()


class Boards:
    """A bare board origin with tasks on it, and clones of it, in a temporary folder."""

    def __init__(self, test: unittest.TestCase, tasks: list[list[str]], projects: tuple[str, ...] = (), files: dict[str, str] | None = None) -> None:
        handle = tempfile.TemporaryDirectory()
        test.addCleanup(handle.cleanup)
        self.root = Path(handle.name).resolve()
        self.origin = self.root / "board-origin.git"
        _git(self.root, "init", "--quiet", "--bare", "-b", "main", str(self.origin))
        seed = self.root / "seed"
        done = _asdlc("init-board", str(seed))
        test.assertEqual(done.returncode, 0, done.stderr)
        config = seed / "backlog" / "config.yml"
        for project in projects:
            config.write_text(asdlc.with_project(config.read_text(), project) or config.read_text())
        for relative, text in (files or {}).items():
            (seed / relative).parent.mkdir(parents=True, exist_ok=True)
            (seed / relative).write_text(text)
        if projects or files:
            _git(seed, "add", ".")
            _git(seed, "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "-m", "Projects and settings")
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
            self.assertEqual(fields["labels"], ("size-1", "size-2", "size-3", "size-4", "size-5", "size-8", "changes-requested", "review-passed"))
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

    def test_the_environment_comes_before_git_config_and_the_flag_before_both(self) -> None:
        code = self.boards.root / "code"
        _git(self.boards.root, "init", "--quiet", "-b", "main", str(code))
        _git(code, "config", "asdlc.board", str(self.boards.root / "not-a-board"))
        done = _asdlc("board", "task", "list", "--plain", cwd=code, env={"ASDLC_BOARD": str(self.mine)})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("TASK-1", done.stdout)
        done = _asdlc("--board", str(self.mine), "board", "task", "list", "--plain", cwd=code, env={"ASDLC_BOARD": str(code)})
        self.assertEqual(done.returncode, 0, done.stderr)
        refused = _asdlc("board", "task", "list", "--plain", cwd=code)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("(from git config asdlc.board) is not a board", refused.stderr)

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


class BoardModeTest(unittest.TestCase):
    def test_a_board_with_no_settings_file_is_local(self) -> None:
        self.assertFalse(asdlc.board_mode(None))

    def test_a_board_with_settings_and_no_mode_is_shared_as_every_board_was(self) -> None:
        self.assertTrue(asdlc.board_mode('stale_after = "2h"\n'))

    def test_mode_says_which(self) -> None:
        self.assertTrue(asdlc.board_mode('mode = "shared"\n'))
        self.assertFalse(asdlc.board_mode('mode = "local"\n'))

    def test_any_other_mode_is_refused_with_the_two_words(self) -> None:
        with self.assertRaisesRegex(asdlc.AsdlcError, 'mode is "shared".*or "local"'):
            asdlc.board_mode('mode = "team"\n')


@needs_backlog
class LocalBoardTest(unittest.TestCase):
    """A board kept in the repository where the work is done: committed to the checked-out branch, never pushed."""

    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.code = Path(handle.name).resolve() / "code"
        _git(self.code.parent, "init", "--quiet", "-b", "main", str(self.code))
        _git(self.code, "config", "user.email", "test@example.com")
        _git(self.code, "config", "user.name", "Test")
        (self.code / "app.py").write_text("print('hi')\n")
        _git(self.code, "add", ".")
        _git(self.code, "commit", "--quiet", "-m", "start")
        _git(self.code, "switch", "--quiet", "-c", "feature")
        done = _asdlc("init-board", "--local", str(self.code))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_init_commits_backlog_on_the_checked_out_branch_and_writes_no_settings_file(self) -> None:
        self.assertEqual(_git(self.code, "log", "-1", "--format=%s"), "Initialise the asdlc board")
        self.assertEqual(_git(self.code, "branch", "--show-current"), "feature")
        self.assertFalse((self.code / "asdlc.toml").exists())
        self.assertFalse(asdlc.open_board(self.code).shared)

    def test_a_change_is_committed_to_the_branch_with_no_remote_and_code_edits_are_left_alone(self) -> None:
        (self.code / "app.py").write_text("print('edited')\n")
        (self.code / "notes.txt").write_text("untracked\n")
        done = _asdlc("board", "task", "create", *_sized("First"), cwd=self.code)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("TASK-1", done.stdout)
        self.assertEqual(_git(self.code, "branch", "--show-current"), "feature")
        self.assertEqual(_git(self.code, "show", "--stat", "--format=", "HEAD").count("app.py"), 0)
        self.assertEqual((self.code / "app.py").read_text(), "print('edited')\n")
        self.assertEqual((self.code / "notes.txt").read_text(), "untracked\n")
        self.assertEqual(_git(self.code, "status", "--porcelain"), "M app.py\n?? notes.txt")

    def test_a_refused_change_leaves_no_commit_and_code_edits_alone(self) -> None:
        (self.code / "app.py").write_text("print('edited')\n")
        head = _git(self.code, "rev-parse", "HEAD")
        done = _asdlc("board", "task", "edit", "TASK-9", "--notes", "x", cwd=self.code)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(_git(self.code, "rev-parse", "HEAD"), head)
        self.assertEqual(_git(self.code, "status", "--porcelain"), "M app.py")

    def test_a_dropped_change_takes_back_only_backlog(self) -> None:
        (self.code / "app.py").write_text("print('edited')\n")
        board = asdlc.open_board(self.code)
        with self.assertRaises(RuntimeError), asdlc._change(board):
            _git(self.code, "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "--allow-empty", "-m", "board change")
            (self.code / "backlog" / "stray.md").write_text("x\n")
            raise RuntimeError
        self.assertFalse((self.code / "backlog" / "stray.md").exists())
        self.assertEqual(_git(self.code, "log", "-1", "--format=%s"), "Initialise the asdlc board")
        self.assertEqual(_git(self.code, "status", "--porcelain"), "M app.py")

    def test_refuses_while_changes_are_staged_since_a_board_commit_would_sweep_them_in(self) -> None:
        (self.code / "app.py").write_text("print('staged')\n")
        _git(self.code, "add", "app.py")
        done = _asdlc("board", "task", "list", "--plain", cwd=self.code)
        self.assertEqual(done.returncode, 1)
        self.assertIn("staged changes", done.stderr)
        self.assertIn("app.py", done.stderr)


@needs_backlog
class ClaimTest(unittest.TestCase):
    def setUp(self) -> None:
        self.boards = Boards(self, [_sized("Add the login page"), _sized("Second", "size-1"), _sized("Too big", "size-8")])
        self.mine = self.boards.clone("mine")
        self.theirs = self.boards.clone("theirs")

    def test_claims_on_the_board_only_outside_a_code_repository(self) -> None:
        done = _asdlc("--board", str(self.mine), "claim", "1", "--as", "agent.1", cwd=self.boards.root)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("on the board only", done.stdout)
        claimed = self.boards.on_origin()["TASK-1"][0]
        self.assertEqual((claimed.status, claimed.assignees), ("In Progress", ("@agent.1",)))

    def test_refuses_a_claimed_task_and_one_that_cant_start(self) -> None:
        self.assertEqual(_asdlc("--board", str(self.mine), "claim", "TASK-1", "--as", "agent.1").returncode, 0)
        again = _asdlc("--board", str(self.theirs), "claim", "TASK-1", "--as", "agent.2")
        self.assertEqual(again.returncode, 1)
        self.assertIn("assigned to @agent.1", again.stderr)
        big = _asdlc("--board", str(self.theirs), "claim", "TASK-3", "--as", "agent.2")
        self.assertEqual(big.returncode, 1)
        self.assertIn("split it before it starts", big.stderr)

    def test_losing_at_the_push_undoes_the_claim(self) -> None:
        env = _interfering_backlog(self.boards.root, self.theirs, '"$REAL_BACKLOG" task edit TASK-1 -s "In Progress" -a @agent.2')
        done = _asdlc("--board", str(self.mine), "claim", "TASK-1", "--as", "agent.1", env=env)
        self.assertEqual(done.returncode, 1)
        self.assertIn("Another agent claimed TASK-1 first. Run asdlc next for another task.", done.stderr)
        self.assertEqual(self.boards.on_origin()["TASK-1"][0].assignees, ("@agent.2",))
        self.assertEqual(_git(self.mine, "rev-parse", "HEAD"), _git(self.mine, "rev-parse", "origin/main"))

    def test_each_attempt_goes_in_the_machines_event_log(self) -> None:
        state = {"XDG_STATE_HOME": str(self.boards.root / "state")}
        lose = _interfering_backlog(self.boards.root, self.theirs, '"$REAL_BACKLOG" task edit TASK-1 -s "In Progress" -a @agent.2')
        self.assertEqual(_asdlc("--board", str(self.mine), "claim", "TASK-1", "--as", "agent.1", env=lose | state).returncode, 1)
        self.assertEqual(_asdlc("--board", str(self.mine), "claim", "TASK-1", "--as", "agent.1", env=state).returncode, 1)
        self.assertEqual(_asdlc("--board", str(self.mine), "claim", "TASK-3", "--as", "agent.1", env=state).returncode, 1)
        self.assertEqual(_asdlc("--board", str(self.mine), "claim", "TASK-2", "--as", "agent.1", env=state).returncode, 0)
        log = (self.boards.root / "state" / "asdlc" / "events.jsonl").read_text()
        events = [(e["command"], e["worker"], e["task"], e["outcome"]) for e in asdlc.parse_events(log)]
        self.assertEqual(events, [("claim", "agent.1", "TASK-1", "lost"), ("claim", "agent.1", "TASK-1", "refused"),
                                  ("claim", "agent.1", "TASK-3", "refused"), ("claim", "agent.1", "TASK-2", "claimed")])
        self.assertIn("split it before it starts", asdlc.parse_events(log)[2]["reason"])

    def test_stats_reads_the_boards_history_and_the_log(self) -> None:
        state = {"XDG_STATE_HOME": str(self.boards.root / "state")}
        self.assertEqual(_asdlc("--board", str(self.mine), "claim", "TASK-1", "--as", "agent.1", env=state).returncode, 0)
        self.assertEqual(_asdlc("--board", str(self.mine), "board", "task", "edit", "TASK-1", "-s", "In Review").returncode, 0)
        done = _asdlc("--board", str(self.theirs), "stats", "--json", env=state)
        self.assertEqual(done.returncode, 0, done.stderr)
        report = json.loads(done.stdout)
        self.assertEqual(report["tasks"], {"claimed": 1, "in_review": 1, "done": 0})
        self.assertEqual(list(report["stages"]), list(asdlc.STAGES))
        stages = report["stages"]
        self.assertEqual(stages["build"]["metrics"]["claim_to_review"]["count"], 1)
        self.assertEqual(stages["deploy"]["metrics"]["time_to_first_review"]["waiting_now"], ["TASK-1"])
        races = stages["coordination"]["metrics"]["lost_races"]
        self.assertEqual((races["claimed"], races["lost"]), (1, 0))
        later = _asdlc("--board", str(self.theirs), "stats", "--since", "2999-01-01", env=state)
        self.assertIn("tasks: 0 claimed, 1 in review now, 0 done", later.stdout)
        self.assertIn("Not measurable from the board", later.stdout)
        build = _asdlc("--board", str(self.theirs), "stats", "--stage", "build", env=state)
        self.assertIn("Build (play 03, 06)", build.stdout)
        self.assertNotIn("Deploy (play", build.stdout)
        self.assertEqual(_git(self.theirs, "status", "--porcelain"), "", "stats changes nothing")

    def test_a_push_rejected_for_another_task_is_retried(self) -> None:
        env = _interfering_backlog(self.boards.root, self.theirs, '"$REAL_BACKLOG" task edit TASK-2 -s "In Progress" -a @agent.2')
        done = _asdlc("--board", str(self.mine), "claim", "TASK-1", "--as", "agent.1", env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        on_origin = self.boards.on_origin()
        self.assertEqual(on_origin["TASK-1"][0].assignees, ("@agent.1",))
        self.assertEqual(on_origin["TASK-2"][0].assignees, ("@agent.2",))

    def test_the_race(self) -> None:
        """Two clones claim the same task at once, ten times: exactly one wins each time."""
        boards = Boards(self, [_sized(f"Task {n}") for n in range(1, 11)])
        first, second = boards.clone("first"), boards.clone("second")
        lost_at_push = 0
        for number in range(1, 11):
            env = {**os.environ, **ISOLATED, **NO_MACHINE_CONFIG, **as_engineer("agent"), "ASDLC_BACKLOG": BACKLOG}
            racers = [
                subprocess.Popen([sys.executable, str(ROOT / "scripts" / "asdlc"), "--board", str(clone), "claim", f"TASK-{number}", "--as", worker],
                                 cwd=boards.root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for clone, worker in ((first, "agent.1"), (second, "agent.2"))
            ]
            results = [(racer.wait(timeout=120), *racer.communicate()) for racer in racers]
            codes = sorted(code for code, _, _ in results)
            self.assertEqual(codes, [0, 1], results)
            loser = next(err for code, _, err in results if code == 1)
            self.assertRegex(loser, r"Another agent claimed TASK-\d+ first|assigned to @agent\.")
            lost_at_push += "first" in loser
            claimed = boards.on_origin()[f"TASK-{number}"]
            self.assertEqual(len(claimed), 1)
            self.assertEqual(len(claimed[0].assignees), 1, claimed)
            self.assertEqual(claimed[0].status, "In Progress")
            for clone in (first, second):
                self.assertEqual(_git(clone, "status", "--porcelain", "--untracked-files=no"), "")
        print(f"\n  race: 10 of 10 had exactly one winner; {lost_at_push} were lost at the push", flush=True)


@needs_backlog
def _code_repo(root: Path, owner: str, name: str, clone: Path) -> Path:
    """A code repository with one commit on origin's main, its origin at <root>/origins/<owner>/<name>.git."""
    origin = root / "origins" / owner / f"{name}.git"
    origin.parent.mkdir(parents=True, exist_ok=True)
    if not origin.exists():
        _git(root, "init", "--quiet", "--bare", "-b", "main", str(origin))
        seed = root / "origins" / f"{owner}-{name}-seed"
        _git(root, "clone", "--quiet", str(origin), str(seed))
        (seed / "README.md").write_text(f"{name}\n")
        _git(seed, "add", ".")
        _git(seed, "commit", "--quiet", "-m", "start")
        _git(seed, "push", "--quiet", "origin", "main")
    _git(root, "clone", "--quiet", str(origin), str(clone))
    return clone


@needs_backlog
class WorktreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.boards = Boards(self, [_sized("Add the login page", "size-2", "--priority", "low", "--project", "acme-app"),
                                    _sized("Second", "size-1", "--priority", "high", "--project", "acme-app")], projects=("acme-app",))
        self.board = self.boards.clone("board")
        self.code = _code_repo(self.boards.root, "acme", "app", self.boards.root / "app")
        self.machine = {"XDG_CONFIG_HOME": str(self.boards.root / "config")}
        done = _asdlc("register", "--board", str(self.board), cwd=self.code, env=self.machine)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_claim_makes_a_worktree_with_its_marker(self) -> None:
        done = _asdlc("claim", "TASK-1", "--as", "agent.1", cwd=self.code, env=self.machine)
        self.assertEqual(done.returncode, 0, done.stderr)
        path = self.boards.root / "app.worktrees" / "task-1"
        self.assertEqual(done.stdout.strip().splitlines()[-1], str(path))
        self.assertEqual(json.loads((path / ".asdlc-task").read_text()), {"task": "TASK-1", "worker": "agent.1", "board": str(self.board), "type": "task"})
        self.assertEqual(_git(path, "branch", "--show-current"), "task-1-add-the-login-page")
        self.assertEqual(_git(path, "rev-parse", "HEAD"), _git(self.code, "rev-parse", "origin/main"))
        self.assertIn(".asdlc-task", (self.code / ".git" / "info" / "exclude").read_text().splitlines())
        self.assertEqual(_git(path, "status", "--porcelain"), "")
        no_upstream = subprocess.run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "@{upstream}"], capture_output=True)
        self.assertNotEqual(no_upstream.returncode, 0, "the task branch must not track main, or a bare git push could reach it")

    def test_a_bug_task_s_marker_says_so_for_the_test_edit_guard(self) -> None:
        made = _asdlc("board", "task", "create", "Lockout counts successes", "--type", "bug", "-l", "size-1", "--project", "acme-app",
                      cwd=self.board, env=self.machine)
        self.assertEqual(made.returncode, 0, made.stderr)
        done = _asdlc("claim", "TASK-3", "--as", "agent.1", cwd=self.code, env=self.machine)
        self.assertEqual(done.returncode, 0, done.stderr)
        marker = json.loads((self.boards.root / "app.worktrees" / "task-3" / ".asdlc-task").read_text())
        self.assertEqual((marker["task"], marker["type"]), ("TASK-3", "bug"))

    def test_next_takes_the_highest_priority_and_skips_claimed_tasks(self) -> None:
        first = _asdlc("next", "--as", "agent.1", cwd=self.code, env=self.machine)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("claimed TASK-2", first.stdout)
        second = _asdlc("next", "--as", "agent.2", cwd=self.code, env=self.machine)
        self.assertIn("claimed TASK-1", second.stdout)
        third = _asdlc("next", "--as", "agent.3", cwd=self.code, env=self.machine)
        self.assertEqual((third.returncode, third.stdout.strip()), (0, "no work available"))

    def test_release_puts_the_task_back_and_leaves_the_worktree(self) -> None:
        self.assertEqual(_asdlc("claim", "TASK-1", "--as", "agent.1", cwd=self.code, env=self.machine).returncode, 0)
        refused = _asdlc("release", "TASK-1", "--as", "agent.2", cwd=self.code, env=self.machine)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("only @agent.2's own", refused.stderr)
        done = _asdlc("release", "TASK-1", "--as", "agent.1", cwd=self.code, env=self.machine)
        self.assertEqual(done.returncode, 0, done.stderr)
        released = self.boards.on_origin()["TASK-1"][0]
        self.assertEqual((released.status, released.assignees), ("To Do", ()))
        path = self.boards.root / "app.worktrees" / "task-1"
        self.assertIn(str(path), done.stdout)
        self.assertTrue((path / ".asdlc-task").exists())
        again = _asdlc("claim", "TASK-1", "--as", "agent.2", cwd=self.code, env=self.machine)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads((path / ".asdlc-task").read_text())["worker"], "agent.2")

    def test_the_default_branch_comes_from_origin_head(self) -> None:
        _git(self.code, "push", "--quiet", "origin", "main:trunk")
        _git(self.code, "remote", "set-head", "origin", "trunk")
        self.assertEqual(asdlc.default_branch(self.code), "trunk")
        _git(self.code, "remote", "set-head", "origin", "--delete")
        self.assertEqual(asdlc.default_branch(self.code), "main")


class Team:
    """A board with two projects, and one machine with clones of both code repositories registered."""

    def __init__(self, test: unittest.TestCase, tasks: list[list[str]], files: dict[str, str] | None = None) -> None:
        self.test = test
        self.boards = Boards(test, tasks, projects=("acme-api", "acme-web", "acme-ios"), files=files)  # acme-ios: registered on another machine only
        root = self.boards.root
        self.board = self.boards.clone("board")
        self.machine = {"XDG_CONFIG_HOME": str(root / "config")}
        self.api = _code_repo(root, "acme", "api", root / "api")
        self.web = _code_repo(root, "acme", "web", root / "web")
        for repo in (self.api, self.web):
            done = _asdlc("register", "--board", str(self.board), cwd=repo, env=self.machine)
            test.assertEqual(done.returncode, 0, done.stderr)

    def run(self, *args: str, engineer: str = "kyle", cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return _asdlc("--board", str(self.board), *args, cwd=cwd or self.boards.root, env={**self.machine, **(env or {})}, engineer=engineer)

    def ok(self, *args: str, **options: object) -> subprocess.CompletedProcess[str]:
        done = self.run(*args, **options)
        self.test.assertEqual(done.returncode, 0, done.stderr)
        return done

    def task(self, task_id: str) -> object:
        return self.boards.on_origin()[task_id][0]

    def text(self, task_id: str) -> str:
        """A task or draft file's text as it is on origin/main."""
        fresh = Path(tempfile.mkdtemp(dir=self.boards.root))
        _git(fresh, "clone", "--quiet", str(self.boards.origin), str(fresh / "c"))
        for path in (fresh / "c" / "backlog").glob("*/*.md"):
            if path.name.lower().startswith(f"{task_id.lower()} - "):
                return path.read_text()
        raise AssertionError(f"{task_id} is not on origin")


@needs_backlog
class IdentityAndRegisterTest(unittest.TestCase):
    def test_whoami_needs_the_engineer_and_says_how_to_set_it(self) -> None:
        done = run_script("scripts/asdlc", "whoami", env={**ISOLATED, **NO_MACHINE_CONFIG})
        self.assertEqual(done.returncode, 1)
        self.assertIn("git config --global asdlc.engineer <name>", done.stderr)
        claimed = run_script("scripts/asdlc", "--board", "/nowhere", "claim", "1", "--as", "kyle.w1", env={**ISOLATED, **NO_MACHINE_CONFIG})
        self.assertEqual(claimed.returncode, 1)

    def test_register_records_the_repository_on_the_machine_and_the_board(self) -> None:
        team = Team(self, [])
        registry = asdlc.parse_registry((team.boards.root / "config" / "asdlc" / "repos.toml").read_text())
        self.assertEqual({slug: e.path for slug, e in registry.items()}, {"acme-api": team.api.resolve(), "acme-web": team.web.resolve()})
        self.assertEqual(_git(team.api, "config", "asdlc.board"), str(team.board))
        fresh = team.boards.clone("check")
        self.assertEqual(asdlc.frontmatter(f"---\n{(fresh / 'backlog' / 'config.yml').read_text()}---\n")["projects"], ("acme-api", "acme-web", "acme-ios"))
        again = _asdlc("register", "--json", cwd=team.api, env=team.machine)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout)["added_to_board"], False)
        listed = _asdlc("repos", "--json", env=team.machine)
        self.assertEqual([r["slug"] for r in json.loads(listed.stdout)["repos"]], ["acme-api", "acme-web"])

    def test_a_new_project_is_added_to_the_boards_projects(self) -> None:
        team = Team(self, [])
        docs = _code_repo(team.boards.root, "acme", "docs", team.boards.root / "docs")
        done = _asdlc("register", "--board", str(team.board), cwd=docs, env=team.machine)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("acme-docs added to the board's projects", done.stdout)
        self.assertEqual(_git(team.boards.origin, "log", "-1", "--format=%s", "main"), "Register project acme-docs")

    def test_register_needs_an_origin(self) -> None:
        team = Team(self, [])
        lonely = team.boards.root / "lonely"
        _git(team.boards.root, "init", "--quiet", "-b", "main", str(lonely))
        done = _asdlc("register", "--board", str(team.board), cwd=lonely, env=team.machine)
        self.assertEqual(done.returncode, 1)
        self.assertIn("has no origin remote", done.stderr)

    def test_whoami_reports_preferences_and_repositories(self) -> None:
        team = Team(self, [], files={"devs/kyle.yaml": "name: kyle\nprefer: [acme-web]\nworkers: 2\n"})
        report = json.loads(team.ok("whoami", "--json").stdout)
        self.assertEqual(report["engineer"], "kyle")
        self.assertEqual(report["board"], str(team.board))
        self.assertEqual((report["preferences"]["prefer"], report["preferences"]["workers"]), (["acme-web"], 2))
        self.assertEqual(sorted(report["repos"]), ["acme-api", "acme-web"])


@needs_backlog
class ReservedClaimTest(unittest.TestCase):
    def setUp(self) -> None:
        self.team = Team(self, [
            _sized("Reserved", "size-2", "--project", "acme-api", "-a", "@kyle"),
            _sized("Open", "size-2", "--project", "acme-web"),
            _sized("Elsewhere", "size-2", "--project", "acme-ios"),
        ])

    def test_only_the_owners_workers_claim_reserved_work_and_the_person_stays(self) -> None:
        refused = self.team.run("claim", "1", "--as", "ann.w1", engineer="ann")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("reserved for @kyle", refused.stderr)
        done = self.team.ok("claim", "1", "--as", "kyle.w1", "--json")
        report = json.loads(done.stdout)
        self.assertEqual(self.team.task("TASK-1").assignees, ("@kyle", "@kyle.w1"))
        self.assertEqual(report["worktree"], str(self.team.boards.root / "api.worktrees" / "task-1"))
        self.assertEqual((report["project"], report["model"], report["branch"]), ("acme-api", "sonnet", "task-1-reserved"))
        released = self.team.ok("release", "1", "--as", "kyle.w1")
        self.assertIn("reserved for @kyle", released.stdout)
        self.assertEqual((self.team.task("TASK-1").status, self.team.task("TASK-1").assignees), ("To Do", ("@kyle",)))

    def test_the_worktree_is_made_in_the_registered_repository_not_the_current_directory(self) -> None:
        done = self.team.ok("claim", "2", "--as", "kyle.w1", cwd=self.team.api)
        path = self.team.boards.root / "web.worktrees" / "task-2"
        self.assertEqual(done.stdout.strip().splitlines()[-1], str(path))
        self.assertEqual(_git(path, "rev-parse", "HEAD"), _git(self.team.web, "rev-parse", "origin/main"))

    def test_a_worker_must_belong_to_the_engineer(self) -> None:
        done = self.team.run("claim", "2", "--as", "ann.w1")
        self.assertEqual(done.returncode, 1)
        self.assertIn("not one of kyle's workers", done.stderr)

    def test_a_task_in_an_unregistered_repository_is_refused_before_it_is_claimed(self) -> None:
        done = self.team.run("claim", "3", "--as", "kyle.w1")
        self.assertEqual(done.returncode, 1)
        self.assertIn("acme-ios, which is not registered on this machine", done.stderr)
        self.assertEqual(self.team.task("TASK-3").status, "To Do")


@needs_backlog
class NextTest(unittest.TestCase):
    def test_preferences_rank_work_and_the_cap_holds(self) -> None:
        team = Team(self, [
            _sized("Api", "size-2", "--project", "acme-api", "--priority", "high"),
            _sized("Web", "size-2", "--project", "acme-web", "--priority", "low"),
            _sized("Elsewhere", "size-2", "--project", "acme-ios"),
        ], files={"devs/kyle.yaml": "name: kyle\nprefer: [acme-web]\nworkers: 1\n"})
        first = team.ok("next", "--as", "kyle.w1", "--json")
        report = json.loads(first.stdout)
        self.assertEqual((report["task"], report["worker"]), ("TASK-2", "kyle.w1"))
        self.assertIn("skipped TASK-3 is in acme-ios", first.stderr)
        capped = team.ok("next", "--as", "kyle.w2", "--json")
        self.assertIn("the cap in devs/kyle.yaml (1)", json.loads(capped.stdout)["reason"])
        self.assertEqual(team.task("TASK-1").status, "To Do")
        other = json.loads(team.ok("next", "--as", "ann.w1", "--json", engineer="ann").stdout)
        self.assertEqual(other["task"], "TASK-1")
        none = team.ok("next", "--as", "ann.w2", engineer="ann")
        self.assertEqual(none.stdout.strip(), "no work available")


@needs_backlog
class AcceptTest(unittest.TestCase):
    def test_accepts_an_intent_and_its_draft_children_in_one_commit(self) -> None:
        team = Team(self, [_sized("Already here", "size-1", "--project", "acme-api"), ["Big thing", "--draft", "--type", "intent", "--ac", "It works"]])
        team.ok("board", "task", "create", "Api part", "--draft", "-p", "DRAFT-1", "--project", "acme-api", "-l", "size-2")
        team.ok("board", "task", "create", "Web part", "--draft", "-p", "DRAFT-1", "--project", "acme-web", "-l", "size-1", "--dep", "DRAFT-2", "-a", "@kyle")
        before = int(_git(team.boards.origin, "rev-list", "--count", "main"))
        report = json.loads(team.ok("accept", "DRAFT-1", "--json").stdout)
        self.assertEqual(int(_git(team.boards.origin, "rev-list", "--count", "main")), before + 1)
        self.assertEqual(report["accepted"], {"DRAFT-1": "TASK-2", "DRAFT-2": "TASK-2.1", "DRAFT-3": "TASK-2.2"})
        on_origin = team.boards.on_origin()
        intent, api, web = on_origin["TASK-2"][0], on_origin["TASK-2.1"][0], on_origin["TASK-2.2"][0]
        self.assertEqual((intent.status, intent.type), ("To Do", "intent"))
        self.assertEqual((api.parent, api.project, web.parent, web.dependencies, web.assignees), ("TASK-2", "acme-api", "TASK-2", ("TASK-2.1",), ("@kyle",)))
        fresh = team.boards.clone("after")
        self.assertEqual(list((fresh / "backlog" / "drafts").glob("*.md")), [])
        later = team.ok("board", "task", "create", "Docs part", "--draft", "-p", "TASK-2", "--project", "acme-api", "-l", "size-1")
        self.assertIn("DRAFT-1", later.stdout)
        self.assertEqual(json.loads(team.ok("accept", "TASK-2", "--json").stdout)["accepted"], {"DRAFT-1": "TASK-2.3"})
        self.assertIn("nothing to accept", team.ok("accept", "TASK-2").stdout)
        refused = team.run("accept", "TASK-1")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("not an intent", refused.stderr)


@needs_backlog
class MineAndRecordCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.team = Team(self, [
            _sized("Mine", "size-2", "--project", "acme-api"),
            _sized("Reserved", "size-2", "--project", "acme-web", "-a", "@kyle"),
            ["Big thing", "--type", "intent"],
        ])
        self.team.ok("claim", "1", "--as", "kyle.w1")

    def test_mine(self) -> None:
        report = json.loads(self.team.ok("mine", "--as", "kyle", "--json").stdout)
        self.assertEqual((report["active"], report["workers_cap"]), (1, 3))
        self.assertEqual([(t["id"], t["workers"]) for t in report["tasks"]], [("TASK-1", ["kyle.w1"])])
        self.assertNotIn("leads", report)
        self.assertEqual([t["id"] for t in report["reserved"]], ["TASK-2"])
        self.assertIn("1 of 3 workers busy", self.team.ok("mine", "--as", "kyle").stdout)

    def test_record_check_notes_the_command_and_keeps_its_exit_code(self) -> None:
        worktree = self.team.boards.root / "api.worktrees" / "task-1"
        self.team.ok("board", "task", "edit", "TASK-1", "--plan", "1. Do it. Proof: the check.")
        self.team.ok("approve", "TASK-1")
        done = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "sh", "-c", "echo checked; exit 3", cwd=worktree, env=self.team.machine, engineer="kyle")
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertEqual(done.stdout, "checked\n")
        text = self.team.text("TASK-1")
        self.assertIn("Check FAILED: `sh -c 'echo checked; exit 3'` exited 3", text)
        self.assertIn(f"in {worktree} on task-1-mine at {_git(worktree, 'rev-parse', 'HEAD')[:12]}", text)
        self.assertIn("checked", text)
        self.assertEqual(self.team.run("record-check", "TASK-1", "true").returncode, 1)


@needs_backlog
class ReviewCommandTest(unittest.TestCase):
    """Review claims, the same-machine fallback and verdicts, against real repositories."""

    def setUp(self) -> None:
        self.team = Team(self, [_sized("Rate limit", "size-2", "--project", "acme-api"), _sized("Second", "size-2", "--project", "acme-api")])

    def submit(self, task_id: str, worker: str = "ann.w1", team: object | None = None) -> None:
        """A worker claims the task and finishes it: branch and pull request recorded, In Review."""
        team = team or self.team
        engineer = asdlc.owner_of(worker)
        team.ok("claim", task_id, "--as", worker, engineer=engineer)
        number = task_id.rpartition("-")[2]
        team.ok("board", "task", "edit", task_id, "--plan", "1. Limit it. Proof: the tests.", engineer=engineer)
        team.ok("approve", task_id, engineer=engineer)
        team.ok("finish", task_id, "--as", worker, "--pr", f"https://github.com/acme/api/pull/{number}",
                "--notes", "Built.", engineer=engineer)

    def later(self, **delta: float) -> str:
        return (datetime.now(UTC) + timedelta(**delta)).isoformat()

    def review(self, reviewer: str, *extra: str, team: object | None = None) -> dict[str, object]:
        done = (team or self.team).ok("review-next", "--as", reviewer, "--json", *extra, engineer=asdlc.owner_of(reviewer))
        return json.loads(done.stdout)

    def test_claims_the_oldest_review_and_says_where_to_review_it(self) -> None:
        self.submit("TASK-1")
        self.submit("TASK-2", "ann.w2")
        first = self.review("kyle.r1")
        self.assertEqual(
            {k: first[k] for k in ("task", "reviewer", "kind", "authors", "repo", "default_branch", "branch", "pull_request", "model", "effort")},
            {"task": "TASK-1", "reviewer": "kyle.r1", "kind": "cross-machine", "authors": ["ann"], "repo": str(self.team.api), "default_branch": "main",
             "branch": "task-1-rate-limit", "pull_request": "https://github.com/acme/api/pull/1", "model": "sonnet", "effort": "medium"},
        )
        on_board = self.team.task("TASK-1")
        self.assertEqual((on_board.status, on_board.assignees, on_board.reviewer, on_board.review_kind), ("In Review", ("@ann.w1",), "kyle.r1", "cross-machine"))
        self.assertEqual(first["policies"], [str(self.team.board / "plugins" / "team" / "review.md")], "I3: the team's review policy, never asdlc's REVIEW.md")
        self.assertIn("@kyle.r1 is reviewing TASK-1: a cross-machine review.", self.team.text("TASK-1"))
        self.assertEqual(_git(self.team.boards.origin, "log", "-1", "--format=%s", "main"), "Review TASK-1: @kyle.r1 (cross-machine)")
        self.assertEqual(self.review("kyle.r2")["task"], "TASK-2")
        none = self.team.ok("review-next", "--as", "kyle.r3")
        self.assertEqual(none.stdout.strip(), "no review available")
        self.assertIn("skipped TASK-1 is being reviewed by @kyle.r1", none.stderr)
        mine = json.loads(self.team.ok("mine", "--as", "kyle", "--json").stdout)
        self.assertEqual(([r["id"] for r in mine["reviews"]], mine["reviewing"], mine["tasks"]), (["TASK-1", "TASK-2"], 2, []))
        self.assertIn("review TASK-1\t@kyle.r1\tcross-machine", self.team.ok("mine", "--as", "kyle").stdout)

    def test_by_default_the_author_reviews_at_once_with_the_fallback(self) -> None:
        self.submit("TASK-1")
        late = self.review("ann.r1", "--fallback")
        self.assertEqual((late["task"], late["kind"]), ("TASK-1", "same-machine"))

    def test_the_author_reviews_only_with_fallback_after_the_timeout(self) -> None:
        team = Team(self, [_sized("Rate limit", "size-2", "--project", "acme-api")], files={"asdlc.toml": 'review_fallback_after = "30m"\n'})
        self.team = team
        self.submit("TASK-1")
        own = self.team.ok("review-next", "--as", "ann.r1", "--json", engineer="ann")
        self.assertFalse(json.loads(own.stdout)["claimed"])
        self.assertIn("TASK-1 is ann's own work: another engineer reviews it, or a fresh reviewer here with --fallback", own.stderr)
        early = self.team.ok("review-next", "--as", "ann.r1", "--fallback", "--now", self.later(minutes=10), engineer="ann")
        self.assertEqual(early.stdout.strip(), "no review available")
        self.assertRegex(early.stderr, r"it has waited (9|10)m for one, not yet longer than review_fallback_after \(30m\)")
        late = self.review("ann.r1", "--fallback", "--now", self.later(minutes=31))
        self.assertEqual((late["task"], late["kind"]), ("TASK-1", "same-machine"))
        self.assertEqual(self.team.task("TASK-1").review_kind, "same-machine")
        self.assertRegex(self.team.text("TASK-1"), r"@ann\.r1 is reviewing TASK-1: a same-machine review: it waited 3[01]m")

    def test_the_fallback_timeout_comes_from_the_boards_asdlc_toml(self) -> None:
        team = Team(self, [_sized("Rate limit", "size-2", "--project", "acme-api")], files={"asdlc.toml": 'review_fallback_after = "1h"\n'})
        self.submit("TASK-1", team=team)
        early = team.ok("review-next", "--as", "ann.r1", "--fallback", "--now", self.later(minutes=45), engineer="ann")
        self.assertIn("review_fallback_after (1h 0m)", early.stderr)
        self.assertEqual(self.review("ann.r1", "--fallback", "--now", self.later(minutes=61), team=team)["kind"], "same-machine")

    def test_changes_go_back_to_the_author_and_a_clean_review_waits_for_a_person(self) -> None:
        self.submit("TASK-1")
        self.review("kyle.r1")
        missing = self.team.run("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "changes", "--notes", "[Bugs, Important] x")
        self.assertEqual(missing.returncode, 2)
        self.assertIn("--findings", missing.stderr)
        unfit = self.team.run("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "changes", "--findings", "nit=1", "--plan-matched", "yes",
                              "--notes", "[Bugs, Nit] x")
        self.assertIn("a changes verdict needs at least one Important finding", unfit.stderr)
        self.assertEqual(self.team.task("TASK-1").reviewer, "kyle.r1", "a refused verdict changes nothing")
        changes = json.loads(self.team.ok("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "changes", "--json",
                                          "--findings", "important=1,nit=2", "--policy", "testing", "--policy", "Bugs", "--plan-matched", "no",
                                          "--notes", "[Bugs, Important] the limit resets on every request").stdout)
        self.assertEqual((changes["status"], changes["workers"]), ("In Progress", ["ann.w1"]))
        self.assertEqual((changes["findings"], changes["policies"], changes["plan_matched"]), ({"important": 1, "nit": 2}, ["testing", "Bugs"], False))
        back = self.team.task("TASK-1")
        self.assertEqual((back.review_findings, back.review_policies, back.plan_matched), ("important=1,nit=2", ("testing", "Bugs"), "no"))
        self.assertEqual((back.status, back.assignees, back.reviewer, back.review_kind), ("In Progress", ("@ann.w1",), "", "cross-machine"))
        self.assertIn("changes-requested", back.labels)
        text = self.team.text("TASK-1")
        self.assertIn("Review by @kyle.r1 (cross-machine): changes requested.", text)
        self.assertIn("[Bugs, Important] the limit resets on every request", text)
        self.assertIn("Findings: 1 Important, 2 nit. Cites: testing, Bugs. The diff does not match the plan.", text)
        mine = json.loads(self.team.ok("mine", "--as", "ann", "--json", engineer="ann").stdout)
        self.assertEqual([r["id"] for r in mine["changes_requested"]], ["TASK-1"])
        self.team.ok("finish", "TASK-1", "--as", "ann.w1", "--notes", "Fixed: failures only are counted.", engineer="ann")
        self.assertEqual(self.review("kyle.r1")["task"], "TASK-1")
        clean = self.team.ok("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "clean", "--findings", "important=0,nit=0",
                             "--plan-matched", "yes", "--notes", "No findings.")
        self.assertEqual(clean.stdout.strip(), "TASK-1 passed review by @kyle.r1 (cross-machine); it stays In Review for a person to merge")
        passed = self.team.task("TASK-1")
        self.assertEqual((passed.status, passed.reviewer, passed.labels), ("In Review", "", ("size-2", "review-passed")))
        self.assertEqual((passed.review_findings, passed.review_policies, passed.plan_matched), ("important=0,nit=0", (), "yes"))
        again = self.team.ok("review-next", "--as", "kyle.r1")
        self.assertIn("skipped TASK-1 has passed review and waits for a person to merge it", again.stderr)

    def test_a_second_review_citing_a_policy_names_the_earlier_one(self) -> None:
        self.submit("TASK-1")
        self.submit("TASK-2", "ann.w2")
        self.assertEqual(self.review("kyle.r1")["task"], "TASK-1")
        first = json.loads(self.team.ok("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "changes", "--json", *CHANGES,
                                        "--policy", "testing", "--notes", "[Bugs, Important] asserts on a mock").stdout)
        self.assertEqual(first["repeats"], {})
        self.assertEqual(self.review("kyle.r2")["task"], "TASK-2")
        second = self.team.ok("review-done", "TASK-2", "--as", "kyle.r2", "--verdict", "changes", *CHANGES,
                              "--policy", "testing", "--policy", "review", "--notes", "[Bugs, Important] asserts on a mock again")
        self.assertIn("Earlier reviews cited the same policy: testing (TASK-1).", second.stdout)
        self.assertIn("rule-change", second.stdout)

    def test_only_the_claiming_reviewer_finishes_the_review(self) -> None:
        self.submit("TASK-1")
        self.review("kyle.r1")
        for reviewer, says in (("lee.r1", "@kyle.r1 holds its review, so @lee.r1 can't finish it"), ("kyle.r2", "so @kyle.r2 can't finish it"),
                               ("kyle.w1", "not a reviewer's name")):
            with self.subTest(reviewer=reviewer):
                done = self.team.run("review-done", "TASK-1", "--as", reviewer, "--verdict", "clean", *CLEAN, "--notes", "ok", engineer=asdlc.owner_of(reviewer))
                self.assertEqual(done.returncode, 1)
                self.assertIn(says, done.stderr)
        empty = self.team.run("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "clean", *CLEAN, "--notes", " ")
        self.assertIn("say what the review found", empty.stderr)
        self.assertEqual(self.team.task("TASK-1").reviewer, "kyle.r1")
        unclaimed = self.team.run("review-done", "TASK-2", "--as", "kyle.r1", "--verdict", "clean", *CLEAN, "--notes", "ok")
        self.assertIn("nobody holds its review", unclaimed.stderr)

    def test_a_reviewer_gives_up_its_review_claim_and_nobody_else_can(self) -> None:
        self.submit("TASK-1")
        self.review("kyle.r1")
        refused = self.team.run("release", "TASK-1", "--as", "lee.r1", engineer="lee")
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(self.team.task("TASK-1").reviewer, "kyle.r1")
        self.team.ok("release", "TASK-1", "--as", "kyle.r1")
        released = self.team.task("TASK-1")
        self.assertEqual((released.status, released.assignees, released.reviewer, released.review_kind), ("In Review", ("@ann.w1",), "", ""))
        self.assertIn("@kyle.r1 released its review claim", self.team.text("TASK-1"))
        self.assertEqual(self.review("lee.r1")["task"], "TASK-1")

    def test_an_engineer_who_does_not_review_takes_none(self) -> None:
        team = Team(self, [_sized("Rate limit", "size-2", "--project", "acme-api")], files={"devs/kyle.yaml": "name: kyle\nreview: false\n"})
        self.submit("TASK-1", team=team)
        report = json.loads(team.ok("review-next", "--as", "kyle.r1", "--json").stdout)
        self.assertEqual(report["claimed"], False)
        self.assertIn("devs/kyle.yaml has review: false", report["reason"])

    def test_losing_a_review_claim_at_the_push(self) -> None:
        self.submit("TASK-1")
        theirs = self.team.boards.clone("theirs")
        other = 'sed -i "s/^type: task$/type: task\\nasdlc_reviewer: lee.r1/" backlog/tasks/task-1*.md && git commit -qam review'
        done = self.team.run("review-next", "--as", "kyle.r1", "--json", env=_interfering_backlog(self.team.boards.root, theirs, other))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["claimed"], False)
        self.assertIn("Another reviewer claimed the review of TASK-1 first: @lee.r1", done.stderr)
        self.assertEqual(self.team.task("TASK-1").reviewer, "lee.r1")
        self.assertEqual(_git(self.team.board, "rev-parse", "HEAD"), _git(self.team.board, "rev-parse", "origin/main"))

    def test_two_reviewers_on_two_clones_at_once(self) -> None:
        """Both race for the same oldest review: each ends with exactly one review, never the same one."""
        self.submit("TASK-1")
        self.submit("TASK-2", "ann.w2")
        theirs = self.team.boards.clone("theirs")
        racers = [
            subprocess.Popen([sys.executable, str(ROOT / "scripts" / "asdlc"), "--board", str(clone), "review-next", "--as", reviewer, "--json"],
                             cwd=self.team.boards.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             env={**os.environ, **ISOLATED, **self.team.machine, **as_engineer(asdlc.owner_of(reviewer)), "ASDLC_BACKLOG": BACKLOG})
            for clone, reviewer in ((self.team.board, "kyle.r1"), (theirs, "lee.r1"))
        ]
        results = [(racer.wait(timeout=120), *racer.communicate()) for racer in racers]
        self.assertEqual([code for code, _, _ in results], [0, 0], results)
        claimed = {json.loads(out)["reviewer"]: json.loads(out)["task"] for _, out, _ in results}
        self.assertEqual(sorted(claimed.values()), ["TASK-1", "TASK-2"], results)
        self.assertEqual({tid: self.team.task(tid).reviewer for tid in ("TASK-1", "TASK-2")}, {task_id: r for r, task_id in claimed.items()})


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


@needs_backlog
class DraftParentCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.team = Team(self, [["Big thing", "--draft", "--type", "intent"]])

    def test_the_board_refuses_a_draft_parent_that_isnt_a_draft(self) -> None:
        done = self.team.run("board", "task", "create", "Child", "--draft", "-p", "DRAFT-7")
        self.assertEqual(done.returncode, 1)
        self.assertIn("DRAFT-7 is not a draft on the board", done.stderr)


if __name__ == "__main__":
    unittest.main()


# --- the independent review's experiments, as regression tests -----------------------
# Each class reproduces one experiment from the review of the pilot (plan/pilot.md,
# "Fixes from the independent review") against real repositories.


@needs_backlog
class ReleasedWorkerTest(unittest.TestCase):
    """B1: a worker that let go of a task can't finish, or record checks on, a task someone else now holds."""

    def setUp(self) -> None:
        self.team = Team(self, [_sized("Add login", "size-1", "--project", "acme-api")])
        self.team.ok("claim", "1", "--as", "kyle.w1")
        self.worktree = self.team.boards.root / "api.worktrees" / "task-1"
        self.team.ok("release", "1", "--as", "kyle.w1")
        self.team.ok("claim", "1", "--as", "ann.w1", engineer="ann")

    def test_finish_refuses_a_worker_that_no_longer_holds_the_task(self) -> None:
        done = self.team.run("finish", "1", "--as", "kyle.w1", "--pr", "https://github.com/acme/api/pull/1", "--notes", "built")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("@ann.w1", done.stderr)
        task = self.team.task("TASK-1")
        self.assertEqual((task.status, task.assignees, task.references), ("In Progress", ("@ann.w1",), ()))

    def test_record_check_refuses_a_worker_that_no_longer_holds_the_task(self) -> None:
        ran = self.team.boards.root / "ran"
        done = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "touch", str(ran), cwd=self.worktree, env=self.team.machine, engineer="kyle")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("@ann.w1", done.stderr)
        self.assertFalse(ran.exists(), "the check ran for a worker that doesn't hold the task")
        self.assertNotIn("Check passed", self.team.text("TASK-1"))

    def test_the_holder_finishes_it(self) -> None:
        done = self.team.ok("finish", "1", "--as", "ann.w1", "--pr", "https://github.com/acme/api/pull/1", "--notes", "built it", engineer="ann")
        self.assertIn("TASK-1 is In Review", done.stdout)
        task = self.team.task("TASK-1")
        self.assertEqual((task.status, task.assignees), ("In Review", ("@ann.w1",)))
        self.assertEqual(task.references, ("task-1-add-login", "https://github.com/acme/api/pull/1"))
        self.assertIn("built it", self.team.text("TASK-1"))
        self.assertEqual(_git(self.team.boards.origin, "log", "-1", "--format=%s", "main"), "Finish TASK-1: @ann.w1, In Review")


@needs_backlog
class ResumedBranchTest(unittest.TestCase):
    """B2: a released changes-requested task is resumed from its pushed branch, never rebuilt from main."""

    def test_the_branch_is_recorded_at_claim_and_a_reclaim_resumes_it_from_origin(self) -> None:
        team = Team(self, [_sized("Add login", "size-1", "--project", "acme-api")])
        report = json.loads(team.ok("claim", "1", "--as", "kyle.w1", "--json").stdout)
        worktree, branch = Path(report["worktree"]), report["branch"]
        self.assertEqual(team.task("TASK-1").branch, branch)
        (worktree / "login.py").write_text("kyle's work\n")
        _git(worktree, "add", ".")
        _git(worktree, "commit", "-qm", "kyle's work")
        _git(worktree, "push", "-q", "-u", "origin", "HEAD")
        work = _git(worktree, "rev-parse", "HEAD")
        team.ok("finish", "1", "--as", "kyle.w1", "--notes", "built")
        team.ok("review-next", "--as", "ann.r1", engineer="ann")
        team.ok("review-done", "1", "--as", "ann.r1", "--verdict", "changes", *CHANGES, "--notes", "[Bugs, Important] fix x", engineer="ann")
        team.ok("release", "1", "--as", "kyle.w1")
        released = team.task("TASK-1")
        self.assertEqual((released.status, released.assignees, released.branch), ("To Do", ("@kyle",), branch))
        self.assertIn("changes-requested", released.labels)
        refused = team.run("claim", "1", "--as", "ann.w1", engineer="ann")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("reserved for @kyle", refused.stderr)
        # Another of kyle's workers picks it up on a machine without the old worktree or branch.
        _git(team.api, "worktree", "remove", "--force", str(worktree))
        _git(team.api, "branch", "-D", branch)
        again = json.loads(team.ok("claim", "1", "--as", "kyle.w2", "--json").stdout)
        self.assertEqual((again["worktree"], again["branch"], again["resumed_from"]), (str(worktree), branch, f"origin/{branch}"))
        self.assertEqual(_git(worktree, "rev-parse", "HEAD"), work)
        self.assertEqual((worktree / "login.py").read_text(), "kyle's work\n")
        (worktree / "fix.py").write_text("fixed\n")
        _git(worktree, "add", ".")
        _git(worktree, "commit", "-qm", "fix")
        _git(worktree, "push", "-q", "-u", "origin", "HEAD")
        self.assertEqual(_git(team.api, "rev-list", "--count", f"origin/main..origin/{branch}"), "2")

    def test_a_local_branch_behind_origin_is_brought_up_to_it(self) -> None:
        team = Team(self, [_sized("Add login", "size-1", "--project", "acme-api")])
        report = json.loads(team.ok("claim", "1", "--as", "kyle.w1", "--json").stdout)
        worktree, branch = Path(report["worktree"]), report["branch"]
        _git(worktree, "commit", "-q", "--allow-empty", "-m", "first")
        _git(worktree, "push", "-q", "-u", "origin", "HEAD")
        elsewhere = team.boards.root / "elsewhere"
        _git(team.boards.root, "clone", "-q", "-b", branch, str(team.boards.root / "origins" / "acme" / "api.git"), str(elsewhere))
        _git(elsewhere, "commit", "-q", "--allow-empty", "-m", "second, pushed from another machine")
        _git(elsewhere, "push", "-q", "origin", branch)
        team.ok("release", "1", "--as", "kyle.w1")
        _git(team.api, "worktree", "remove", "--force", str(worktree))
        team.ok("claim", "1", "--as", "kyle.w2")
        self.assertEqual(_git(worktree, "log", "-1", "--format=%s"), "second, pushed from another machine")


@needs_backlog
class InterruptedCommandTest(unittest.TestCase):
    """I1: an interrupted asdlc command never wedges the board clone, and never pushes a phantom claim later."""

    def setUp(self) -> None:
        self.team = Team(self, [_sized("T1", "size-2", "--project", "acme-api"), _sized("T2", "size-2", "--project", "acme-api")])
        self.theirs = self.team.boards.clone("theirs")

    def interrupted_claim(self, signal_number: int) -> None:
        """kyle.w1's claim, stopped after backlog committed it and before the push."""
        root = self.team.boards.root
        flag, wrapper = root / "committed", root / "slow-backlog"
        wrapper.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "--version" ]; then exec "$REAL_BACKLOG" "$@"; fi\n'
            '"$REAL_BACKLOG" "$@"; status=$?\n'
            'case "$*" in *"task edit"*"In Progress"*) : > "$FLAG"; sleep 60;; esac\n'
            "exit $status\n"
        )
        wrapper.chmod(0o755)
        env = {**os.environ, **ISOLATED, **NO_MACHINE_CONFIG, **self.team.machine, **as_engineer("kyle"),
               "ASDLC_BACKLOG": str(wrapper), "REAL_BACKLOG": BACKLOG, "FLAG": str(flag)}
        claim = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "asdlc"), "--board", str(self.team.board), "claim", "1", "--as", "kyle.w1"],
                                 cwd=root, env=env, start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(600):
            if flag.exists() or claim.poll() is not None:
                break
            time.sleep(0.05)
        if not flag.exists():
            self.fail(f"the claim never reached its push: {claim.communicate()}")
        os.killpg(claim.pid, signal_number)
        claim.communicate(timeout=60)

    def ann_claims_it_on_her_clone(self) -> None:
        done = _asdlc("--board", str(self.theirs), "claim", "1", "--as", "ann.w1", env=self.team.machine, engineer="ann")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_terminated_claim_is_dropped_at_once(self) -> None:
        self.interrupted_claim(signal.SIGTERM)
        self.assertEqual(_git(self.team.board, "rev-list", "--count", "origin/main..HEAD"), "0")
        self.assertEqual(_git(self.team.board, "status", "--porcelain", "--untracked-files=no"), "")
        self.ann_claims_it_on_her_clone()
        done = self.team.ok("next", "--as", "kyle.w2", "--json")
        self.assertEqual(json.loads(done.stdout)["task"], "TASK-2")
        self.assertEqual(self.team.task("TASK-1").assignees, ("@ann.w1",))

    def test_a_killed_claim_is_dropped_by_the_next_command_never_pushed(self) -> None:
        self.interrupted_claim(signal.SIGKILL)
        self.assertEqual(_git(self.team.board, "rev-list", "--count", "origin/main..HEAD"), "1", "the kill left the claim unpushed")
        self.ann_claims_it_on_her_clone()
        done = self.team.ok("next", "--as", "kyle.w2", "--json")
        self.assertIn("interrupted", done.stderr)
        self.assertEqual(json.loads(done.stdout)["task"], "TASK-2")
        self.assertEqual(self.team.task("TASK-1").assignees, ("@ann.w1",))
        self.assertEqual(_git(self.team.board, "rev-list", "--count", "origin/main..HEAD"), "0")

    def test_recovery_keeps_a_persons_uncommitted_edit(self) -> None:
        """Second review, Minor 1: recovering from a kill restores only backlog/, and names anything else that is dirty."""
        self.interrupted_claim(signal.SIGKILL)
        edited = self.team.board / "devs" / "example.yaml"
        edited.write_text(edited.read_text() + "# kyle's edit\n")
        refused = self.team.run("next", "--as", "kyle.w2")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("devs/example.yaml", refused.stderr)
        self.assertIn("# kyle's edit", edited.read_text())
        _git(self.team.board, "checkout", "--", "devs/example.yaml")
        self.assertEqual(json.loads(self.team.ok("next", "--as", "kyle.w2", "--json").stdout)["claimed"], True)

    def test_a_persons_commit_on_an_interrupted_change_is_kept(self) -> None:
        """Second review, Minor 1: only trailer-marked commits that touch nothing outside backlog/ count as asdlc's own."""
        self.interrupted_claim(signal.SIGKILL)
        edited = self.team.board / "devs" / "example.yaml"
        edited.write_text(edited.read_text() + "# kyle's edit\n")
        _git(self.team.board, "commit", "-qam", "kyle prefs")
        refused = self.team.run("mine", "--as", "kyle")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("kyle prefs", refused.stderr)
        self.assertIn("cherry-pick", refused.stderr)
        self.assertIn("kyle prefs", _git(self.team.board, "log", "--format=%s", "origin/main..HEAD"))
        self.assertIn("# kyle's edit", edited.read_text())

    def test_a_commit_asdlc_did_not_make_is_never_pushed_or_dropped(self) -> None:
        (self.team.board / "devs").mkdir(exist_ok=True)
        (self.team.board / "devs" / "kyle.yaml").write_text("name: kyle\nreview: true\n")
        _git(self.team.board, "add", "devs")
        _git(self.team.board, "commit", "-qm", "Add kyle's preferences")
        done = self.team.run("mine", "--as", "kyle")
        self.assertEqual(done.returncode, 1)
        self.assertIn("Add kyle's preferences", done.stderr)
        self.assertIn("asdlc didn't make", done.stderr)
        self.assertEqual(_git(self.team.board, "rev-list", "--count", "origin/main..HEAD"), "1")
        self.assertNotIn("devs/kyle.yaml", _git(self.team.boards.origin, "ls-tree", "-r", "--name-only", "main"))

    def test_the_lock_wait_is_well_under_two_minutes_and_says_who_holds_it(self) -> None:
        self.assertLessEqual(asdlc.LOCK_WAIT_SECONDS, 60, "a Bash call's two-minute timeout must not kill a command waiting for the lock")
        import fcntl
        board = asdlc.Board(self.team.board, frozendict(asdlc.hooks_off({**os.environ, **ISOLATED})))
        with (self.team.board / ".git" / "asdlc.lock").open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            waited, asdlc.LOCK_WAIT_SECONDS = asdlc.LOCK_WAIT_SECONDS, 0.2
            try:
                with self.assertRaisesRegex(asdlc.AsdlcError, "another asdlc command holds the lock"):
                    with asdlc._locked(board):
                        pass
            finally:
                asdlc.LOCK_WAIT_SECONDS = waited


@needs_backlog
class PlanApprovalTest(unittest.TestCase):
    """I7: a size 2+ task is built and finished only after a person's recorded approval of its plan."""

    def test_building_waits_for_asdlc_approve(self) -> None:
        team = Team(self, [_sized("Rate limit", "size-2", "--project", "acme-api"), _sized("Typo", "size-1", "--project", "acme-api")])
        worktree = Path(json.loads(team.ok("claim", "1", "--as", "kyle.w1", "--json").stdout)["worktree"])
        check = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "true", cwd=worktree, env=team.machine, engineer="kyle")
        self.assertEqual(check.returncode, 1)
        self.assertIn("asdlc approve TASK-1", check.stderr)
        early = team.run("finish", "1", "--as", "kyle.w1", "--notes", "built")
        self.assertEqual(early.returncode, 1)
        self.assertIn("asdlc approve TASK-1", early.stderr)
        no_plan = team.run("approve", "1")
        self.assertEqual(no_plan.returncode, 1)
        self.assertIn("no plan", no_plan.stderr)
        team.ok("board", "task", "edit", "1", "--plan", "Files: limiter.py. Proof: the tests.")
        self.assertIn("approved the plan of TASK-1", team.ok("approve", "1").stdout)
        self.assertEqual(team.task("TASK-1").plan_approved_by, "kyle")
        self.assertIn("Plan approved by @kyle", team.text("TASK-1"))
        ok = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "true", cwd=worktree, env=team.machine, engineer="kyle")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        team.ok("finish", "1", "--as", "kyle.w1", "--notes", "built")
        team.ok("claim", "2", "--as", "kyle.w2")
        team.ok("finish", "2", "--as", "kyle.w2", "--notes", "size-1: no approval needed")


@needs_backlog
class RecordCheckWhereTest(unittest.TestCase):
    """I9: a recorded check ran in the task's own worktree, by its holder, and says where."""

    def test_only_in_the_tasks_worktree(self) -> None:
        team = Team(self, [_sized("One", "size-1", "--project", "acme-api"), _sized("Two", "size-1", "--project", "acme-api")])
        one = Path(json.loads(team.ok("claim", "1", "--as", "kyle.w1", "--json").stdout)["worktree"])
        two = Path(json.loads(team.ok("claim", "2", "--as", "kyle.w2", "--json").stdout)["worktree"])
        ran = team.boards.root / "ran"
        for where, says in ((team.board, "is not a task's worktree"), (team.api, "is not a task's worktree"), (two, "the worktree of TASK-2, not TASK-1")):
            with self.subTest(where=where):
                done = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "touch", str(ran), cwd=where, env=team.machine, engineer="kyle")
                self.assertEqual(done.returncode, 1)
                self.assertIn(says, done.stderr)
                self.assertFalse(ran.exists())
        (one / "wip.py").write_text("x\n")
        done = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "true", cwd=one, env=team.machine, engineer="kyle")
        self.assertEqual(done.returncode, 0, done.stderr)
        head = _git(one, "rev-parse", "HEAD")[:12]
        self.assertIn(f"Check passed: `true` exited 0 at", team.text("TASK-1"))
        self.assertIn(f"in {one} on task-1-one at {head} with uncommitted changes", team.text("TASK-1"))


@needs_backlog
class RecordCheckInTest(unittest.TestCase):
    """The first eval run: both workers ran record-check from the tasks clone, were refused, and fell back on `cd <worktree> && ...`,
    which Claude Code prompts for when the line also runs git. `--in <worktree>` lets them stay where they are."""

    def test_record_check_takes_the_worktree_with_in_from_the_tasks_clone(self) -> None:
        team = Team(self, [_sized("One", "size-1", "--project", "acme-api"), _sized("Two", "size-1", "--project", "acme-api")])
        one = Path(json.loads(team.ok("claim", "1", "--as", "kyle.w1", "--json").stdout)["worktree"])
        two = Path(json.loads(team.ok("claim", "2", "--as", "kyle.w2", "--json").stdout)["worktree"])
        for words in (("TASK-1", "--in", str(one), "--as", "kyle.w1"), ("--in", str(one), "TASK-1", "--as", "kyle.w1"),
                      ("TASK-1", "--as", "kyle.w1", f"--in={one}")):
            with self.subTest(words=words):
                done = _asdlc("record-check", *words, "--", "sh", "-c", "pwd > ran", cwd=team.board, env=team.machine, engineer="kyle")
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual((one / "ran").read_text().strip(), str(one.resolve()), "the check ran in the worktree")
        self.assertIn(f"in {one.resolve()} on task-1-one", team.text("TASK-1"))
        before = _asdlc("--in", str(one), "record-check", "TASK-1", "--as", "kyle.w1", "--", "true", cwd=team.board, env=team.machine, engineer="kyle")
        self.assertEqual(before.returncode, 0, before.stderr)
        wrong = _asdlc("record-check", "TASK-1", "--in", str(two), "--as", "kyle.w1", "--", "touch", "ran-two", cwd=team.board, env=team.machine, engineer="kyle")
        self.assertEqual(wrong.returncode, 1)
        self.assertIn("the worktree of TASK-2, not TASK-1", wrong.stderr)
        self.assertFalse((two / "ran-two").exists())
        missing = _asdlc("record-check", "TASK-1", "--in", str(team.boards.root / "nowhere"), "--as", "kyle.w1", "--", "true",
                         cwd=team.board, env=team.machine, engineer="kyle")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("is not a folder", missing.stderr)

    def test_the_refusal_outside_a_worktree_names_in(self) -> None:
        team = Team(self, [_sized("One", "size-1", "--project", "acme-api")])
        worktree = json.loads(team.ok("claim", "1", "--as", "kyle.w1", "--json").stdout)["worktree"]
        done = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "true", cwd=team.board, env=team.machine, engineer="kyle")
        self.assertEqual(done.returncode, 1)
        self.assertIn("--in <worktree>", done.stderr)
        self.assertTrue(worktree)

    def test_in_is_every_commands_working_folder(self) -> None:
        team = Team(self, [_sized("One", "size-1", "--project", "acme-api")])
        elsewhere = team.boards.root / "elsewhere"
        elsewhere.mkdir()
        lost = json.loads(_asdlc("whoami", "--json", cwd=elsewhere, env=team.machine, engineer="kyle").stdout)
        self.assertIsNone(lost["board"], "no board from an unrelated folder")
        for words in (("--in", str(team.board), "whoami", "--json"), ("whoami", "--in", str(team.board), "--json"),
                      ("--in", str(team.api), "whoami", "--json")):
            with self.subTest(words=words):
                done = _asdlc(*words, cwd=elsewhere, env=team.machine, engineer="kyle")
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(Path(json.loads(done.stdout)["board"]).resolve(), team.board.resolve())
        listed = _asdlc("--in", str(team.board), "board", "task", "list", "--plain", cwd=elsewhere, env=team.machine, engineer="kyle")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("One", listed.stdout)

    def test_a_claim_says_where_to_open_a_pull_request(self) -> None:
        team = Team(self, [_sized("One", "size-1", "--project", "acme-api")])
        self.assertIsNone(json.loads(team.ok("claim", "1", "--as", "kyle.w1", "--json").stdout)["github"], "no gh here, so no pull request")
        self.assertEqual(asdlc.pull_request_repo("/usr/bin/gh", "git@github.com:acme/api.git"), "acme/api")
        self.assertIsNone(asdlc.pull_request_repo("", "git@github.com:acme/api.git"), "gh missing")
        self.assertIsNone(asdlc.pull_request_repo("/usr/bin/gh", "/srv/origins/acme/api.git"), "not on GitHub")
        self.assertIsNone(asdlc.pull_request_repo("/usr/bin/gh", None), "no origin")


@needs_backlog
class WorkerTrailerTest(unittest.TestCase):
    """A check on a sent-back task says whether every commit since the review carries the worker trailer, and stats counts it."""

    def test_record_check_counts_the_commits_since_the_review(self) -> None:
        team = Team(self, [_sized("Add login", "size-1", "--project", "acme-api")])
        worktree = Path(json.loads(team.ok("claim", "1", "--as", "kyle.w1", "--json").stdout)["worktree"])
        _git(worktree, "commit", "-q", "--allow-empty", "-m", "Build it", "--trailer", "Asdlc-Worker: kyle.w1")
        _git(worktree, "push", "-q", "-u", "origin", "HEAD")
        first = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "true", cwd=worktree, env=team.machine, engineer="kyle")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertNotIn("Commits since the review", team.text("TASK-1"), "only a sent-back task's checks count them")
        team.ok("finish", "1", "--as", "kyle.w1", "--notes", "built")
        team.ok("review-next", "--as", "ann.r1", engineer="ann")
        team.ok("review-done", "1", "--as", "ann.r1", "--verdict", "changes", *CHANGES, "--policy", "testing", "--notes", "[Bugs, Important] x", engineer="ann")
        _git(worktree, "commit", "-q", "--allow-empty", "-m", "Fix it", "--trailer", "Asdlc-Worker: kyle.w1")
        _git(worktree, "commit", "-q", "--allow-empty", "-m", "A person's fix")
        done = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "true", cwd=worktree, env=team.machine, engineer="kyle")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Commits since the review: 2, 1 without the Asdlc-Worker trailer.", team.text("TASK-1"))
        _git(worktree, "push", "-q", "origin", "HEAD")
        team.ok("finish", "1", "--as", "kyle.w1", "--notes", "fixed")
        report = json.loads(team.ok("stats", "--stage", "deploy", "--json").stdout)
        self.assertEqual(list(report["stages"]), ["deploy"])
        deploy = report["stages"]["deploy"]["metrics"]
        self.assertEqual((deploy["worker_only_fixes"]["count"], deploy["worker_only_fixes"]["of"]), (0, 1))
        self.assertEqual(deploy["findings_by_policy"]["by_policy"].keys(), {"testing"})
        self.assertEqual(deploy["defects_caught"]["important"], 1)
        self.assertTrue((team.board / ".asdlc" / "stats" / "history.json").is_file(), "the parsed history is cached in the board clone")
        self.assertEqual(_git(team.board, "status", "--porcelain"), "", "the cache is ignored")
        again = json.loads(team.ok("stats", "--stage", "deploy", "--json").stdout)
        self.assertEqual(again["stages"]["deploy"]["metrics"]["worker_only_fixes"], deploy["worker_only_fixes"], "the cache reads the same")


@needs_backlog
class MergeTimeTest(unittest.TestCase):
    def test_gh_gives_the_merge_time_and_it_is_cached(self) -> None:
        team = Team(self, [_sized("Add login", "size-2", "--project", "acme-api")])
        team.ok("claim", "1", "--as", "kyle.w1")
        team.ok("board", "task", "edit", "TASK-1", "--plan", "Files: login.py. Proof: it parses.")
        team.ok("approve", "TASK-1")
        team.ok("finish", "1", "--as", "kyle.w1", "--pr", "https://github.com/acme/api/pull/9", "--notes", "built")
        team.ok("board", "task", "edit", "TASK-1", "-s", "Done")
        asked = team.boards.root / "asked"
        gh = team.boards.root / "gh"
        gh.write_text(f'#!/bin/sh\necho "$@" >> {asked}\necho \'{{"mergedAt": "2999-01-01T00:00:00Z"}}\'\n')
        gh.chmod(0o755)
        merged = json.loads(team.ok("stats", "--stage", "build", "--json", env={"ASDLC_GH": str(gh)}).stdout)
        found = merged["stages"]["build"]["metrics"]["approval_to_merge"]
        self.assertEqual(found["sources"], {"gh": 1})
        self.assertEqual(asked.read_text(), "pr view https://github.com/acme/api/pull/9 --json mergedAt\n")
        cached = json.loads(team.ok("stats", "--stage", "build", "--json").stdout)["stages"]["build"]["metrics"]["approval_to_merge"]
        self.assertEqual((cached["sources"], cached["median"]), ({"gh": 1}, found["median"]), "a known merge time is kept, without asking again")
        self.assertEqual(len(asked.read_text().splitlines()), 1)


@needs_backlog
class IntentStartedTest(unittest.TestCase):
    def test_records_when_the_conversation_began_once(self) -> None:
        team = Team(self, [_sized("A task", "size-1", "--project", "acme-api")])
        team.ok("board", "task", "create", "Faster logins", "--draft", "--type", "intent")
        team.ok("board", "task", "create", "Not an intent", "--draft", "--type", "task")
        start = (datetime.now(UTC) - timedelta(minutes=20)).replace(microsecond=0)
        done = team.ok("intent-started", "DRAFT-1", "--at", start.isoformat())
        self.assertIn(f"DRAFT-1: the conversation began at {start.isoformat()}", done.stdout)
        self.assertIn(f"asdlc_intent_started: '{start.isoformat()}'", team.text("DRAFT-1"))
        self.assertIn("already recorded", team.ok("intent-started", "1", "--at", start.isoformat()).stdout)
        for args, says in ((("DRAFT-1", "--at", (start + timedelta(minutes=1)).isoformat()), "asdlc doesn't change it"),
                           (("DRAFT-2",), "not an intent"), (("TASK-1",), "not a draft on the board"),
                           (("DRAFT-1", "--at", "2999-01-01T00:00:00+00:00"), "in the future")):
            with self.subTest(args=args):
                refused = team.run("intent-started", *args)
                self.assertEqual(refused.returncode, 1)
                self.assertIn(says, refused.stderr)
        stats = json.loads(team.ok("stats", "--stage", "plan", "--json").stdout)["stages"]["plan"]["metrics"]
        self.assertEqual(stats["conversation_to_intent"]["count"], 1)
        self.assertGreaterEqual(stats["conversation_to_intent"]["median"], 20 * 60 - 5)


@needs_backlog
class AcceptSubtreeTest(unittest.TestCase):
    """I5: accept promotes the whole draft subtree under an intent, re-parenting each level."""

    def test_three_levels(self) -> None:
        team = Team(self, [])
        team.ok("board", "task", "create", "Checkout", "--draft", "--type", "intent")
        team.ok("board", "task", "create", "API part", "--draft", "-p", "DRAFT-1", "--project", "acme-api", "-l", "size-3")
        team.ok("board", "task", "create", "API sub", "--draft", "-p", "DRAFT-2", "--project", "acme-api", "-l", "size-1")
        team.ok("board", "task", "create", "API sub two", "--draft", "-p", "DRAFT-2", "--project", "acme-api", "-l", "size-1", "--dep", "DRAFT-3")
        team.ok("board", "task", "create", "Other idea", "--draft")
        report = json.loads(team.ok("accept", "DRAFT-1", "--json").stdout)
        self.assertEqual(report["accepted"], {"DRAFT-1": "TASK-1", "DRAFT-2": "TASK-1.1", "DRAFT-3": "TASK-1.1.1", "DRAFT-4": "TASK-1.1.2"})
        on_origin = team.boards.on_origin()
        self.assertEqual({tid: on_origin[tid][0].parent for tid in ("TASK-1.1", "TASK-1.1.1", "TASK-1.1.2")},
                         {"TASK-1.1": "TASK-1", "TASK-1.1.1": "TASK-1.1", "TASK-1.1.2": "TASK-1.1"})
        self.assertEqual(on_origin["TASK-1.1.2"][0].dependencies, ("TASK-1.1.1",))
        self.assertEqual({tid: on_origin[tid][0].accepted_from for tid in ("TASK-1", "TASK-1.1", "TASK-1.1.1")},
                         {"TASK-1": "DRAFT-1", "TASK-1.1": "DRAFT-2", "TASK-1.1.1": "DRAFT-3"})
        drafts = [path.name for path in (team.boards.clone("after") / "backlog" / "drafts").glob("*.md")]
        self.assertEqual(len(drafts), 1, drafts)
        self.assertIn("Other-idea", drafts[0])


@needs_backlog
class AcceptedIdsTest(unittest.TestCase):
    """I4: after accept, a lead's old draft id still finds its task, and never an unrelated draft that reuses the id."""

    def test_old_draft_ids_resolve_to_the_accepted_task(self) -> None:
        team = Team(self, [])
        team.ok("board", "task", "create", "Intent A", "--draft", "--type", "intent")
        team.ok("board", "task", "create", "A1", "--draft", "-p", "DRAFT-1", "--project", "acme-api", "-l", "size-2")
        team.ok("accept", "DRAFT-1")
        self.assertIn("DRAFT-1 -> TASK-1", team.text("TASK-1"))
        self.assertIn("DRAFT-2 -> TASK-1.1", team.text("TASK-1"))
        team.ok("claim", "TASK-1.1", "--as", "kyle.w1")
        team.ok("board", "task", "create", "Intent B", "--draft", "--type", "intent")
        team.ok("board", "task", "create", "B1", "--draft", "-p", "DRAFT-1", "--project", "acme-api", "-l", "size-2")
        team.ok("release", "DRAFT-2", "--as", "kyle.w1")
        self.assertEqual(team.task("TASK-1.1").status, "To Do")
        self.assertEqual(asdlc.task_from("x", team.text("DRAFT-2")).title, "B1")


@needs_backlog
class ReviewSlotTest(unittest.TestCase):
    """I2: with review on, asdlc next leaves a slot free for a review waiting for this engineer, so reviews never starve."""

    def test_next_leaves_a_slot_for_a_waiting_review(self) -> None:
        team = Team(self, [_sized(f"T{n}", "size-1", "--project", "acme-api") for n in (1, 2, 3, 4)],
                    files={"devs/kyle.yaml": "name: kyle\nworkers: 2\nreview: true\n", "devs/lee.yaml": "name: lee\nworkers: 1\nreview: false\n"})
        team.ok("claim", "1", "--as", "ann.w1", engineer="ann")
        team.ok("finish", "1", "--as", "ann.w1", "--notes", "built", engineer="ann")
        first = json.loads(team.ok("next", "--as", "kyle.w1", "--json").stdout)
        self.assertEqual(first["task"], "TASK-2")
        held = json.loads(team.ok("next", "--as", "kyle.w2", "--json").stdout)
        self.assertFalse(held["claimed"])
        self.assertIn("leaves one slot for the review of TASK-1", held["reason"])
        mine = json.loads(team.ok("mine", "--as", "kyle", "--json").stdout)
        self.assertEqual((mine["reviews_waiting"], mine["slot_left_for_review"]), (["TASK-1"], True))
        other = json.loads(team.ok("next", "--as", "lee.w1", "--json", engineer="lee").stdout)
        self.assertEqual(other["task"], "TASK-3", "an engineer who doesn't review keeps every slot for building")
        self.assertEqual(json.loads(team.ok("review-next", "--as", "kyle.r1", "--json").stdout)["task"], "TASK-1")
        none = json.loads(team.ok("next", "--as", "kyle.w2", "--json").stdout)
        self.assertIn("the cap in devs/kyle.yaml (2)", none["reason"])


@needs_backlog
class ReviewPolicyTest(unittest.TestCase):
    """I3: a review claim names the team's review policy and the repository plugin's own, from the tasks repository."""

    def test_the_claim_names_the_policies_that_exist(self) -> None:
        team = Team(self, [_sized("Rate limit", "size-1", "--project", "acme-api")], files={"plugins/acme-api/review.md": "# acme-api review\n"})
        team.ok("claim", "1", "--as", "ann.w1", engineer="ann")
        team.ok("finish", "1", "--as", "ann.w1", "--notes", "built", engineer="ann")
        claimed = json.loads(team.ok("review-next", "--as", "kyle.r1", "--json").stdout)
        self.assertEqual(claimed["policies"], [str(team.board / "plugins" / "team" / "review.md"), str(team.board / "plugins" / "acme-api" / "review.md")])
        self.assertNotIn("REVIEW.md", claimed["route"])


@needs_backlog
class SameWorkerNameTest(unittest.TestCase):
    """M4: a claim for a task already held under the same worker name is refused, since another session may be using that name."""

    def test_refused(self) -> None:
        team = Team(self, [_sized("One", "size-1", "--project", "acme-api")])
        team.ok("claim", "1", "--as", "kyle.w1")
        again = team.run("claim", "1", "--as", "kyle.w1")
        self.assertEqual(again.returncode, 1)
        self.assertIn("already claimed by @kyle.w1", again.stderr)
        self.assertIn("another session may be using that name", again.stderr)


@needs_backlog
class PermissionsCommandTest(unittest.TestCase):
    """I10 and the second review's Important 3: --write merges the rules into the tasks clone's own local settings, after a backup, atomically."""

    def test_print_and_write(self) -> None:
        team = Team(self, [], files={"plugins/acme-api/commands.toml": '[test]\nrun = "make test"\nverified = 2026-10-20\n'
                                                                       '[lint]\nrun = "./lint.sh | tee out"\nverified = 2026-10-20\n'})
        config = team.boards.root / "claude-config"
        env = {"CLAUDE_CONFIG_DIR": str(config), "ASDLC_CLAUDE": "/bin/false"}
        target = team.board / ".claude" / "settings.local.json"
        shown = json.loads(team.ok("permissions", "--json", env=env).stdout)
        self.assertEqual(shown["settings"], str(target))
        self.assertIn("Bash(make test)", shown["allow"])
        self.assertEqual(shown["skipped"][0]["command"], "lint")
        self.assertIn(f"{team.api}.worktrees", shown["directories"])
        self.assertFalse(target.exists(), "printing writes nothing")
        self.assertIn("lint", team.ok("permissions", env=env).stdout)
        target.parent.mkdir()
        target.write_text(json.dumps({"theme": "dark", "env": {"X": "\u00e9"}, "permissions": {"allow": ["Bash(git status)"]}}, ensure_ascii=False))
        self.assertFalse(Path(f"{team.api}.worktrees").exists(), "no claim yet")
        written = team.ok("permissions", "--write", env=env)
        self.assertIn(str(target), written.stdout)
        for folder in shown["directories"]:
            with self.subTest(folder=folder):
                self.assertTrue(Path(folder).is_dir(), "the second eval run: a worktree folder missing when the session started wasn't readable by its workers")
        result = json.loads(target.read_text())
        self.assertEqual((result["theme"], result["env"]["X"], result["permissions"]["allow"][0]), ("dark", "\u00e9", "Bash(git status)"))
        self.assertIn("\u00e9", target.read_text(), "non-ASCII text is kept as it was written")
        self.assertIn("Bash(make test)", result["permissions"]["allow"])
        self.assertFalse((config / "settings.json").exists(), "never the user's settings")
        backups = list(target.parent.glob("settings.local.json.*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(sorted(p.name for p in target.parent.iterdir()), sorted(["settings.local.json", backups[0].name]), "no temporary file left")
        self.assertIn(".claude/settings.local.json", (team.board / ".git" / "info" / "exclude").read_text())
        self.assertEqual(_git(team.board, "status", "--porcelain"), "")
        self.assertIn("nothing to add", team.ok("permissions", "--write", env=env).stdout)
        for text, says in (("{not json", "not valid JSON"), ('{"permissions": null}', "permissions")):
            with self.subTest(text=text):
                target.write_text(text)
                refused = team.run("permissions", "--write", env=env)
                self.assertEqual(refused.returncode, 1)
                self.assertIn(says, refused.stderr)
                self.assertNotIn("Traceback", refused.stderr)
                self.assertEqual(target.read_text(), text)


# --- the second review round's experiments, as regression tests ----------------------


@needs_backlog
class ApprovedPlanTest(unittest.TestCase):
    """Second review, Important 4: an approval holds only for the plan text and the size it approved."""

    def test_a_changed_plan_or_size_needs_approval_again(self) -> None:
        team = Team(self, [_sized("Big", "size-3", "--project", "acme-api"), _sized("Other", "size-2", "--project", "acme-api")])
        worktree = Path(json.loads(team.ok("claim", "1", "--as", "kyle.w1", "--json").stdout)["worktree"])
        team.ok("board", "task", "edit", "1", "--plan", "1. small safe change")
        approved = team.ok("approve", "1").stdout
        self.assertIn("1. small safe change", approved, "approve shows the plan it approves")
        digest = asdlc.plan_digest("1. small safe change")
        self.assertIn(digest, approved)
        self.assertEqual(json.loads(team.ok("mine", "--as", "kyle", "--json").stdout)["tasks"][0]["plan_hash"], digest)
        team.ok("board", "task", "edit", "1", "--plan", "1. rewrite the auth layer")
        check = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "true", cwd=worktree, env=team.machine, engineer="kyle")
        self.assertEqual(check.returncode, 1)
        self.assertIn("changed since @kyle approved it", check.stderr)
        self.assertIn("asdlc approve TASK-1", check.stderr)
        self.assertEqual(team.run("finish", "1", "--as", "kyle.w1", "--notes", "built").returncode, 1)
        team.ok("approve", "1")
        ok = _asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "true", cwd=worktree, env=team.machine, engineer="kyle")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        team.ok("board", "task", "edit", "1", "--remove-label", "size-3", "--add-label", "size-1")
        resized = team.run("finish", "1", "--as", "kyle.w1", "--notes", "built")
        self.assertEqual(resized.returncode, 1)
        self.assertIn("size-3", resized.stderr)
        self.assertIn("size-1", resized.stderr)
        # The orchestrator passes the hash of the plan it showed the person.
        team.ok("claim", "2", "--as", "kyle.w2")
        team.ok("board", "task", "edit", "2", "--plan", "1. the plan shown")
        shown = asdlc.plan_digest("1. the plan shown")
        team.ok("board", "task", "edit", "2", "--plan", "1. a plan rewritten meanwhile")
        stale = team.run("approve", "2", "--plan-hash", shown)
        self.assertEqual(stale.returncode, 1)
        self.assertIn("changed since it was shown", stale.stderr)
        self.assertEqual(team.task("TASK-2").plan_approved_by, "")
        team.ok("approve", "2", "--plan-hash", asdlc.plan_digest("1. a plan rewritten meanwhile"))


class OldBoardPolicyTest(unittest.TestCase):
    """Second review, Minor 7: a board made before the team review policy existed is flagged, and its reviews aren't claimed."""

    def test_doctor_flags_a_missing_team_review_policy(self) -> None:
        (found,) = [f for f in asdlc.diagnose(facts(team_review_policy=False)) if f.area == "review policy"]
        self.assertEqual(found.level, asdlc.Level.WARN)
        self.assertIn("asdlc init-board /home/kyle/tasks", found.message)
        self.assertFalse([f for f in asdlc.diagnose(facts()) if f.area == "review policy" and f.level is not asdlc.Level.PASS])

    @needs_backlog
    def test_review_next_refuses_without_a_policy(self) -> None:
        team = Team(self, [_sized("Small", "size-1", "--project", "acme-api")])
        team.ok("claim", "1", "--as", "ann.w1", engineer="ann")
        team.ok("finish", "1", "--as", "ann.w1", "--notes", "built", engineer="ann")
        _git(team.board, "rm", "-q", "plugins/team/review.md")
        _git(team.board, "commit", "-qm", "An older board")
        _git(team.board, "push", "-q", "origin", "main")
        refused = team.run("review-next", "--as", "kyle.r1")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("plugins/team/review.md", refused.stderr)
        self.assertIn("asdlc init-board", refused.stderr)
        self.assertEqual(team.task("TASK-1").reviewer, "")


# --- the third review round ----------------------------------------------------------


@needs_backlog
class InitBoardBehindTest(unittest.TestCase):
    """Third review, Minor 1: re-running init-board on a clone that is behind origin goes through the board's own
    transaction (catch up, commit with the trailer, push), so the clone is never left with a commit asdlc refuses."""

    def test_missing_scaffolding_is_pushed_from_a_clone_behind_origin(self) -> None:
        boards = Boards(self, [])
        kyle, ann = boards.clone("kyle"), boards.clone("ann")
        _git(kyle, "rm", "-q", "plugins/team/review.md")
        _git(kyle, "commit", "-qm", "An older board")
        _git(kyle, "push", "-q", "origin", "main")
        self.assertEqual(_asdlc("--board", str(ann), "board", "task", "create", *_sized("T1")).returncode, 0)
        done = _asdlc("init-board", str(kyle))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(_git(kyle, "rev-list", "--count", "origin/main..HEAD"), "0", "nothing left unpushed")
        self.assertIn("plugins/team/review.md", _git(boards.origin, "ls-tree", "-r", "--name-only", "main"))
        self.assertIn("Asdlc-Transaction:", _git(boards.origin, "log", "-1", "--format=%B", "main"))
        self.assertEqual(sorted(boards.on_origin()), ["TASK-1"], "the other clone's task is kept")
        listed = _asdlc("--board", str(kyle), "board", "task", "list", "--plain")
        self.assertEqual(listed.returncode, 0, listed.stderr)

    def test_the_foreign_commit_refusal_says_to_rebase_before_pushing(self) -> None:
        refusal = asdlc.foreign_refusal(Path("/b"), [asdlc.Unpushed("a" * 40, "Our edit", False)])
        self.assertIn("git -C /b pull --rebase origin main", refusal)
