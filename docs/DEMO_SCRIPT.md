# Presentation walkthrough

## Intended audience and format

This draft is for a capstone presentation to faculty and peers. The MP4 uses narrated screenshots captured from a verified run of the application. It is not a continuous screen recording. The narration uses the standard macOS Samantha voice and can be replaced with my own narration using `NARRATION.md`.

The demonstration uses synthetic records, a fixed August 13, 2026 scenario, a simulated notification outbox, and a local calendar effect. It does not demonstrate live accounts or an LLM call. Optional model and account integrations need a separate verified recording after access is configured.

The requested video duration is eight minutes. The expanded walkthrough explains the full synthetic workflow and preserves the humorous Muse closing. The submission deadline is still awaiting my input.

## Recording sequence

| Scene | What to show | What it establishes |
|---|---|---|
| 1 | Family overview with the synthetic banner | Problem and working interface |
| 2 | Sources and evidence | Current BYGA-101 and LINGO-201, superseded BYGA-100, provenance |
| 3 | Checked result and source citations | Sixty-minute overlap and saved case trace |
| 4 | Candidate list and score breakdown | Bounded alternative generation and independent constraint checking |
| 5 | Exact action preview and rejected unapproved execution | Permission boundary works at the server |
| 6 | Saved local calendar change | Specific approval, execution, and verification |
| 7 | Simulated outbox and completed task | Feedback, deduplication, and persistent memory |
| 8 | Failed source scenario | Unavailable information stays pending |
| 9 | Rejected tournament-skipping branch | Hard family rules override scores |
| 10 | College planning discussion template | Parent/student review and unverified official requirements |
| 11 | Weekly reflection | Verified outcome summary, test evidence, and next steps |
| 12 | Return to the family overview | A humorous closing about Meta's Muse launch and making room for the people and experiences that matter |

## Live presentation click path

1. Start `python -m organized_mom` and open `http://127.0.0.1:8000`.
2. Load **Soccer changed** and click **Check my family's plans**.
3. Inspect the retrieval results and current source records.
4. Review alternatives, then preview the Chinese make-up.
5. Click **Test execution without approval**. Read the rejection inside the dialog.
6. Check **I approve this exact action**, then apply locally.
7. Return to overview, send a simulated notification, and attempt it again to show duplicate suppression.
8. Open **Tasks & memory**, click Done, reload, and show the saved completed status and local calendar change.
9. Load **Calendar check failed**. Run the check and show that no notification or approved action follows.
10. Load **Tournament hard rule** and show the rejected branch.
11. Load **Grade 9 planning** and open Decisions to show the review template.
12. Create a weekly reflection and explain what remains for a real-account pilot.

Quiet hours are a real guardrail. During 9 PM–7 AM Pacific, notification attempts defer. For reproducible daytime screenshots use the browser demo during daytime. `scripts/evaluate.py` separately fixes its synthetic notification test clock to noon and discloses that choice.

## Recreate the provided MP4

```bash
python -m pip install -e '.[dev,artifacts]'
python -m playwright install chromium
python scripts/browser_demo.py
python scripts/build_video.py
```

On this prepared Mac, the browser script can use the installed Chrome executable in a fresh, temporary browser context:

```bash
python scripts/browser_demo.py --chrome '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

The video builder requires macOS `say`. Other platforms can use the provided MP4 or record narration from `NARRATION.md` in a preferred editor. It creates a 1920×1080 MP4 with optional English subtitles, a separate SRT, and a scene manifest with measured durations.

## Questions to prepare for

**Why use retrieval?** The changing family schedule exists outside model memory. Revision-aware source evidence is required before checking conflicts.

**Why six roles?** Each role has a bounded responsibility. The critic independently evaluates candidate schedules. Simple tasks avoid unnecessary planning.

**Is the demo powered by an LLM?** The default is deterministic. Optional model review has role-specific read-only tool calls and was contract-tested with a mock response, not live credentials. It does not replace hard checks.

**What proves safety?** Behavioral tests and the browser workflow show blocked unapproved, expired, altered, replayed, or stale-source actions. This evidence applies to the local prototype, not an untested external adapter.

**What remains?** Representative free-form extraction evaluation, authorized source sync, live Telegram validation, provider-specific writes, and production hosting controls.
