# Connections and access guide

The first release uses synthetic data by agreement. None of these setup steps ran against real accounts during the build. Keep credentials in `.env` or `secrets/`, which are excluded from GitHub.

## Optional model-assisted review

1. Copy `.env.example` to `.env`.
2. Set your own `OPENAI_API_KEY`, a Responses-compatible `OPENAI_MODEL_NAME`, and `MOM_LLM_ENABLED=true`.
3. Restart the app, run a family check, and choose **Request model review**.

The model receives a read-only `read_verified_case` tool. Routine reviews use two roles and four API calls. Conflict and college reviews use four roles and eight calls. Each call limits output tokens. These calls can incur API charges. No live model call was made during the synthetic build.

The review is labeled unverified commentary. It cannot change source facts, deterministic scores, action approvals, or outgoing alerts. Raw notice prose is excluded from the tool payload, and sensitive records block review. Labels and other structured strings are still untrusted input. Production use needs factuality evaluation and source-data review.

The request/response protocol follows the [official Responses function-calling guide](https://developers.openai.com/api/docs/guides/function-calling). Responses use `store=false`; this is a request setting, not a claim about all provider retention policies.

## Gmail and Google Calendar: read only

Use a Google Cloud project you control. Enable Gmail API and Google Calendar API, configure the OAuth consent screen for your account, and create a **Desktop app** OAuth client. For a personal Gmail account, use the appropriate external/testing configuration and add yourself as a test user. Download the client JSON into `secrets/google-client.json`.

```bash
python -m pip install -e '.[google]'
python scripts/connect_google.py
```

Complete sign-in and consent in Google's official browser flow. The requested scopes are `gmail.readonly` and `calendar.readonly`. No send or calendar-write scopes are requested. The local token file has owner-only permissions.

After connection:

```bash
python -m organized_mom.google_import --query 'newer_than:7d' --max-items 20
```

This reads at most 20 matching emails and at most 20 calendar items over the next 14 days. It saves raw results to `artifacts/private/google-import.json`. It does not automatically infer which child an item concerns. Review and normalize a record using `data/sample-record.json`, then import it from **Sources & evidence**.

This bounded reader is not a complete synchronization engine. Pagination, provider cursors, recurring/all-day normalization, identity matching, and source freshness reporting are pilot work. Protected links remain unreviewed until the user supplies authorized content. Do not bypass school login, MFA, or CAPTCHA.

Setup references: [Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) and [Calendar Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python).

## BYGA, LingoAce, Schoology, and ParentSquare

Start with a provider-supported export, calendar feed, or notification email containing complete details. Use the original provider ID and revision where possible. If no permitted API/export exists, enter a structured record manually. A login link alone does not establish the date, child, or current schedule. Mark unresolved records `pending_login` or `check_failed`.

No vendor-specific private API or scraping adapter is claimed in this release. Identify the actual permitted access method before implementing one.

## Telegram

Create a bot through Telegram's official BotFather flow and add it only to the intended family chat. Store `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`. Never paste the bot token into a public issue or repository.

The app additionally requires exact standing consent. The consent endpoint accepts:

```json
{"enabled": true, "confirmation": "Allow notifications to <your configured chat ID>"}
```

Send that body to `/api/settings/telegram` using the current `X-Mom-CSRF` token from `/api/state`. This is an explicit local setup step, not authorization inferred from a module document. A later setup UI can wrap it. To revoke permission, send `{"enabled": false}`.

The normal UI notification button stays simulated. After setting standing consent, an explicit live request uses `/api/cases/<case ID>/notify?live=true`, or start the worker with `--live-telegram`.

The sender verifies the response's chat ID and message ID. `api_accepted` means Telegram accepted the message; it does not establish that a person read it. Timeouts become `delivery_unknown` and are not blindly retried. Quiet hours are 9 PM–7 AM Pacific. Sensitive-flagged records stay private. Current implementation does not support urgent quiet-hour exceptions or automatic Sunday Telegram summaries.

Reference: [Telegram Bot API sendMessage](https://core.telegram.org/bots/api#sendmessage).

## Local polling and reflection

```bash
python -m organized_mom.worker --once
python -m organized_mom.worker
```

The continuous command checks saved structured records each minute while running. Events/deadlines within two days are eligible. The worker does not refresh Gmail or school sites by itself. Sunday morning runs between 8 AM and noon produce one local reflection per date. Quiet hours defer alerts. Snoozed tasks can re-notify once after their snooze expires; completed/acknowledged tasks suppress reminders.

The fixed August demonstration dates may be in the past when you run the worker, so an empty due list is expected. Use freshly dated synthetic records to test current reminder timing.

## Optional MCP server

Start the app once to initialize synthetic records, then run:

```bash
python -m organized_mom.mcp_server
```

Example client configuration, replacing the absolute path:

```json
{
  "mcpServers": {
    "organized-mom": {
      "command": "/ABSOLUTE/PROJECT/.venv/bin/python",
      "args": ["-m", "organized_mom.mcp_server"],
      "env": {"MOM_DB": "/ABSOLUTE/PROJECT/runtime/mom.sqlite3"}
    }
  }
}
```

Tools are `check_family_schedule`, `get_case`, and `list_pending_tasks`. Schedule checking saves a local case for traceability. There are no model-accessible approval, send-email, or calendar-write tools. The MCP server uses the [official Python SDK](https://github.com/modelcontextprotocol/python-sdk).

## Private hosting and real writes

The current service rejects non-local hostnames and has no account-based authentication. A hosted pilot requires a separate deployment design with authentication, secrets, retention, backup, and access control. Real calendar/email adapters remain disabled even if a local action is approved. Implement and test provider-specific scope binding, uncertain-result reconciliation, and post-write verification before enabling those effects.
