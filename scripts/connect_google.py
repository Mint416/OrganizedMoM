"""User-run read-only OAuth setup. Never called by the assistant during the synthetic demo."""

import os
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def main():
    from google_auth_oauthlib.flow import InstalledAppFlow

    path = Path("secrets/google-client.json")
    if not path.exists():
        raise SystemExit(
            "Place your Google Desktop OAuth client JSON at secrets/google-client.json. See docs/INTEGRATIONS.md."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
    credentials = flow.run_local_server(port=0)
    target = Path("secrets/google-token.json")
    target.write_text(credentials.to_json())
    os.chmod(target, 0o600)
    print("Read-only connection saved locally. No messages sent or calendar changes made.")


if __name__ == "__main__":
    main()
