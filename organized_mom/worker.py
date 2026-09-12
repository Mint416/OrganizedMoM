"""Local reminder polling; run explicitly. The default channel is simulation."""

import argparse
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .actions import digest
from .agents import FamilyCoordinator
from .models import Record
from .retrieval import current_records
from .store import Store


def tick(store, clock=None, live=False):
    current_time = clock or datetime.now(ZoneInfo("America/Los_Angeles"))
    coordinator = FamilyCoordinator(store)
    records, errors = current_records([Record.model_validate(r) for r in store.all("records")])
    if errors:
        store.log("worker_check_failed", "sources", {"errors": errors})
        return {"status": "check_failed", "errors": errors}
    due = [r for r in records if current_time <= (r.deadline or r.start) <= current_time + timedelta(days=2)]
    results = []
    if due:
        snapshot = digest([r.model_dump(mode="json") for r in records])
        cached = store.get("worker_cases", snapshot)
        case = (
            store.get("cases", cached["id"])
            if cached
            else coordinator.ask("Prepare upcoming family reminders and check conflicts")
        )
        store.put("worker_cases", snapshot, {"id": case["id"]})
        results.append(coordinator.notifications.send(case, live=live, clock=current_time))
    # Sunday reflection is local only until live summary delivery is separately implemented.
    if current_time.weekday() == 6 and 8 <= current_time.hour < 12:
        key = current_time.date().isoformat()
        if store.claim("weekly_runs", key, {"status": "started"}):
            reflection = coordinator.reflection.reflect()
            store.put("weekly_runs", key, {"status": "completed", "reflection_id": reflection["id"]})
            results.append({"status": "local_reflection_created", "id": reflection["id"]})
    return {"status": "checked", "due": len(due), "results": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--live-telegram", action="store_true", help="Requires configured chat and standing app permission"
    )
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    store = Store(os.getenv("MOM_DB", "runtime/mom.sqlite3"))
    while True:
        try:
            print(tick(store, live=args.live_telegram), flush=True)
        except ValueError as exc:
            print({"status": "blocked", "reason": str(exc)}, flush=True)
        if args.once:
            break
        time.sleep(60)


if __name__ == "__main__":
    main()
