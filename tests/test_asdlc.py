import json
import os
import random
import re
import shutil
import stat
import subprocess
import sys
import tempfile
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
        self.assertEqual(asdlc.parse_settings(""), asdlc.Settings(timedelta(hours=2), timedelta(minutes=30)))
        self.assertEqual(asdlc.parse_settings('stale_after = "45m"\nother = 1\n').stale_after, timedelta(minutes=45))
        self.assertEqual(asdlc.parse_settings('review_fallback_after = "1h"\n').review_fallback_after, timedelta(hours=1))
        with self.assertRaisesRegex(asdlc.AsdlcError, "in quotes"):
            asdlc.parse_settings("stale_after = 2\n")
        with self.assertRaisesRegex(asdlc.AsdlcError, "not valid TOML"):
            asdlc.parse_settings("stale_after = \n")


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
        added = asdlc.with_key(self.TEXT, "asdlc_lead", "kyle.lead")
        self.assertEqual(asdlc.task_from("x", added).lead, "kyle.lead")
        replaced = asdlc.with_key(asdlc.with_key(added, "labels", "[b]"), "asdlc_lead", "ann.lead")
        self.assertEqual(asdlc.task_from("x", replaced).labels, ("b",))
        self.assertEqual(asdlc.task_from("x", replaced).lead, "ann.lead")
        self.assertIn("labels: not this", replaced)
        self.assertEqual(asdlc.with_key(added, "asdlc_lead", None), self.TEXT)
        stamped = asdlc.with_key(self.TEXT, "asdlc_heartbeat", asdlc.yaml_quoted("2026-10-22T10:00:00+00:00"))
        self.assertEqual(asdlc.task_from("x", stamped).heartbeat, "2026-10-22T10:00:00+00:00")
        with self.assertRaises(asdlc.AsdlcError):
            asdlc.with_key("no frontmatter", "a", "b")

    def test_reads_project_lead_and_heartbeat(self) -> None:
        found = asdlc.task_from("backlog/drafts/draft-1 - x.md", "---\nid: DRAFT-1\nproject: Acme-API\nasdlc_lead: '@kyle.lead'\n---\n")
        self.assertEqual((found.project, found.lead), ("acme-api", "kyle.lead"))
        self.assertTrue(asdlc.is_draft(found))


