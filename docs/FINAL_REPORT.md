# The Organized Mom: first-release report

**Min Tao — September 7, 2026**

## Problem and outcome

I designed The Organized Mom to reduce the mental work of coordinating family schedules across separate sources. The first working release demonstrates the complete synthetic workflow: retrieve current evidence, detect a conflict, compare bounded alternatives, request exact approval, apply a local calendar change, verify the result, send a simulated notification, and retain feedback.

The application runs locally and includes six specialist roles. It provides a GitHub-ready codebase, a consolidated project plan, reproducible evaluation evidence, and a narrated demonstration walkthrough. Real accounts remain disconnected, following my decision to start with synthetic data.

## Method

I used the six module submissions as project requirements and the capstone rubric as a deliverables checklist. I kept the original family-assistant scope when the generic forecasting rubric described unrelated application examples. Document text did not grant permission to access accounts or execute real effects.

The implementation uses Python, FastAPI, SQLite, and a browser interface. TF-IDF and truncated SVD implement the Module 3 retrieval approach. The Information Agent returns three ranked records while exact metadata and revision checks determine which records can support the active schedule. Deterministic interval logic checks overlaps and a disclosed 30-minute travel buffer.

The Planning Agent generates structured candidate changes and passes them to a separate Schedule Critic. Beam search bounds branching, retained states, depth, and elapsed time. Candidates carry source IDs, change details, scores, unresolved questions, and rejection reasons. The trace shows observable decisions and tool results, not hidden model reasoning.

I simplified the proposed CrewAI/LangChain stack after confirming that the behavior mattered more than those specific frameworks. The default demo uses programmatic roles and no language-model calls. Optional Responses API role review provides read-only tool use with isolated role prompts. Its protocol was tested with mocked responses; live model quality and latency remain unmeasured. An optional MCP server exposes schedule checks and saved state without approval or external-write tools.

## End-to-end example

The demonstration replays Thursday, August 13, 2026. BYGA-100 is the earlier notice. BYGA-101 is the current update moving soccer practice to 5:30–7:00 PM. LINGO-201 retains a 6:00–7:00 PM Chinese class for the same child. The assistant identifies a 60-minute overlap.

The confirmed Friday make-up resolves the synthetic conflict and scores 97/100. An unsupported partial-attendance option remains pending. Skipping protected commitments is rejected. The chosen local action cannot execute until I approve its exact payload. After approval, the server applies the local calendar change and reads it back, then records the verified outcome.

The outbox labels its message `simulated_delivered`. A second send is suppressed. Marking the task completed persists in SQLite and suppresses further reminders. The source-provider records remain unchanged because the local demonstration does not book a make-up or update an external calendar.

## Verification results

The measured run is recorded in `artifacts/evaluation.json` and `artifacts/test-results.txt`. Its timestamp is September 7, 2026, 23:12 UTC.

| Check | Observed result | Interpretation |
|---|---|---|
| Automated behavioral/API tests | 41 run, 0 failures, 0 errors | Regression evidence for the implemented synthetic behavior |
| Authored conflict classification | 5 labeled cases: 4 true positives, 1 true negative, 0 false positives, 0 false negatives | Precision and recall are 100% on this small authored sample only |
| Source/identity failure scenarios | Source unavailable, identity unclear, and source disagreement all block the case | These cases do not produce a false “no conflict” conclusion |
| Simple-path latency | Median 0.685 ms over 20 local runs | Warm deterministic case computation, excluding network and LLM time |
| Planning-path latency | Median 1.11 ms over 20 local runs | Small fixed dataset; not a hosted end-to-end latency claim |
| Actual browser workflow | 8 documented checks passed, no JavaScript errors | Includes approval rejection, verified local write, persistence after reload, failure handling, tournament rule, and mobile overflow |
| MCP protocol smoke test | Three expected tools discovered; schedule tool returned the 60-minute conflict | Actual stdio protocol exchange with no external effects |
| Model protocol contract | Read-only four-role tool loop tested with mocked HTTP responses | No claim of live LLM performance |

The source-failure scenario returns an empty conflict list **with a blocked status**, not evidence of a clear schedule. Evaluation excludes blocked cases from the binary conflict precision/recall denominator.

## Guardrails implemented

The server requires explicit action-specific approval. It binds approval to the exact payload and source snapshot, expires it after ten minutes, and consumes it once. Database transactions cover approval transitions and local execution. Concurrent execution attempts cannot both apply the same approved action. Source changes invalidate execution and outgoing notifications.

The notification sender rechecks evidence and the configured destination, respects quiet hours, prevents duplicate effects, and treats uncertain delivery as unknown. Refreshing only a retrieval timestamp does not create a new alert. Snooze expiry allows one reminder; completion and acknowledgement suppress reminders. Real Telegram behavior is covered by mocked destination/timeout tests, not a live delivery test.

Raw notice content cannot call tools or grant approval. The UI escapes source and model text. MCP exposes no approval or messaging actions. The local HTTP service checks host/origin and requires a CSRF token for mutations. Sensitive-flagged records block model review and notification. External email and calendar write adapters remain disabled.

## What the evaluation does not establish

The Module 6 targets remain acceptance criteria for the personal pilot. This release has not established 95% free-form extraction accuracy, production conflict precision/recall, 99% real Telegram delivery, or 95% safe fallback across real provider failures. Input validation of structured fixtures is not an extraction evaluation.

The 30-minute travel buffer is an assumption. The app does not retrieve traffic or driving routes. Revision checks do not replace provider sync completeness or a mature freshness policy. The Google reader imports only a bounded set of raw records for parent normalization. It does not provide continuous account monitoring.

The college advisor is a discussion template with explicit missing evidence. It cannot verify graduation requirements without official school sources. Illness handling stays with the parent, and the prototype conservatively rejects tournament-skipping options. Sunday reflection is a local preview and does not automatically post to Telegram. Real hosting needs authentication, secret storage, retention controls, and operational monitoring.

## Deliverables and next phase

`PROJECT_PLAN.md` consolidates the requirements and remaining work. The code, tests, source fixtures, evaluation JSON, and end-to-end trace support review and reproduction. The browser screenshots and narrated MP4 demonstrate the verified synthetic flow. `docs/NARRATION.md` provides an editable script for my own voice.

The next phase is an authorized personal pilot: connect selected read-only sources, label representative notices, validate extraction and synchronization, then test one approved Telegram chat. Real calendar/email writes require their own provider-specific implementation and tests. The requested presentation video length is now eight minutes. I will confirm the submission deadline before the final submission edit.

## References

The exact module filenames and page mapping appear in `PROJECT_PLAN.md`. Implementation references are the [OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling), [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [Gmail quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python), [Google Calendar quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python), and [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage).
