# The Organized Mom

A personal family assistant that checks changing schedules, compares alternatives, remembers feedback, and keeps commitment changes under parent control.

**This release is a local synthetic prototype.** The default flow is deterministic and requires no API key. It does not access real family accounts or send real messages. Optional model review and read-only account setup are separate features.

## Run on your Mac

From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m organized_mom
```

Open **http://127.0.0.1:8000**. Python 3.11 or newer is required. Python 3.12 is the tested isolated environment.

On the prepared workspace, dependencies are already installed:

```bash
cd /Users/mintao/Documents/AI_Learning/organized-mom
.venv/bin/python -m organized_mom
```

The app binds to localhost. Do not expose it publicly without adding authentication. It uses a local CSRF token and rejects foreign origins/hostnames, but it is not a multi-user hosted service.

## A two-minute first run

1. Keep the **Soccer changed** scenario and click **Check my family's plans**.
2. Inspect the current BYGA-101 and LINGO-201 records and the one-hour overlap.
3. Open **Review the alternatives** and preview the confirmed Chinese make-up.
4. Try execution without approval to see the guardrail, then check the exact approval box and apply locally.
5. Return to the overview and send a simulated notification during daytime hours. A second attempt is suppressed.
6. Open **Tasks & memory**, mark the task Done, and create a weekly reflection.
7. Load **Calendar check failed**, run another check, and observe that the assistant keeps it pending.

Dates intentionally replay the August 13, 2026 module example. The local calendar change does not alter BYGA or LingoAce source records. Re-running the original source check can therefore still show the original provider conflict.

## Project contents

| Path | Purpose |
|---|---|
| `PROJECT_PLAN.md` | Consolidated Modules 1–6 plan and implementation status |
| `organized_mom/` | Six roles, retrieval, planning, tool gate, memory, API, optional integrations |
| `web/` | Local browser interface |
| `data/` | Synthetic records and schema example |
| `tests/` | Behavioral, approval, failure, concurrency, and API tests |
| `scripts/` | Evaluation, browser demo, packaging, and optional account setup |
| `artifacts/` | Generated synthetic evidence and demo materials |
| `docs/FINAL_REPORT.md` | Method, measured results, and limitations |
| `docs/DEMO_SCRIPT.md` | Presentation walkthrough and narration |
| `docs/INTEGRATIONS.md` | Optional model, Google, Telegram, and MCP setup |

## Verify and reproduce

```bash
python -m unittest discover -s tests -v
python scripts/evaluate.py
python -m organized_mom.worker --once
```

Optional browser checking uses Playwright in a new browser context. It never reads your existing browser session:

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
python scripts/browser_demo.py
```

The browser script exercises **synthetic scenario data**, so run it against a dedicated demo database. See the script's `--help` for details.

## GitHub upload

Upload the `organized-mom` project folder or use the generated release ZIP. `.gitignore` excludes `.env`, OAuth secrets, runtime databases, private imports, and virtual environments. Review manually added records before sharing.

```bash
git init
git add .
git commit -m "Build Organized Mom synthetic assistant"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/organized-mom.git
git push -u origin main
```

Create your repository first and replace `YOUR-USERNAME`. No repository was created or pushed automatically. The included GitHub Actions workflow runs tests on pushes and pull requests.

## Boundaries

- Six programmatic roles run locally. The optional model review uses role-specific Responses API calls with read-only tools. It is not part of the default demo and has not been live-tested without credentials.
- The schema validates structured input. General email extraction accuracy is not yet measured.
- The travel check uses a 30-minute buffer, not traffic data.
- Telegram is simulated by default. Real sends require explicit standing consent for a configured chat.
- All external calendar changes and email replies remain disabled.
- Sunday reflections remain local previews. The worker must be running to poll.
- School-specific college facts remain pending until official sources and student goals are supplied.

See the project plan for the remaining work before real family use.