class LeadAndStalenessTest(unittest.TestCase):
    NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)

    def test_lead_of(self) -> None:
        items = (task("TASK-1", type="intent", lead="kyle.lead"), task("TASK-1.1", parent="TASK-1"), task("TASK-2"), task("TASK-3.1", parent="TASK-3"))
        self.assertEqual(asdlc.lead_of(items, "TASK-1.1"), asdlc.LeadOf("TASK-1.1", "TASK-1", "kyle.lead"))
        self.assertEqual(asdlc.lead_of(items, "TASK-1"), asdlc.LeadOf("TASK-1", "TASK-1", "kyle.lead"))
        self.assertEqual(asdlc.lead_of(items, "TASK-2"), asdlc.LeadOf("TASK-2", None, None))
        self.assertEqual(asdlc.lead_of(items, "TASK-3.1"), asdlc.LeadOf("TASK-3.1", None, None))
        with self.assertRaises(asdlc.AsdlcError):
            asdlc.lead_of(items, "TASK-9")

    def test_stale_holds(self) -> None:
        items = (
            task("TASK-1", status="In Progress", assignees=("@kyle", "@kyle.w1"), path="a"),
            task("TASK-2", status="In Progress", assignees=("@kyle.w2",), path="b"),
            task("TASK-3", status="In Progress", assignees=("@kyle",), path="c"),
            task("TASK-4", type="intent", lead="ann.lead", path="d"),
            task("TASK-5", status="In Review", assignees=("@kyle.w3",), path="e"),
        )
        old, fresh = self.NOW - timedelta(hours=3), self.NOW - timedelta(minutes=10)
        touched = {"a": old, "b": fresh, "c": old, "d": old, "e": old}
        found = asdlc.stale_holds(items, touched, self.NOW, timedelta(hours=2))
        self.assertEqual([(s.task.id, s.hold, s.holders) for s in found],
                         [("TASK-1", asdlc.Hold.CLAIM, ("@kyle.w1",)), ("TASK-4", asdlc.Hold.LEAD, ("@ann.lead",))])
        comment = asdlc.reap_comment(found[0], timedelta(hours=2))
        self.assertIn("no board update for 3h 0m, longer than stale_after (2h 0m)", comment)
        self.assertIn("stays reserved for @kyle", comment)

    def test_mine_report(self) -> None:
        items = (
            task("TASK-1", status="In Progress", assignees=("@kyle", "@kyle.w1")),
            task("TASK-2", status="In Review", assignees=("@kyle.w2",)),
            task("TASK-3", status="Done", assignees=("@kyle.w3",)),
            task("TASK-4", assignees=("@kyle",)),
            task("TASK-5", type="intent", lead="kyle.lead"),
            task("TASK-6", status="In Progress", assignees=("@ann.w1",)),
        )
        report = asdlc.mine_report(items, "kyle", asdlc.Prefs("kyle", workers=3))
        self.assertEqual((report["active"], report["workers_cap"]), (1, 3))
        self.assertEqual([(r["id"], r["workers"]) for r in report["tasks"]], [("TASK-1", ["kyle.w1"]), ("TASK-2", ["kyle.w2"])])
        self.assertEqual([r["id"] for r in report["leads"]], ["TASK-5"])
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

    def test_review_comment(self) -> None:
        text = asdlc.review_comment("kyle.r1", "same-machine", asdlc.ReviewVerdict.CHANGES, "  [Bugs, Important] x  ")
        self.assertTrue(text.startswith("Review by @kyle.r1 (same-machine): changes requested."))
        self.assertTrue(text.endswith("\n\n[Bugs, Important] x"))
        self.assertIn("stays In Review for a person to merge", asdlc.review_comment("kyle.r1", "", asdlc.ReviewVerdict.CLEAN, "No findings."))

    def test_stale_review_claims_and_the_cap(self) -> None:
        items = (
            task("TASK-1", status="In Review", assignees=("@ann.w1",), reviewer="kyle.r1", path="a"),
            task("TASK-2", status="In Progress", assignees=("@kyle.w1",), path="b"),
        )
        old = self.NOW - timedelta(hours=3)
        found = asdlc.stale_holds(items, {"a": old, "b": self.NOW}, self.NOW, timedelta(hours=2))
        self.assertEqual([(s.task.id, s.hold, s.holders) for s in found], [("TASK-1", asdlc.Hold.REVIEW, ("@kyle.r1",))])
        comment = asdlc.reap_comment(found[0], timedelta(hours=2))
        self.assertIn("the review claim held by @kyle.r1", comment)
        self.assertIn("Another reviewer may claim it", comment)
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
    )
    return asdlc.replace(healthy, **changes)


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
        self.assertIn("must be shorter than stale_after", self.only("fail", facts(settings='stale_after = "30m"\nreview_fallback_after = "30m"\n'))[0].message)
        self.assertIn("not valid TOML", self.only("fail", facts(settings="stale_after = \n"))[0].message)
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


def at(minutes: float, task_id: str = "TASK-1", **fields: object) -> object:
    return asdlc.Snapshot(T0 + timedelta(minutes=minutes), task(task_id, **fields))


