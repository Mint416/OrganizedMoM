"""Explicit, user-run bounded read-only imports. Unresolved identities stay pending."""

import argparse
import base64
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path


def read_google(query="newer_than:7d", max_items=20):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    path = Path(os.getenv("GOOGLE_TOKEN_PATH", "secrets/google-token.json"))
    if not path.exists():
        raise ValueError("Run scripts/connect_google.py after reviewing docs/INTEGRATIONS.md.")
    credentials = Credentials.from_authorized_user_file(str(path))
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        path.write_text(credentials.to_json())
        os.chmod(path, 0o600)
    mail = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    calendar = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    messages = (
        mail.users().messages().list(userId="me", q=query, maxResults=max_items).execute().get("messages", [])
    )
    inbox = []
    for item in messages:
        message = mail.users().messages().get(userId="me", id=item["id"], format="full").execute()
        payload = message.get("payload", {})

        def text_parts(part):
            result = []
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                data = part["body"]["data"]
                result.append(
                    base64.urlsafe_b64decode(data + "=" * ((-len(data)) % 4)).decode(errors="replace")
                )
            for child in part.get("parts", []):
                result.extend(text_parts(child))
            return result

        inbox.append(
            {
                "id": item["id"],
                "source": "Gmail",
                "status": "pending_parent_normalization",
                "headers": payload.get("headers", []),
                "text": "\n".join(text_parts(payload))[:12000] or message.get("snippet", ""),
            }
        )
    start = datetime.now(UTC)
    events = (
        calendar.events()
        .list(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            timeMin=start.isoformat(),
            timeMax=(start + timedelta(days=14)).isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_items,
        )
        .execute()
    )
    return {
        "retrieved_at": start.isoformat(),
        "gmail": inbox,
        "calendar": events.get("items", []),
        "status": "pending_parent_normalization",
        "limited_to": max_items,
        "note": "Bounded import, not a complete account sync. Assign child and validate dates before importing structured records.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="newer_than:7d")
    parser.add_argument("--max-items", type=int, default=20, choices=range(1, 101))
    args = parser.parse_args()
    result = read_google(args.query, args.max_items)
    target = Path("artifacts/private/google-import.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2))
    os.chmod(target, 0o600)
    print("Private read-only import saved. Review and normalize it before adding records to the app.")


if __name__ == "__main__":
    main()
