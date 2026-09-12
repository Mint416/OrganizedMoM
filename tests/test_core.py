import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from organized_mom.agents import FamilyCoordinator
from organized_mom.app import create_app
from organized_mom.fixtures import fixture_records, load_scenario
from organized_mom.models import Record
from organized_mom.planning import find_conflicts
from organized_mom.retrieval import current_records
from organized_mom.store import Store


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "test.sqlite3")
        self.coordinator = FamilyCoordinator(self.store)
        load_scenario(self.store, "schedule_change")

    def case(self, scenario=None):
        if scenario:
            load_scenario(self.store, scenario)
        return self.coordinator.ask("Did soccer change and conflict with Chinese class?")

    def preview(self):
        c = self.case()
        b = c["planning"]["recommendations"][0]
        return self.coordinator.actions.preview(c, b)

    def clock(self, hour=12):
        return datetime.now(ZoneInfo("America/Los_Angeles")).replace(hour=hour, minute=0)

    def test_retrieval_and_revision(self):
        c = self.case()
        self.assertEqual(c["source_ids"], ["BYGA-101", "LINGO-201"])
        self.assertEqual(len(c["evidence"]), 3)
        self.assertEqual({e["record"]["source"] for e in c["evidence"]}, {"BYGA", "LingoAce"})
        self.assertEqual(c["conflicts"][0]["minutes"], 60)

    def test_confirmed_makeup_selected(self):
        c = self.case()
        changes = c["planning"]["recommendations"][0]["changes"]
        self.assertEqual(changes[0]["event_id"], "chinese-thursday")
        self.assertEqual(changes[0]["type"], "move")

    def test_failure_is_not_no_conflict(self):
        c = self.case("source_failure")
        self.assertEqual(c["status"], "blocked")
        self.assertIsNone(c["planning"])
        self.assertNotIn("No conflicts", c["answer"])
        with self.assertRaises(ValueError):
            self.coordinator.notifications.send(c, clock=self.clock())

    def test_ambiguous_child(self):
        self.assertEqual(self.case("ambiguous_child")["status"], "blocked")

    def test_source_disagreement(self):
        self.assertEqual(self.case("source_disagreement")["status"], "blocked")

    def test_tournament_never_skipped(self):
        c = self.case("tournament")
        rejected = [
            b
            for b in c["planning"]["branches"]
            if any(ch["event_id"] == "soccer-thursday" and ch["type"] == "skip" for ch in b["changes"])
        ]
        self.assertTrue(rejected)
        self.assertTrue(all(b["verdict"] == "pruned" for b in rejected))
        self.assertTrue(any("illness" in reason for b in rejected for reason in b["hard_rule_failures"]))

    def test_shared_driver_travel(self):
        self.assertEqual(self.case("transportation")["conflicts"][0]["type"], "transportation")

    def test_routine_bypasses_planner(self):
        c = self.case("routine")
        self.assertEqual(c["status"], "clear")
        self.assertIsNone(c["planning"])

    def test_unknown_makeup_remains_pending(self):
        r = self.store.get("records", "LINGO-201")
        r.update(makeup_start=None, makeup_end=None)
        self.store.put("records", r["id"], r)
        c = self.case()
        self.assertTrue(any(b["verdict"] == "pending_evidence" for b in c["planning"]["branches"]))
        self.assertEqual(c["planning"]["recommendations"], [])

    def test_beam_bounded(self):
        p = self.case()["planning"]
        self.assertLessEqual(p["expansions"], 28)
        self.assertTrue(all(b["depth"] <= 3 for b in p["branches"]))

    def test_no_approval_no_effect(self):
        action = self.preview()
        with self.assertRaises(ValueError):
            self.coordinator.actions.execute(action["id"])
        self.assertEqual(self.store.all("calendar"), [])

    def test_approved_write_is_verified_and_single_use(self):
        action = self.preview()
        self.coordinator.actions.approve(action["id"])
        result = self.coordinator.actions.execute(action["id"])
        self.assertEqual(result["status"], "executed")
        self.assertEqual(len(self.store.all("calendar")), 1)
        with self.assertRaises(ValueError):
            self.coordinator.actions.execute(action["id"])
        self.assertIn("action_verified", [a["kind"] for a in self.store.audit()])

    def test_approval_expires(self):
        action = self.preview()
        self.coordinator.actions.approve(action["id"])
        action = self.store.get("actions", action["id"])
        action["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        self.store.put("actions", action["id"], action)
        with self.assertRaises(ValueError):
            self.coordinator.actions.execute(action["id"])

    def test_approval_cannot_cover_changed_content(self):
        action = self.preview()
        self.coordinator.actions.approve(action["id"])
        action = self.store.get("actions", action["id"])
        action["changes"][0]["start"] = "2026-08-14T20:00:00-07:00"
        self.store.put("actions", action["id"], action)
        with self.assertRaises(ValueError):
            self.coordinator.actions.execute(action["id"])

    def test_new_source_invalidates_approval(self):
        action = self.preview()
        self.coordinator.actions.approve(action["id"])
        r = self.store.get("records", "LINGO-201")
        r["revision"] += 1
        self.store.put("records", r["id"], r)
        with self.assertRaises(ValueError):
            self.coordinator.actions.execute(action["id"])

    def test_concurrent_execution_only_once(self):
        action = self.preview()
        self.coordinator.actions.approve(action["id"])

        def attempt(_):
            try:
                return self.coordinator.actions.execute(action["id"])["status"]
            except ValueError:
                return "blocked"

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt, range(2))), ["blocked", "executed"])

    def test_notification_deduplication(self):
        c = self.case()
        first = self.coordinator.notifications.send(c, clock=self.clock())
        second = self.coordinator.notifications.send(c, clock=self.clock())
        self.assertEqual(first["status"], "simulated_delivered")
        self.assertEqual(second["status"], "duplicate_suppressed")

    def test_completion_suppresses_reminder(self):
        c = self.case()
        delivery = self.coordinator.notifications.send(c, clock=self.clock())
        task = self.store.get("tasks", delivery["id"])
        task["status"] = "completed"
        self.store.put("tasks", task["id"], task)
        self.assertEqual(self.coordinator.notifications.send(c, clock=self.clock())["status"], "suppressed")

    def test_quiet_hours(self):
        self.assertEqual(
            self.coordinator.notifications.send(self.case(), clock=self.clock(23))["status"], "deferred"
        )
        self.assertEqual(self.store.all("notifications"), [])

    def test_live_send_requires_explicit_consent(self):
        with patch("organized_mom.actions.httpx.post") as post:
            with self.assertRaises(ValueError):
                self.coordinator.notifications.send(self.case(), live=True, clock=self.clock())
            post.assert_not_called()

    def test_sensitive_notice_stays_private(self):
        r = self.store.get("records", "LINGO-201")
        r["sensitive"] = True
        self.store.put("records", r["id"], r)
        with self.assertRaises(ValueError):
            self.coordinator.notifications.send(self.case(), clock=self.clock())

    def test_prompt_injection_cannot_authorize_actions(self):
        c = self.case("prompt_injection")
        self.assertEqual(self.store.all("actions"), [])
        self.assertEqual(self.store.all("notifications"), [])
        self.assertEqual(c["status"], "needs_review")

    def test_college_requires_student_and_parent_review(self):
        load_scenario(self.store, "college")
        c = self.coordinator.ask("Help with college milestones")
        self.assertEqual(c["advice"]["status"], "parent_and_student_review")
        self.assertIsNone(c["advice"]["admission_prediction"])

    def test_memory_survives_restart(self):
        c = self.case()
        reopened = Store(self.store.path)
        self.assertEqual(reopened.get("cases", c["id"])["answer"], c["answer"])

    def test_reflection_does_not_modify_rules(self):
        self.case()
        reflection = self.coordinator.reflection.reflect()
        self.assertFalse(reflection["rubric_changed"])
        self.assertEqual(reflection["cases_reviewed"], 1)

    def test_timezone_validation(self):
        r = fixture_records()[0]
        r["start"] = "2026-08-13T16:30:00"
        with self.assertRaises(ValueError):
            Record.model_validate(r)

    def test_touching_events_same_location_do_not_overlap(self):
        rs = [Record.model_validate(r) for r in fixture_records()]
        a = rs[1]
        b = rs[2].model_copy(
            update={"start": a.end, "end": a.end + timedelta(hours=1), "location": a.location}
        )
        self.assertEqual(find_conflicts([a, b]), [])

    def test_cancelled_latest_revision_hides_previous(self):
        rs = [Record.model_validate(r) for r in fixture_records()]
        rs[1] = rs[1].model_copy(update={"status": "cancelled"})
        current, errors = current_records(rs)
        self.assertFalse(errors)
        self.assertEqual([r.id for r in current], ["LINGO-201"])


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(create_app(Path(self.temp.name) / "api.sqlite3"))
        self.csrf = self.client.get("/api/state").json()["csrf"]

    def post(self, path, body=None):
        return self.client.post(path, json=body or {}, headers={"X-Mom-CSRF": self.csrf})

    def test_full_workflow(self):
        c = self.post("/api/ask", {"query": "Soccer conflict with Chinese?"}).json()
        b = c["planning"]["recommendations"][0]
        action = self.post(f"/api/cases/{c['id']}/preview/{b['id']}").json()
        self.assertEqual(self.post(f"/api/actions/{action['id']}/execute").status_code, 409)
        self.assertEqual(
            self.post(
                "/api/actions/approve",
                {"action_id": action["id"], "confirmation": "I approve this exact action"},
            ).status_code,
            200,
        )
        self.assertEqual(self.post(f"/api/actions/{action['id']}/execute").json()["status"], "executed")
        self.assertEqual(self.post("/api/reflection").json()["verified_local_actions"], 1)

    def test_csrf_and_origin(self):
        self.assertEqual(self.client.post("/api/ask", json={"query": "test"}).status_code, 403)
        response = self.client.post(
            "/api/ask",
            json={"query": "test"},
            headers={"X-Mom-CSRF": self.csrf, "Origin": "https://outsider.example"},
        )
        self.assertEqual(response.status_code, 403)

    def test_host_rebinding(self):
        self.assertEqual(self.client.get("/api/state", headers={"Host": "outsider.example"}).status_code, 403)

    def test_home_and_assets(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/static/app.js").status_code, 200)
        self.assertIn("frame-ancestors 'none'", self.client.get("/").headers["content-security-policy"])


if __name__ == "__main__":
    unittest.main()