class StatsTest(unittest.TestCase):
    """The pilot's numbers over fixed histories."""

    SNAPSHOTS = (
        # TASK-1: claimed at 0, In Review at 30, reviewed (changes) at 40, back at 60, reviewed clean at 70, Done at 100.
        at(0, status="To Do"),
        at(1, status="In Progress", assignees=("@ann.w1",)),
        at(30, status="In Review", assignees=("@ann.w1",)),
        at(40, status="In Review", assignees=("@ann.w1",), reviewer="kyle.r1", review_kind="cross-machine"),
        at(45, status="In Progress", assignees=("@ann.w1",), labels=("size-2", "changes-requested"), review_kind="cross-machine"),
        at(60, status="In Review", assignees=("@ann.w1",), labels=("size-2",), review_kind="cross-machine"),
        at(70, status="In Review", assignees=("@ann.w1",), reviewer="kyle.r1", review_kind="cross-machine"),
        at(75, status="In Review", assignees=("@ann.w1",), labels=("size-2", "review-passed"), review_kind="cross-machine"),
        at(100, status="Done", assignees=("@ann.w1",), labels=("size-2", "review-passed")),
        # TASK-2: size-1, claimed at 10, In Review at 20, a same-machine review at 60.
        at(5, "TASK-2", labels=("size-1",)),
        at(10, "TASK-2", status="In Progress", assignees=("@ann.w2",), labels=("size-1",)),
        at(20, "TASK-2", status="In Review", assignees=("@ann.w2",), labels=("size-1",)),
        at(60, "TASK-2", status="In Review", assignees=("@ann.w2",), labels=("size-1",), reviewer="ann.r1", review_kind="same-machine"),
        # TASK-3: in another project, claimed at 2 and still In Review with nobody reviewing.
        at(2, "TASK-3", status="In Progress", assignees=("@kyle.w1",), project="acme-web"),
        at(50, "TASK-3", status="In Review", assignees=("@kyle.w1",), project="acme-web"),
    )

    def report(self, since: datetime | None = None, events: tuple[dict[str, object], ...] = ()) -> dict[str, object]:
        by_task = asdlc.histories(self.SNAPSHOTS)
        current = (self.SNAPSHOTS[8].task, self.SNAPSHOTS[12].task, self.SNAPSHOTS[14].task)
        texts = {"TASK-2": "size-1: plan approval skipped; small because one line"}
        published = asdlc.published_plugins([(T0 + timedelta(minutes=25), "Add the app plugin"), (T0 + timedelta(minutes=90), "Update the app plugin")])
        return asdlc.board_stats(by_task, current, texts, published, events, since)

    def test_history_reads_the_transitions(self) -> None:
        h = asdlc.histories(self.SNAPSHOTS)["TASK-1"]
        minute = lambda m: T0 + timedelta(minutes=m)  # noqa: E731
        self.assertEqual(h.claims, (minute(1),))
        self.assertEqual(h.entered_review, (minute(30), minute(60)))
        self.assertEqual(h.review_claims, ((minute(40), "cross-machine"), (minute(70), "cross-machine")))
        self.assertEqual((h.changes, h.done, h.project), ((minute(45),), minute(100), "app"))

    def test_the_numbers(self) -> None:
        report = self.report()
        self.assertEqual(report["tasks"], {"claimed": 3, "in_review": 2, "done": 1})
        self.assertEqual(report["claim_to_review"], {"count": 3, "median": 29 * 60.0, "p90": 48 * 60.0})
        self.assertEqual(report["review_to_done"], {"count": 1, "median": 70 * 60.0, "p90": 70 * 60.0})
        self.assertEqual(report["review_wait"], {"count": 3, "median": 10 * 60.0, "p90": 40 * 60.0, "waiting_now": ["TASK-3"]})
        self.assertEqual(report["changes_requested"], {"reviewed_tasks": 2, "round_trips": 1, "per_task": 0.5, "by_task": {"TASK-1": 1, "TASK-2": 0}})
        self.assertEqual(report["reviews"], {"total": 3, "same_machine": 1, "share_same_machine": 1 / 3})
        self.assertEqual(report["onboardings"], [{"plugin": "app", "published": (T0 + timedelta(minutes=25)).isoformat(), "task": "TASK-2", "seconds": 15 * 60.0}])
        self.assertEqual(report["plan_approval_skipped"], [{"id": "TASK-2", "recorded": True}])

    def test_since_leaves_out_what_came_before(self) -> None:
        report = self.report(since=T0 + timedelta(minutes=55))
        self.assertEqual(report["tasks"], {"claimed": 0, "in_review": 2, "done": 1})
        self.assertEqual(report["review_wait"]["count"], 1)  # TASK-1 back In Review at 60; the others entered before 55
        self.assertEqual(report["reviews"]["total"], 2)
        self.assertEqual(report["onboardings"], [])

    def test_races_come_from_the_event_log(self) -> None:
        event = lambda m, command, outcome: {"time": (T0 + timedelta(minutes=m)).isoformat(), "command": command, "outcome": outcome}  # noqa: E731
        events = (event(1, "next", "claimed"), event(2, "next", "lost"), event(3, "next", "claimed"), event(4, "claim", "refused"),
                  event(5, "review-next", "claimed"), event(6, "lead", "lost"))
        races = self.report(events=events)["races"]
        self.assertEqual((races["claimed"], races["lost"], races["lost_per_claim"]), (2, 1, 0.5))
        self.assertEqual(races["by_command"]["lead"], {"lost": 1})
        self.assertEqual(self.report(since=T0 + timedelta(minutes=3), events=events)["races"]["claimed"], 1)

    def test_lines(self) -> None:
        lines = asdlc.stats_lines(self.report(), "/state/asdlc/events.jsonl")
        self.assertIn("tasks: 3 claimed, 2 in review now, 1 done", lines)
        self.assertIn("claim to In Review: median 29m, p90 48m (3)", lines)
        self.assertIn("review wait: median 10m, p90 40m (3); waiting now: TASK-3", lines)
        self.assertIn("changes requested: 1 round trip(s) over 2 reviewed task(s), 0.5 per task, most 1 (TASK-1)", lines)
        self.assertIn("reviews: 3, 1 same-machine (33%)", lines)
        self.assertIn("lost races per claim: - (0 lost, 0 claimed; this machine's log, /state/asdlc/events.jsonl)", lines)
        self.assertIn(f"onboarded app at {(T0 + timedelta(minutes=25)).isoformat()}, 15m after TASK-2 was claimed", lines)
        self.assertEqual(lines[-1], "plan approval skipped (size-1): TASK-2")

    def test_percentile_and_the_pieces(self) -> None:
        self.assertIsNone(asdlc.percentile([], 0.5))
        self.assertEqual(asdlc.percentile([5, 1, 3, 2, 4], 0.5), 3)
        self.assertEqual(asdlc.percentile(list(range(1, 11)), 0.9), 9)
        self.assertEqual(asdlc.percentile([7], 0.9), 7)
        self.assertEqual([asdlc._duration(v) for v in (None, 42.7, 60, 5400)], ["-", "42s", "1m", "1h 30m"])
        self.assertEqual(asdlc.published_plugins([(T0, "Add the acme-api plugin"), (T0, "Update the acme-api plugin"), (T0, "Claim TASK-1")]),
                         ((T0, "acme-api"),))
        self.assertEqual(asdlc.batch_objects(b"abc blob 3\nxyz\nmain:gone missing\ndef blob 0\n\n"), ["xyz", None, ""])


