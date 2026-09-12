import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .models import Record
from .retrieval import current_records
from .store import now


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class ActionGate:
    def __init__(self, store):
        self.store = store

    def preview(self, case, branch):
        if case["status"] == "blocked" or branch["verdict"] != "feasible":
            raise ValueError("Only a verified feasible plan can become an action preview.")
        action = {
            "id": str(uuid.uuid4()),
            "case_id": case["id"],
            "kind": "calendar_change",
            "target": "local demonstration calendar",
            "changes": branch["changes"],
            "source_ids": branch["source_ids"],
            "source_snapshot": case["source_snapshot"],
            "status": "awaiting_approval",
            "created_at": now(),
            "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        }
        action["payload_hash"] = digest(
            {k: action[k] for k in ("kind", "target", "changes", "source_snapshot")}
        )
        self.store.put("actions", action["id"], action)
        self.store.log("action_previewed", action["id"], {"payload_hash": action["payload_hash"]})
        return action

    def approve(self, action_id):
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT body FROM objects WHERE kind='actions' AND id=?", (action_id,)
            ).fetchone()
            action = json.loads(row[0]) if row else None
            if not action or action["status"] != "awaiting_approval":
                raise ValueError("Action is missing, already used, or no longer pending.")
            if datetime.fromisoformat(action["expires_at"]) <= datetime.now(UTC):
                raise ValueError("Approval preview expired; create a fresh preview.")
            action["status"] = "approved"
            action["approved_at"] = now()
            db.execute(
                "UPDATE objects SET body=? WHERE kind='actions' AND id=?", (json.dumps(action), action_id)
            )
            db.execute(
                "INSERT INTO audit(at,kind,ref,body) VALUES (?,?,?,?)",
                (
                    now(),
                    "explicit_parent_approval",
                    action_id,
                    json.dumps({"payload_hash": action["payload_hash"], "scope": action["target"]}),
                ),
            )
        return action

    def execute(self, action_id):
        # Approval consumption, freshness validation, local effect and audit are one transaction.
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT body FROM objects WHERE kind='actions' AND id=?", (action_id,)
            ).fetchone()
            action = json.loads(row[0]) if row else None
            if not action or action["status"] != "approved":
                raise ValueError("Blocked: matching explicit approval is required and is single-use.")
            if datetime.fromisoformat(action["expires_at"]) <= datetime.now(UTC):
                raise ValueError("Approval expired.")
            if action["payload_hash"] != digest(
                {k: action[k] for k in ("kind", "target", "changes", "source_snapshot")}
            ):
                raise ValueError("Approved payload changed.")
            rows = db.execute("SELECT body FROM objects WHERE kind='records'").fetchall()
            records = [Record.model_validate_json(r[0]) for r in rows]
            current, errors = current_records(records)
            snapshot = digest(sorted([r.model_dump(mode="json") for r in current], key=lambda r: r["id"]))
            if errors or snapshot != action["source_snapshot"]:
                raise ValueError("Sources changed or a check failed. Recheck the plan before approval.")
            if action["target"] != "local demonstration calendar" or action["kind"] != "calendar_change":
                raise ValueError("External calendar and email writes are disabled in this release.")
            for change in action["changes"]:
                body = {**change, "action_id": action_id, "verified_at": now()}
                db.execute(
                    "INSERT INTO objects VALUES ('calendar',?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body",
                    (change["event_id"], json.dumps(body)),
                )
                verify = db.execute(
                    "SELECT body FROM objects WHERE kind='calendar' AND id=?", (change["event_id"],)
                ).fetchone()
                if json.loads(verify[0]) != body:
                    raise ValueError("Calendar verification failed.")
            action.update(status="executed", verified_at=now(), effect="local simulation")
            db.execute(
                "UPDATE objects SET body=? WHERE kind='actions' AND id=?", (json.dumps(action), action_id)
            )
            db.execute(
                "INSERT INTO audit(at,kind,ref,body) VALUES (?,?,?,?)",
                (
                    now(),
                    "action_verified",
                    action_id,
                    json.dumps({"payload_hash": action["payload_hash"], "effect": "local simulation"}),
                ),
            )
        return action


