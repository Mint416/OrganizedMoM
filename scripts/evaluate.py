"""Generate reproducible evidence from real runs against temporary synthetic databases."""

import io
import json
import statistics
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from organized_mom.agents import FamilyCoordinator
from organized_mom.fixtures import SCENARIOS, fixture_records, load_scenario
from organized_mom.store import Store, now


def main():
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (output / "test-results.txt").write_text(log.getvalue())
    scenarios = []
    with tempfile.TemporaryDirectory() as temp:
        store = Store(Path(temp) / "evaluation.sqlite3")
        coordinator = FamilyCoordinator(store)
        for name in SCENARIOS:
            load_scenario(store, name)
            query = (
                "Review high school college milestones"
                if name == "college"
                else "Did soccer change and conflict with Chinese?"
            )
            case = coordinator.ask(query)
            scenarios.append(
                {
                    "scenario": name,
                    "status": case["status"],
                    "conflicts": len(case["conflicts"]),
                    "source_ids": case["source_ids"],
                    "elapsed_ms": case["elapsed_ms"],
                }
            )
        simple, complex_ = [], []
        for name, times in (("routine", simple), ("schedule_change", complex_)):
            load_scenario(store, name)
            for _ in range(20):
                times.append(coordinator.ask("Check soccer and Chinese conflicts")["elapsed_ms"])
        # A compact, separate end-to-end trace includes actual tool outcomes.
        trace_store = Store(Path(temp) / "trace.sqlite3")
        load_scenario(trace_store, "schedule_change")
        c = FamilyCoordinator(trace_store)
        case = c.ask("Did BYGA change soccer this week, and does it conflict with LingoAce Chinese class?")
        action = c.actions.preview(case, case["planning"]["recommendations"][0])
        try:
            c.actions.execute(action["id"])
            blocked = False
        except ValueError:
            blocked = True
        c.actions.approve(action["id"])
        execution = c.actions.execute(action["id"])
        demo_clock = datetime.now(ZoneInfo("America/Los_Angeles")).replace(hour=12, minute=0)
        delivery = c.notifications.send(case, clock=demo_clock)
        duplicate = c.notifications.send(case, clock=demo_clock)
        task = trace_store.get("tasks", delivery["id"])
        task["status"] = "completed"
        trace_store.put("tasks", task["id"], task)
        completed = c.notifications.send(case, clock=demo_clock)
        reflection = c.reflection.reflect()
        trace = {
            "generated_at": now(),
            "disclosure": "Actual deterministic synthetic run. Notification clock fixed to noon. No external effects.",
            "case": case,
            "unauthorized_execution_blocked": blocked,
            "approved_execution": execution,
            "notification": delivery,
            "repeat_notification": duplicate,
            "after_completion": completed,
            "reflection": reflection,
            "audit": trace_store.audit(),
        }
        (output / "end-to-end-trace.json").write_text(json.dumps(trace, indent=2))
    expected = {
        "schedule_change": True,
        "tournament": True,
        "transportation": True,
        "routine": False,
        "prompt_injection": True,
    }
    tp = fp = fn = tn = 0
    for row in scenarios:
        if row["scenario"] not in expected:
            continue
        truth, prediction = expected[row["scenario"]], bool(row["conflicts"])
        tp += truth and prediction
        fp += not truth and prediction
        fn += truth and not prediction
        tn += not truth and not prediction
    report = {
        "generated_at": now(),
        "mode": "deterministic_synthetic",
        "tests": {
            "run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "passed": result.wasSuccessful(),
        },
        "scenarios": scenarios,
        "conflict_evaluation": {
            "sample_size": len(expected),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        },
        "latency": {
            "samples_per_path": 20,
            "simple_median_ms": statistics.median(simple),
            "planning_median_ms": statistics.median(complex_),
            "includes_network_or_llm": False,
        },
        "unmeasured": [
            "Free-form notice extraction accuracy",
            "Live Google synchronization completeness",
            "Real Telegram delivery rate",
            "Real-world conflict precision and recall",
            "LLM latency and factuality",
            "Production fallback success rate",
        ],
        "interpretation": "Small authored fixtures and unit tests establish regression behavior only. Do not present their percentages as production reliability.",
    }
    (output / "evaluation.json").write_text(json.dumps(report, indent=2))
    (ROOT / "data/sample-record.json").write_text(json.dumps(fixture_records()[2], indent=2))
    (ROOT / "data/demo-records.json").write_text(json.dumps(fixture_records(), indent=2))
    print(
        json.dumps(
            {
                "tests": report["tests"],
                "conflict_evaluation": report["conflict_evaluation"],
                "latency": report["latency"],
            },
            indent=2,
        )
    )
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