# --- the script, against real git repositories and the backlog CLI --------------------


def as_engineer(name: str) -> dict[str, str]:
    """`git config asdlc.engineer <name>` through the environment, the way one machine sets it once."""
    return {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "asdlc.engineer", "GIT_CONFIG_VALUE_0": name}


# A machine with nothing registered: tests that register pass their own XDG_CONFIG_HOME. Its
# event log goes to a folder of its own, never the real ~/.local/state.
_STATE = tempfile.TemporaryDirectory()
NO_MACHINE_CONFIG = {"XDG_CONFIG_HOME": "/nonexistent/asdlc-tests", "XDG_STATE_HOME": _STATE.name}


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
        self.assertEqual(report["claim_to_review"]["count"], 1)
        self.assertEqual(report["review_wait"]["waiting_now"], ["TASK-1"])
        self.assertEqual((report["races"]["claimed"], report["races"]["lost"]), (1, 0))
        later = _asdlc("--board", str(self.theirs), "stats", "--since", "2999-01-01", env=state)
        self.assertIn("tasks: 0 claimed, 1 in review now, 0 done", later.stdout)
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
        self.assertEqual(json.loads((path / ".asdlc-task").read_text()), {"task": "TASK-1", "worker": "agent.1", "board": str(self.board)})
        self.assertEqual(_git(path, "branch", "--show-current"), "task-1-add-the-login-page")
        self.assertEqual(_git(path, "rev-parse", "HEAD"), _git(self.code, "rev-parse", "origin/main"))
        self.assertIn(".asdlc-task", (self.code / ".git" / "info" / "exclude").read_text().splitlines())
        self.assertEqual(_git(path, "status", "--porcelain"), "")
        no_upstream = subprocess.run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "@{upstream}"], capture_output=True)
        self.assertNotEqual(no_upstream.returncode, 0, "the task branch must not track main, or a bare git push could reach it")

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
class LeadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.team = Team(self, [["Big thing", "--draft", "--type", "intent"], _sized("Plain", "size-1", "--project", "acme-api")])
        self.theirs = self.team.boards.clone("theirs")

    def test_the_first_orchestrator_leads_and_the_second_sees_it(self) -> None:
        led = json.loads(self.team.ok("lead", "draft-1", "--as", "kyle.lead", "--json").stdout)
        self.assertEqual((led["intent"], led["lead"], led["mine"]), ("DRAFT-1", "kyle.lead", True))
        self.assertIn("asdlc_lead: kyle.lead", self.team.text("DRAFT-1"))
        self.assertIn("@kyle.lead leads DRAFT-1", self.team.text("DRAFT-1"))
        other = self.team.run("lead", "DRAFT-1", "--as", "ann.lead", "--json", engineer="ann")
        self.assertEqual(other.returncode, 1)
        self.assertEqual(json.loads(other.stdout)["lead"], "kyle.lead")
        self.assertEqual(self.team.ok("lead", "DRAFT-1", "--as", "kyle.lead").stdout.strip(), "@kyle.lead already leads DRAFT-1")
        child = self.team.ok("board", "task", "create", "Child", "--draft", "-p", "DRAFT-1", "--project", "acme-api", "-l", "size-2")
        self.assertIn("DRAFT-2", child.stdout)
        self.assertEqual(json.loads(self.team.ok("lead-of", "DRAFT-2", "--json").stdout), {"task": "DRAFT-2", "intent": "DRAFT-1", "lead": "kyle.lead"})
        self.assertIn("has no parent intent", self.team.ok("lead-of", "TASK-1").stdout)

    def test_losing_the_lead_at_the_push(self) -> None:
        other = f'sed -i "s/^type: intent$/type: intent\\nasdlc_lead: ann.lead/" backlog/drafts/draft-1*.md && git commit -qam lead'
        env = _interfering_backlog(self.team.boards.root, self.theirs, other)
        done = self.team.run("lead", "DRAFT-1", "--as", "kyle.lead", env=env)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("Another orchestrator claimed the lead on DRAFT-1 first: @ann.lead", done.stdout)
        self.assertEqual(asdlc.task_from("x", self.team.text("DRAFT-1")).lead, "ann.lead")

    def test_only_an_intent_has_a_lead_and_a_lead_can_be_given_up(self) -> None:
        refused = self.team.run("lead", "TASK-1", "--as", "kyle.lead")
        self.assertIn("not an intent", refused.stderr)
        self.team.ok("lead", "DRAFT-1", "--as", "kyle.lead")
        self.assertIn("released the lead on DRAFT-1", self.team.ok("release", "DRAFT-1", "--as", "kyle.lead").stdout)
        self.assertEqual(asdlc.task_from("x", self.team.text("DRAFT-1")).lead, "")

    def test_the_board_refuses_a_draft_parent_that_isnt_a_draft(self) -> None:
        done = self.team.run("board", "task", "create", "Child", "--draft", "-p", "DRAFT-7")
        self.assertEqual(done.returncode, 1)
        self.assertIn("DRAFT-7 is not a draft on the board", done.stderr)