class Notifications:
    def __init__(self, store):
        self.store = store

    def send(self, case, live=False, clock=None):
        if case["status"] == "blocked" or not case["source_ids"]:
            raise ValueError("A factual alert requires current source support and successful checks.")
        if any(r.get("sensitive") for r in case["records"]):
            raise ValueError("Sensitive records require private parent review.")
        records = [Record.model_validate(r) for r in self.store.all("records")]
        current, errors = current_records(records)
        snapshot = digest(sorted([r.model_dump(mode="json") for r in current], key=lambda r: r["id"]))
        if errors or snapshot != case["source_snapshot"]:
            raise ValueError("Source evidence changed; run a fresh check before sending a notification.")
        consent = self.store.get("settings", "telegram") or {}
        if live and not consent.get("enabled"):
            raise ValueError("Standing permission for the configured Telegram chat is required.")
        token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
        if live and (not token or not chat_id or consent.get("chat_id") != chat_id):
            raise ValueError("Telegram credentials or approved destination are missing or changed.")
        current_time = clock or datetime.now(ZoneInfo("America/Los_Angeles"))
        if current_time.hour >= 21 or current_time.hour < 7:
            return {"status": "deferred", "reason": "Quiet hours: 9 PM to 7 AM Pacific"}
        channel = "telegram" if live else "simulation"
        key = digest(
            {
                "records": sorted(
                    [{k: v for k, v in r.items() if k != "retrieved_at"} for r in case["records"]],
                    key=lambda r: r["id"],
                ),
                "channel": channel,
            }
        )
        task = self.store.get("tasks", key)
        if task and task["status"] in ("completed", "acknowledged", "rescheduled", "incorrect"):
            return {"status": "suppressed", "reason": task["status"]}
        if task and task.get("snooze_until") and datetime.fromisoformat(task["snooze_until"]) > current_time:
            return {"status": "deferred", "reason": "Snoozed"}
        delivery_key = (
            digest({"task": key, "snooze_until": task["snooze_until"]})
            if task and task["status"] == "snoozed" and task.get("snooze_until")
            else key
        )
        message = "Verified schedule: " + "; ".join(
            f"{r['child']}: {r['title']} {datetime.fromisoformat(r['start']).astimezone(ZoneInfo('America/Los_Angeles')).strftime('%b %d, %I:%M %p')} to {datetime.fromisoformat(r['end']).astimezone(ZoneInfo('America/Los_Angeles')).strftime('%I:%M %p')} Pacific [{r['id']}]"
            for r in case["records"]
            if r["id"] in case["source_ids"]
        )
        message += f". Conflicts found: {len(case['conflicts'])}. Recommendation: review the family plan; no external schedule has been changed."
        delivery = {
            "id": delivery_key,
            "task_id": key,
            "case_id": case["id"],
            "channel": channel,
            "text": message,
            "source_ids": case["source_ids"],
            "status": "sending",
            "created_at": now(),
        }
        if not self.store.claim("notifications", delivery_key, delivery):
            return {"status": "duplicate_suppressed", "id": delivery_key}
        try:
            if live:
                response = httpx.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": message},
                    timeout=10,
                )
                response.raise_for_status()
                result = response.json()
                if not result.get("ok") or str(result["result"]["chat"]["id"]) != str(chat_id):
                    raise ValueError("Telegram did not confirm the configured destination.")
                delivery.update(status="api_accepted", message_id=result["result"]["message_id"])
            else:
                delivery["status"] = "simulated_delivered"
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # A timeout may follow a successful external effect. Do not blindly retry.
            delivery.update(
                status="delivery_unknown", error="Delivery could not be verified; review before retrying."
            )
        self.store.put("notifications", delivery_key, delivery)
        self.store.put(
            "tasks",
            key,
            {
                "id": key,
                "case_id": case["id"],
                "title": "Review family schedule",
                "status": "pending",
                "source_ids": case["source_ids"],
                "created_at": task.get("created_at", now()) if task else now(),
            },
        )
        self.store.log("notification_result", key, {"status": delivery["status"], "channel": channel})
        return delivery
