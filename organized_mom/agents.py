import time
import uuid
from datetime import UTC, datetime, timedelta

from .actions import ActionGate, Notifications, digest
from .models import Record
from .planning import PlanningAgent, ScheduleCritic, find_conflicts
from .retrieval import Retriever, current_records
from .store import now

ROLES = [
    {"name": "Family Coordinator", "purpose": "Routes cases, presents decisions, and enforces approval."},
    {"name": "Information Agent", "purpose": "Retrieves current records and checks identity and provenance."},
    {"name": "Planning Agent", "purpose": "Compares bounded alternatives for schedule conflicts."},
    {
        "name": "High School & College Advisor",
        "purpose": "Tracks student-approved milestones and missing official evidence.",
    },
    {"name": "Schedule Critic", "purpose": "Independently checks hard rules, evidence, overlap, and travel."},
    {"name": "Reflection Agent", "purpose": "Reviews verified outcomes and proposes improvements."},
]


class InformationAgent:
    def __init__(self, store):
        self.store = store
        self.retriever = Retriever()

    def collect(self, query, child=None, date=None):
        records = [Record.model_validate(r) for r in self.store.all("records")]
        current, errors = current_records(records)
        selected = [
            r
            for r in current
            if (not child or r.child == child) and (not date or r.start.date().isoformat() == date)
        ]
        evidence = self.retriever.search(records, query, child, date)
        return {"current": selected, "all_current": current, "errors": errors, "evidence": evidence}


class CollegeAdvisor:
    def advise(self, records):
        milestones = [r for r in records if r.kind == "milestone"]
        return {
            "status": "parent_and_student_review",
            "milestones": [r.model_dump(mode="json") for r in milestones],
            "summary": "Review goals with the student and school counselor. Verify graduation requirements and dates against the current official school sources before adopting the plan.",
            "unverified": [
                "School-specific graduation requirements",
                "Current testing and application dates",
            ],
            "admission_prediction": None,
            "planning_template": [
                {
                    "year": "Grade 9",
                    "focus": "Discuss interests, course choices, and an achievable activity routine.",
                },
                {
                    "year": "Grade 10",
                    "focus": "Revisit course progress and student-chosen service or leadership goals.",
                },
                {
                    "year": "Grade 11",
                    "focus": "Review current testing policies, campus interests, and counselor guidance.",
                },
                {
                    "year": "Grade 12",
                    "focus": "Confirm each official application deadline and review submissions together.",
                },
            ],
        }


class ReflectionAgent:
    def __init__(self, store):
        self.store = store

    def reflect(self):
        cutoff = datetime.now(UTC) - timedelta(days=7)
        cases = [c for c in self.store.all("cases") if datetime.fromisoformat(c["created_at"]) >= cutoff]
        actions = [a for a in self.store.all("actions") if datetime.fromisoformat(a["created_at"]) >= cutoff]
        notifications = [
            n for n in self.store.all("notifications") if datetime.fromisoformat(n["created_at"]) >= cutoff
        ]
        result = {
            "id": str(uuid.uuid4()),
            "created_at": now(),
            "period": "Past seven days",
            "cases_reviewed": len(cases),
            "blocked_cases": sum(c["status"] == "blocked" for c in cases),
            "verified_local_actions": sum(a["status"] == "executed" for a in actions),
            "simulated_notifications": sum(n["status"] == "simulated_delivered" for n in notifications),
            "telegram_api_accepted": sum(n["status"] == "api_accepted" for n in notifications),
            "delivery_unknown": sum(n["status"] == "delivery_unknown" for n in notifications),
            "completed_tasks": sum(t["status"] == "completed" for t in self.store.all("tasks")),
            "recommendation": "Review unresolved sources and transport assumptions before changing soft scoring weights.",
            "rubric_changed": False,
            "publication": "local preview; no Telegram post",
        }
        self.store.put("reflections", result["id"], result)
        self.store.log("reflection_created", result["id"], {"cases_reviewed": len(cases)})
        return result


