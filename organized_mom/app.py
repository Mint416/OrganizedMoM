import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .agents import ROLES, FamilyCoordinator
from .fixtures import SCENARIOS, load_scenario
from .models import Approval, Ask, Consent, Feedback, Record
from .store import Store, now

ROOT = Path(__file__).resolve().parent.parent


def create_app(db_path=None):
    store = Store(db_path or os.getenv("MOM_DB", str(ROOT / "runtime/mom.sqlite3")))
    coordinator = FamilyCoordinator(store)
    if not store.get("settings", "initialized"):
        load_scenario(store, "schedule_change")
        store.put("settings", "initialized", {"at": now()})
    app = FastAPI(title="The Organized Mom", version="0.1.0")
    app.state.store, app.state.coordinator = store, coordinator
    csrf = secrets.token_urlsafe(32)

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.url.hostname not in ("127.0.0.1", "localhost", "testserver"):
            return JSONResponse(
                {"detail": "This personal prototype accepts localhost access only."}, status_code=403
            )
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.headers.get('host')}"
            if (origin and origin != expected) or request.headers.get("x-mom-csrf") != csrf:
                return JSONResponse({"detail": "Refresh the app before making this change."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    @app.exception_handler(ValueError)
    async def invalid_action(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/state")
    def state():
        return {
            "csrf": csrf,
            "mode": "Synthetic demonstration",
            "roles": ROLES,
            "scenarios": SCENARIOS,
            "scenario": store.get("settings", "scenario"),
            "records": store.all("records"),
            "cases": store.all("cases")[-20:],
            "tasks": store.all("tasks"),
            "actions": store.all("actions"),
            "notifications": store.all("notifications"),
            "calendar": store.all("calendar"),
            "reflections": store.all("reflections")[-10:],
            "audit": store.audit(),
            "connections": {
                "telegram_configured": bool(
                    os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")
                ),
                "telegram_consent": (store.get("settings", "telegram") or {}).get("enabled", False),
                "model_configured": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL_NAME")),
                "external_writes": "disabled",
            },
        }

    @app.post("/api/scenarios/{scenario}")
    def scenario(scenario: str):
        return load_scenario(store, scenario)

    @app.post("/api/ask")
    def ask(body: Ask):
        return coordinator.ask(body.query, body.child, body.date)

    @app.post("/api/records")
    def import_record(body: Record):
        result = store.put("records", body.id, body.model_dump(mode="json"))
        store.log("record_imported", body.id, {"source": body.source, "revision": body.revision})
        return result

    @app.delete("/api/records/{record_id}")
    def delete_record(record_id: str):
        store.delete("records", record_id)
        store.log("record_deleted", record_id, {})
        return {"status": "deleted", "id": record_id}

    def get_case(case_id):
        result = store.get("cases", case_id)
        if not result:
            raise HTTPException(404, "Case not found")
        return result

    @app.post("/api/cases/{case_id}/preview/{branch_id}")
    def preview(case_id: str, branch_id: str):
        case = get_case(case_id)
        branch = next(
            (b for b in (case.get("planning") or {}).get("branches", []) if b["id"] == branch_id), None
        )
        if not branch:
            raise HTTPException(404, "Candidate not found")
        return coordinator.actions.preview(case, branch)

    @app.post("/api/actions/approve")
    def approve(body: Approval):
        return coordinator.actions.approve(body.action_id)

    @app.post("/api/actions/{action_id}/execute")
    def execute(action_id: str):
        return coordinator.actions.execute(action_id)

    @app.post("/api/cases/{case_id}/notify")
    def notify(case_id: str, live: bool = False):
        return coordinator.notifications.send(get_case(case_id), live=live)

    @app.post("/api/tasks/{task_id}/feedback")
    def feedback(task_id: str, body: Feedback):
        task = store.get("tasks", task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        task.update(status=body.status, updated_at=now())
        if body.status == "snoozed":
            task["snooze_until"] = (datetime.now(UTC) + timedelta(minutes=body.minutes)).isoformat()
        store.put("tasks", task_id, task)
        store.log("task_feedback", task_id, {"status": body.status})
        return task

    @app.post("/api/reflection")
    def reflection():
        return coordinator.reflection.reflect()

    @app.post("/api/settings/telegram")
    def telegram_consent(body: Consent):
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if body.enabled and (not chat_id or body.confirmation != f"Allow notifications to {chat_id}"):
            raise ValueError("Confirm the exact configured chat using: Allow notifications to <chat ID>.")
        store.put("settings", "telegram", {"enabled": body.enabled, "chat_id": chat_id, "at": now()})
        store.log("telegram_consent", "telegram", {"enabled": body.enabled})
        return {"enabled": body.enabled}

    @app.post("/api/cases/{case_id}/model-review")
    def model_review(case_id: str):
        from .llm import review_case

        return review_case(get_case(case_id), store)

    @app.get("/api/export")
    def export():
        return {
            "exported_at": now(),
            "disclosure": "Synthetic local demonstration. Review any manually imported content before sharing.",
            "cases": store.all("cases"),
            "actions": store.all("actions"),
            "notifications": store.all("notifications"),
            "tasks": store.all("tasks"),
            "reflections": store.all("reflections"),
            "audit": store.audit(),
        }

    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")

    @app.get("/")
    def home():
        return FileResponse(ROOT / "web/index.html")

    return app