@needs_backlog
class HeartbeatAndReapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.team = Team(self, [
            _sized("Reserved", "size-2", "--project", "acme-api", "-a", "@kyle"),
            _sized("Open", "size-2", "--project", "acme-web"),
            ["Big thing", "--type", "intent"],
        ])
        self.team.ok("claim", "1", "--as", "kyle.w1")
        self.team.ok("claim", "2", "--as", "kyle.w2")
        self.team.ok("lead", "3", "--as", "kyle.lead")

    def later(self, **delta: float) -> str:
        return (datetime.now(UTC) + timedelta(**delta)).isoformat()

    def test_a_heartbeat_is_a_board_commit_only_the_holder_makes(self) -> None:
        self.team.ok("heartbeat", "1", "--as", "kyle.w1")
        self.assertTrue(self.team.task("TASK-1").heartbeat)
        self.assertEqual(_git(self.team.boards.origin, "log", "-1", "--format=%s", "main"), "Heartbeat TASK-1 from @kyle.w1")
        self.team.ok("heartbeat", "3", "--as", "kyle.lead")
        refused = self.team.run("heartbeat", "1", "--as", "kyle.w2")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("holds nothing to keep alive", refused.stderr)

    def test_reap_releases_stale_claims_and_leads_and_keeps_the_reservation(self) -> None:
        self.assertIn("nothing stale", self.team.ok("reap", "--now", self.later(hours=1)).stdout)
        report = json.loads(self.team.ok("reap", "--now", self.later(hours=3), "--json").stdout)
        self.assertEqual(sorted((r["id"], r["hold"]) for r in report["released"]), [("TASK-1", "claim"), ("TASK-2", "claim"), ("TASK-3", "lead")])
        first = self.team.task("TASK-1")
        self.assertEqual((first.status, first.assignees), ("To Do", ("@kyle",)))
        self.assertEqual(self.team.task("TASK-2").assignees, ())
        self.assertEqual(self.team.task("TASK-3").lead, "")
        self.assertIn("Released by asdlc reap: the claim held by @kyle.w1 had no board update for", self.team.text("TASK-1"))
        self.assertIn("It stays reserved for @kyle", self.team.text("TASK-1"))

    def test_the_timeout_comes_from_the_flag_or_the_boards_asdlc_toml(self) -> None:
        report = json.loads(self.team.ok("reap", "--older-than", "30m", "--now", self.later(hours=1), "--json").stdout)
        self.assertEqual(len(report["released"]), 3)
        team = Team(self, [_sized("Open", "size-2", "--project", "acme-web")], files={"asdlc.toml": 'stale_after = "4h"\n'})
        team.ok("claim", "1", "--as", "kyle.w1")
        self.assertIn("nothing stale (stale_after 4h 0m)", team.ok("reap", "--now", self.later(hours=3)).stdout)


