from copy import deepcopy
from datetime import timedelta
from itertools import combinations
from time import monotonic

WEIGHTS = {
    "feasibility": 25,
    "evidence": 20,
    "commitments": 20,
    "disruption": 15,
    "transport": 10,
    "clarity": 10,
}


def find_conflicts(records, travel_minutes=30):
    conflicts = []
    for a, b in combinations(records, 2):
        same_child = a.child == b.child
        same_driver = bool(a.driver and a.driver == b.driver)
        if not (same_child or same_driver):
            continue
        overlap = max(a.start, b.start) < min(a.end, b.end)
        before, after = sorted((a, b), key=lambda r: r.start)
        travel = before.location != after.location and before.end <= after.start < before.end + timedelta(
            minutes=travel_minutes
        )
        if overlap or travel:
            conflicts.append(
                {
                    "ids": [a.id, b.id],
                    "event_ids": [a.event_id, b.event_id],
                    "type": "overlap" if overlap else "transportation",
                    "minutes": round((min(a.end, b.end) - max(a.start, b.start)).total_seconds() / 60)
                    if overlap
                    else travel_minutes,
                    "start": max(a.start, b.start).isoformat(),
                    "end": min(a.end, b.end).isoformat(),
                    "reason": "Same child" if same_child else "Shared driver",
                }
            )
    return conflicts


class ScheduleCritic:
    def evaluate(self, candidate, original, modified, parent_illness=False):
        errors = []
        changes = candidate["changes"]
        for c in changes:
            event = next(r for r in original if r.event_id == c["event_id"])
            if event.kind == "tournament" and c["type"] in ("skip", "partial") and not parent_illness:
                errors.append("A tournament cannot be missed without parent-provided illness status.")
            if c["type"] == "move" and not (event.makeup_allowed and event.makeup_start and event.makeup_end):
                errors.append("A confirmed make-up time is required.")
            if c["type"] == "partial" and not event.partial_allowed:
                errors.append("Partial attendance permission is unverified.")
            if c["type"] == "skip" and (event.group or not event.makeup_allowed):
                errors.append("Protect group and no-make-up commitments; parent decision required.")
            if c["type"] == "skip":
                errors.append("Skipping without a verified replacement is a separate parent decision.")
        remaining = find_conflicts(modified)
        components = dict(WEIGHTS)
        components["feasibility"] = 25 if not remaining else 5
        components["transport"] = 10 if not any(c["type"] == "transportation" for c in remaining) else 0
        components["disruption"] = max(0, 15 - 3 * len(changes))
        if errors:
            components["commitments"] = 0
        score = sum(components.values())
        return {
            "score": score,
            "components": components,
            "hard_rule_failures": errors,
            "remaining_conflicts": remaining,
            "verdict": "pruned" if errors or score < 60 else "feasible" if not remaining else "expand",
        }


class PlanningAgent:
    """A bounded beam search over structured actions, not hidden reasoning transcripts."""

    def __init__(self, critic=None):
        self.critic = critic or ScheduleCritic()

    def solve(self, records, parent_illness=False):
        started = monotonic()
        root = {"id": "root", "depth": 0, "changes": [], "records": records}
        beam, trace, solutions = [root], [], []
        expansions = 0
        for depth in range(1, 4):
            next_beam = []
            for node in beam:
                conflicts = find_conflicts(node["records"])
                if not conflicts:
                    continue
                pair = [r for r in node["records"] if r.id in conflicts[0]["ids"]]
                options = []
                for r in pair:
                    if r.makeup_allowed:
                        options.append((r, "move"))
                    if r.partial_allowed:
                        options.append((r, "partial"))
                # Include explicit rejected alternatives so the safety boundary is observable.
                options.extend((r, "skip") for r in pair)
                for event, action in options[:4]:
                    if expansions >= 28 or monotonic() - started >= 8:
                        break
                    expansions += 1
                    modified = list(node["records"])
                    change = {"type": action, "event_id": event.event_id, "source_id": event.id}
                    unresolved = []
                    if action == "move" and event.makeup_start:
                        replacement = event.model_copy(
                            update={"start": event.makeup_start, "end": event.makeup_end}
                        )
                        modified = [replacement if r.id == event.id else r for r in modified]
                        change.update(start=event.makeup_start.isoformat(), end=event.makeup_end.isoformat())
                    elif action == "move":
                        unresolved.append(
                            "Make-up time unknown; request one targeted source refresh or parent clarification."
                        )
                    elif action == "partial":
                        other = next(r for r in pair if r.id != event.id)
                        end = other.start - timedelta(minutes=30 if other.location != event.location else 0)
                        if end > event.start:
                            modified = [
                                r.model_copy(update={"end": end}) if r.id == event.id else r for r in modified
                            ]
                            change.update(start=event.start.isoformat(), end=end.isoformat())
                        else:
                            unresolved.append("There is no feasible partial-attendance window.")
                    else:
                        modified = [r for r in modified if r.id != event.id]
                    candidate = {
                        "id": f"branch-{expansions}",
                        "parent_id": node["id"],
                        "depth": depth,
                        "title": f"{ {'move': 'Use confirmed make-up for', 'partial': 'Attend part of', 'skip': 'Skip'}[action] } {event.title}",
                        "changes": deepcopy(node["changes"]) + [change],
                        "source_ids": [r.id for r in pair],
                        "unresolved": unresolved,
                        "requires_approval": True,
                    }
                    candidate.update(self.critic.evaluate(candidate, records, modified, parent_illness))
                    if unresolved:
                        candidate["verdict"] = "pending_evidence"
                    trace.append(candidate)
                    if candidate["verdict"] == "feasible":
                        solutions.append(candidate)
                    elif candidate["verdict"] == "expand":
                        next_beam.append({**candidate, "records": modified})
                if expansions >= 28 or monotonic() - started >= 8:
                    break
            solutions.sort(key=lambda c: (-c["score"], len(c["changes"])))
            if solutions and solutions[0]["score"] >= 80:
                break
            beam = sorted(next_beam, key=lambda c: -c["score"])[:3]
            if not beam or expansions >= 28 or monotonic() - started >= 8:
                break
        tie = len(solutions) > 1 and solutions[0]["score"] == solutions[1]["score"]
        return {
            "branches": trace,
            "recommendations": solutions[:2] if tie else solutions[:1],
            "needs_parent_choice": tie or not solutions,
            "expansions": expansions,
            "limits": {"branching": 4, "beam": 3, "depth": 3, "expansions": 28, "seconds": 8},
            "elapsed_ms": round((monotonic() - started) * 1000, 2),
        }