class FamilyCoordinator:
    def __init__(self, store):
        self.store = store
        self.information = InformationAgent(store)
        self.critic = ScheduleCritic()
        self.planner = PlanningAgent(self.critic)
        self.advisor = CollegeAdvisor()
        self.reflection = ReflectionAgent(store)
        self.actions = ActionGate(store)
        self.notifications = Notifications(store)

    def ask(self, query, child=None, date=None):
        started = time.monotonic()
        collected = self.information.collect(query, child, date)
        records = collected["current"]
        errors = collected["errors"]
        case_id = str(uuid.uuid4())
        trace = [
            {"agent": "Family Coordinator", "stage": "observe", "observation": "Created a structured case."},
            {
                "agent": "Information Agent",
                "stage": "retrieve",
                "observation": f"Retrieved {len(collected['evidence'])} ranked records; validated {len(records)} current records.",
            },
        ]
        conflicts = find_conflicts(records) if not errors else []
        is_college = any(w in query.lower() for w in ("college", "high school", "graduation", "milestone"))
        planning, advice = None, None
        if errors or not records:
            status = "blocked"
            answer = "Check incomplete. " + "; ".join(errors or ["No verified records match these filters."])
            trace.append(
                {
                    "agent": "Family Coordinator",
                    "stage": "defer",
                    "observation": "Kept pending for source recovery or parent clarification.",
                }
            )
        elif is_college:
            advice = self.advisor.advise(records)
            status = "needs_review"
            answer = advice["summary"]
            trace.extend(
                [
                    {
                        "agent": "High School & College Advisor",
                        "stage": "plan",
                        "observation": "Prepared a multi-year discussion template; school-specific facts remain unverified.",
                    },
                    {
                        "agent": "Schedule Critic",
                        "stage": "verify",
                        "observation": "Parent and student review required; no admissions predictions.",
                    },
                ]
            )
        elif conflicts:
            planning = self.planner.solve(records)
            status = "needs_review"
            descriptions = []
            for conflict in conflicts:
                a, b = [next(r for r in records if r.id == id) for id in conflict["ids"]]
                descriptions.append(
                    f"{a.title} [{a.id}] and {b.title} [{b.id}]: {conflict['minutes']} minutes of {conflict['type']}"
                )
            answer = "; ".join(descriptions) + ". Review the alternatives before changing a commitment."
            trace.extend(
                [
                    {
                        "agent": "Planning Agent",
                        "stage": "plan",
                        "observation": f"Compared {planning['expansions']} bounded candidate actions.",
                    },
                    {
                        "agent": "Schedule Critic",
                        "stage": "verify",
                        "observation": "Checked hard rules before scoring; kept unsupported alternatives pending or pruned.",
                    },
                    {
                        "agent": "Family Coordinator",
                        "stage": "review",
                        "observation": "No changes executed. Parent action-specific approval required.",
                    },
                ]
            )
        else:
            status = "clear"
            answer = "No conflicts found among the verified records in this check. " + "; ".join(
                f"{r.title} [{r.id}]" for r in records
            )
            trace.append(
                {
                    "agent": "Family Coordinator",
                    "stage": "verify",
                    "observation": "Routine path completed without the planner.",
                }
            )
        case = {
            "id": case_id,
            "query": query,
            "created_at": now(),
            "status": status,
            "answer": answer,
            "mode": "deterministic_demo",
            "records": [r.model_dump(mode="json") for r in records],
            "source_ids": [r.id for r in records],
            "evidence": collected["evidence"],
            "errors": errors,
            "source_snapshot": digest(
                sorted([r.model_dump(mode="json") for r in collected["all_current"]], key=lambda r: r["id"])
            ),
            "conflicts": conflicts,
            "planning": planning,
            "advice": advice,
            "trace": trace,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
        self.store.put("cases", case_id, case)
        self.store.log(
            "case_completed",
            case_id,
            {"status": status, "source_ids": case["source_ids"], "elapsed_ms": case["elapsed_ms"]},
        )
        return case