@needs_backlog
class AcceptTest(unittest.TestCase):
    def test_accepts_an_intent_and_its_draft_children_in_one_commit(self) -> None:
        team = Team(self, [_sized("Already here", "size-1", "--project", "acme-api"), ["Big thing", "--draft", "--type", "intent", "--ac", "It works"]])
        team.ok("lead", "DRAFT-1", "--as", "kyle.lead")
        team.ok("board", "task", "create", "Api part", "--draft", "-p", "DRAFT-1", "--project", "acme-api", "-l", "size-2")
        team.ok("board", "task", "create", "Web part", "--draft", "-p", "DRAFT-1", "--project", "acme-web", "-l", "size-1", "--dep", "DRAFT-2", "-a", "@kyle")
        before = int(_git(team.boards.origin, "rev-list", "--count", "main"))
        report = json.loads(team.ok("accept", "DRAFT-1", "--json").stdout)
        self.assertEqual(int(_git(team.boards.origin, "rev-list", "--count", "main")), before + 1)
        self.assertEqual(report["accepted"], {"DRAFT-1": "TASK-2", "DRAFT-2": "TASK-2.1", "DRAFT-3": "TASK-2.2"})
        on_origin = team.boards.on_origin()
        intent, api, web = on_origin["TASK-2"][0], on_origin["TASK-2.1"][0], on_origin["TASK-2.2"][0]
        self.assertEqual((intent.status, intent.type, intent.lead), ("To Do", "intent", "kyle.lead"))
        self.assertEqual((api.parent, api.project, web.parent, web.dependencies, web.assignees), ("TASK-2", "acme-api", "TASK-2", ("TASK-2.1",), ("@kyle",)))
        fresh = team.boards.clone("after")
        self.assertEqual(list((fresh / "backlog" / "drafts").glob("*.md")), [])
        self.assertEqual(json.loads(team.ok("lead-of", "TASK-2.2", "--json").stdout)["lead"], "kyle.lead")
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
        self.team.ok("lead", "3", "--as", "kyle.lead")

    def test_mine(self) -> None:
        report = json.loads(self.team.ok("mine", "--as", "kyle", "--json").stdout)
        self.assertEqual((report["active"], report["workers_cap"]), (1, 3))
        self.assertEqual([(t["id"], t["workers"]) for t in report["tasks"]], [("TASK-1", ["kyle.w1"])])
        self.assertEqual([(t["id"], t["lead"]) for t in report["leads"]], [("TASK-3", "kyle.lead")])
        self.assertEqual([t["id"] for t in report["reserved"]], ["TASK-2"])
        self.assertIn("1 of 3 workers busy", self.team.ok("mine", "--as", "kyle").stdout)

    def test_record_check_notes_the_command_and_keeps_its_exit_code(self) -> None:
        worktree = self.team.boards.root / "api.worktrees" / "task-1"
        done = _asdlc("record-check", "TASK-1", "--", "sh", "-c", "echo checked; exit 3", cwd=worktree, env=self.team.machine, engineer="kyle")
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertEqual(done.stdout, "checked\n")
        text = self.team.text("TASK-1")
        self.assertIn("Check FAILED: `sh -c 'echo checked; exit 3'` exited 3", text)
        self.assertIn("checked", text)
        self.assertEqual(self.team.run("record-check", "TASK-1", "true").returncode, 1)


