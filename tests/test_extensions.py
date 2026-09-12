import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import httpx

from organized_mom.agents import FamilyCoordinator
from organized_mom.fixtures import load_scenario
from organized_mom.llm import review_case
from organized_mom.store import Store
from organized_mom.worker import tick


class ExtensionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "extension.sqlite3")
        load_scenario(self.store, "schedule_change")
        self.coordinator = FamilyCoordinator(self.store)
        self.case = self.coordinator.ask("Soccer and Chinese conflicts")
        self.clock = datetime.now(ZoneInfo("America/Los_Angeles")).replace(hour=12, minute=0)

    def test_notification_revalidates_source_snapshot(self):
        r = self.store.get("records", "BYGA-101")
        r["status"] = "check_failed"
        self.store.put("records", r["id"], r)
        with self.assertRaises(ValueError):
            self.coordinator.notifications.send(self.case, clock=self.clock)

    def test_refresh_timestamp_does_not_duplicate_alert(self):
        self.coordinator.notifications.send(self.case, clock=self.clock)
        r = self.store.get("records", "BYGA-101")
        r["retrieved_at"] = self.clock.isoformat()
        self.store.put("records", r["id"], r)
        fresh = self.coordinator.ask("Soccer and Chinese conflicts")
        self.assertEqual(
            self.coordinator.notifications.send(fresh, clock=self.clock)["status"], "duplicate_suppressed"
        )

    def test_snooze_defers_then_releases_once(self):
        delivery = self.coordinator.notifications.send(self.case, clock=self.clock)
        task = self.store.get("tasks", delivery["task_id"])
        task.update(status="snoozed", snooze_until=(self.clock + timedelta(minutes=30)).isoformat())
        self.store.put("tasks", task["id"], task)
        self.assertEqual(
            self.coordinator.notifications.send(self.case, clock=self.clock)["status"], "deferred"
        )
        sent = self.coordinator.notifications.send(self.case, clock=self.clock + timedelta(hours=1))
        self.assertEqual(sent["status"], "simulated_delivered")
        self.assertNotEqual(sent["id"], delivery["id"])
        self.assertEqual(
            self.coordinator.notifications.send(self.case, clock=self.clock + timedelta(hours=1))["status"],
            "duplicate_suppressed",
        )

    def test_telegram_timeout_is_unknown_and_not_blindly_retried(self):
        self.store.put("settings", "telegram", {"enabled": True, "chat_id": "-100"})
        with (
            patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-only", "TELEGRAM_CHAT_ID": "-100"}),
            patch("organized_mom.actions.httpx.post", side_effect=httpx.ReadTimeout("timeout")) as post,
        ):
            self.assertEqual(
                self.coordinator.notifications.send(self.case, live=True, clock=self.clock)["status"],
                "delivery_unknown",
            )
            self.assertEqual(
                self.coordinator.notifications.send(self.case, live=True, clock=self.clock)["status"],
                "duplicate_suppressed",
            )
            self.assertEqual(post.call_count, 1)

    def test_telegram_response_checks_destination(self):
        self.store.put("settings", "telegram", {"enabled": True, "chat_id": "-100"})
        response = httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 1, "chat": {"id": -200}}},
            request=httpx.Request("POST", "https://example.test"),
        )
        with (
            patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-only", "TELEGRAM_CHAT_ID": "-100"}),
            patch("organized_mom.actions.httpx.post", return_value=response),
        ):
            self.assertEqual(
                self.coordinator.notifications.send(self.case, live=True, clock=self.clock)["status"],
                "delivery_unknown",
            )

    def test_worker_handles_failed_source(self):
        load_scenario(self.store, "source_failure")
        self.assertEqual(tick(self.store, clock=self.clock)["status"], "check_failed")

    def test_worker_creates_one_sunday_reflection(self):
        sunday = datetime(2026, 8, 16, 9, tzinfo=ZoneInfo("America/Los_Angeles"))
        tick(self.store, clock=sunday)
        tick(self.store, clock=sunday)
        self.assertEqual(len(self.store.all("reflections")), 1)

    def test_model_disabled_by_default(self):
        with patch.dict(os.environ, {"MOM_LLM_ENABLED": "false"}), self.assertRaises(ValueError):
            review_case(self.case, self.store)

    def test_model_tool_loop_uses_read_only_context(self):
        requests = []

        def transport(request):
            body = json.loads(request.content)
            requests.append(body)
            if body["tool_choice"] != "none":
                return httpx.Response(
                    200,
                    json={
                        "output": [
                            {
                                "type": "function_call",
                                "name": "read_verified_case",
                                "arguments": "{}",
                                "call_id": "call-1",
                            }
                        ]
                    },
                )
            return httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "Review the verified Chinese make-up [LINGO-201].",
                                }
                            ],
                        }
                    ]
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(transport))
        with (
            patch.dict(
                os.environ,
                {"MOM_LLM_ENABLED": "true", "OPENAI_API_KEY": "test-only", "OPENAI_MODEL_NAME": "test-model"},
            ),
            patch("organized_mom.llm.httpx.Client", return_value=client),
        ):
            result = review_case(self.case, self.store)
        self.assertEqual(len(result["reviews"]), 4)
        self.assertEqual(len(requests), 8)
        self.assertEqual(self.store.all("actions"), [])
        self.assertTrue(all(r["tools"][0]["name"] == "read_verified_case" for r in requests))
        self.assertTrue(all(r["store"] is False for r in requests))


if __name__ == "__main__":
    unittest.main()