@needs_backlog
class ReviewCommandTest(unittest.TestCase):
    """Review claims, the same-machine fallback, verdicts and reaping, against real repositories."""

    def setUp(self) -> None:
        self.team = Team(self, [_sized("Rate limit", "size-2", "--project", "acme-api"), _sized("Second", "size-2", "--project", "acme-api")])

    def submit(self, task_id: str, worker: str = "ann.w1", team: object | None = None) -> None:
        """A worker claims the task and finishes it: branch and pull request recorded, In Review."""
        team = team or self.team
        engineer = asdlc.owner_of(worker)
        team.ok("claim", task_id, "--as", worker, engineer=engineer)
        number = task_id.rpartition("-")[2]
        team.ok("board", "task", "edit", task_id, "--add-ref", f"task-{number}-branch", "--add-ref", f"https://github.com/acme/api/pull/{number}",
                "-s", "In Review", engineer=engineer)

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
             "branch": "task-1-branch", "pull_request": "https://github.com/acme/api/pull/1", "model": "sonnet", "effort": "medium"},
        )
        on_board = self.team.task("TASK-1")
        self.assertEqual((on_board.status, on_board.assignees, on_board.reviewer, on_board.review_kind), ("In Review", ("@ann.w1",), "kyle.r1", "cross-machine"))
        self.assertIn("@kyle.r1 is reviewing TASK-1: a cross-machine review.", self.team.text("TASK-1"))
        self.assertEqual(_git(self.team.boards.origin, "log", "-1", "--format=%s", "main"), "Review TASK-1: @kyle.r1 (cross-machine)")
        self.assertEqual(self.review("kyle.r2")["task"], "TASK-2")
        none = self.team.ok("review-next", "--as", "kyle.r3")
        self.assertEqual(none.stdout.strip(), "no review available")
        self.assertIn("skipped TASK-1 is being reviewed by @kyle.r1", none.stderr)
        mine = json.loads(self.team.ok("mine", "--as", "kyle", "--json").stdout)
        self.assertEqual(([r["id"] for r in mine["reviews"]], mine["reviewing"], mine["tasks"]), (["TASK-1", "TASK-2"], 2, []))
        self.assertIn("review TASK-1\t@kyle.r1\tcross-machine", self.team.ok("mine", "--as", "kyle").stdout)

    def test_the_author_reviews_only_with_fallback_after_the_timeout(self) -> None:
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
        changes = json.loads(self.team.ok("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "changes", "--json",
                                          "--notes", "[Bugs, Important] the limit resets on every request").stdout)
        self.assertEqual((changes["status"], changes["workers"]), ("In Progress", ["ann.w1"]))
        back = self.team.task("TASK-1")
        self.assertEqual((back.status, back.assignees, back.reviewer, back.review_kind), ("In Progress", ("@ann.w1",), "", "cross-machine"))
        self.assertIn("changes-requested", back.labels)
        text = self.team.text("TASK-1")
        self.assertIn("Review by @kyle.r1 (cross-machine): changes requested.", text)
        self.assertIn("[Bugs, Important] the limit resets on every request", text)
        mine = json.loads(self.team.ok("mine", "--as", "ann", "--json", engineer="ann").stdout)
        self.assertEqual([r["id"] for r in mine["changes_requested"]], ["TASK-1"])
        self.team.ok("heartbeat", "TASK-1", "--as", "ann.w1", engineer="ann")
        self.team.ok("board", "task", "edit", "TASK-1", "--remove-label", "changes-requested", "-s", "In Review", engineer="ann")
        self.assertEqual(self.review("kyle.r1")["task"], "TASK-1")
        clean = self.team.ok("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "clean", "--notes", "No findings.")
        self.assertEqual(clean.stdout.strip(), "TASK-1 passed review by @kyle.r1 (cross-machine); it stays In Review for a person to merge")
        passed = self.team.task("TASK-1")
        self.assertEqual((passed.status, passed.reviewer, passed.labels), ("In Review", "", ("size-2", "review-passed")))
        again = self.team.ok("review-next", "--as", "kyle.r1")
        self.assertIn("skipped TASK-1 has passed review and waits for a person to merge it", again.stderr)

    def test_only_the_claiming_reviewer_finishes_the_review(self) -> None:
        self.submit("TASK-1")
        self.review("kyle.r1")
        for reviewer, says in (("lee.r1", "@kyle.r1 holds its review, so @lee.r1 can't finish it"), ("kyle.r2", "so @kyle.r2 can't finish it"),
                               ("kyle.w1", "not a reviewer's name")):
            with self.subTest(reviewer=reviewer):
                done = self.team.run("review-done", "TASK-1", "--as", reviewer, "--verdict", "clean", "--notes", "ok", engineer=asdlc.owner_of(reviewer))
                self.assertEqual(done.returncode, 1)
                self.assertIn(says, done.stderr)
        empty = self.team.run("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "clean", "--notes", " ")
        self.assertIn("say what the review found", empty.stderr)
        self.assertEqual(self.team.task("TASK-1").reviewer, "kyle.r1")
        unclaimed = self.team.run("review-done", "TASK-2", "--as", "kyle.r1", "--verdict", "clean", "--notes", "ok")
        self.assertIn("nobody holds its review", unclaimed.stderr)

    def test_reap_releases_a_stale_review_claim(self) -> None:
        self.submit("TASK-1")
        self.review("kyle.r1")
        self.team.ok("heartbeat", "TASK-1", "--as", "kyle.r1")
        self.assertIn("nothing stale", self.team.ok("reap", "--now", self.later(hours=1)).stdout)
        report = json.loads(self.team.ok("reap", "--now", self.later(hours=3), "--json").stdout)
        self.assertEqual([(r["id"], r["hold"], r["holders"]) for r in report["released"]], [("TASK-1", "review", ["kyle.r1"])])
        released = self.team.task("TASK-1")
        self.assertEqual((released.status, released.assignees, released.reviewer, released.review_kind), ("In Review", ("@ann.w1",), "", ""))
        self.assertIn("Released by asdlc reap: the review claim held by @kyle.r1", self.team.text("TASK-1"))
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


if __name__ == "__main__":
    unittest.main()
