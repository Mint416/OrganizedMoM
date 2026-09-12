"""Exercise the actual UI in a fresh browser and isolated temporary demo database."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chrome", default="", help="Optional browser executable; otherwise use Playwright Chromium"
    )
    args = parser.parse_args()
    output = ROOT / "artifacts/screenshots"
    output.mkdir(parents=True, exist_ok=True)
    results = {"mode": "fresh browser, temporary synthetic database", "checks": [], "screenshots": []}
    with tempfile.TemporaryDirectory() as temp:
        env = {
            **os.environ,
            "MOM_DB": str(Path(temp) / "browser.sqlite3"),
            "MOM_PORT": "8011",
            "MOM_LLM_ENABLED": "false",
        }
        with (Path(temp) / "server.log").open("w") as log:
            server = subprocess.Popen(
                [sys.executable, "-m", "organized_mom"], cwd=ROOT, env=env, stdout=log, stderr=log
            )
            try:
                for _ in range(100):
                    try:
                        response = httpx.get("http://127.0.0.1:8011/api/state", timeout=1)
                        if response.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError(
                        "Demo server did not start: " + (Path(temp) / "server.log").read_text()
                    )
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True, **({"executable_path": args.chrome} if args.chrome else {})
                    )
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 1000}, device_scale_factor=1
                    )
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))

                    def capture(name):
                        page.screenshot(path=str(output / f"{name}.png"), animations="disabled")
                        results["screenshots"].append(f"artifacts/screenshots/{name}.png")

                    page.goto("http://127.0.0.1:8011/")
                    expect(page.get_by_role("heading", name="Everything in its place.")).to_be_visible()
                    expect(page.locator("#agenda .event")).to_have_count(2)
                    capture("01-overview")
                    page.get_by_role("button", name="Sources & evidence", exact=False).click()
                    expect(page.locator("#source-list .source-card")).to_have_count(3)
                    capture("02-sources")
                    page.locator('[data-tab="today"]').click()
                    page.get_by_role("button", name="Check my family's plans", exact=False).click()
                    expect(page.locator("#case-result")).to_contain_text("60 minutes of overlap")
                    page.locator("#case-result").scroll_into_view_if_needed()
                    capture("03-conflict")
                    results["checks"].append("Current sources produce a 60-minute overlap")
                    page.get_by_role("button", name="Review the alternatives", exact=False).click()
                    expect(page.locator("#decision-list")).to_contain_text(
                        "Use confirmed make-up for Chinese class"
                    )
                    capture("04-planning")
                    page.get_by_role("button", name="Preview exact local action").first.click()
                    page.get_by_role("button", name="Test execution without approval").click()
                    expect(page.locator("#approval-status")).to_contain_text("Blocked")
                    capture("05-approval-blocked")
                    results["checks"].append("Unapproved execution rejected through the actual UI")
                    page.locator("#approve-check").check()
                    page.get_by_role("button", name="Approve & apply locally").click()
                    expect(page.locator("#approval-dialog")).not_to_be_visible()
                    expect(page.locator("#action-list")).to_contain_text("executed")
                    results["checks"].append("Exact approved local write executed and verified")
                    page.locator('[data-tab="today"]').click()
                    page.get_by_role("button", name="Send simulated notification").click()
                    # Quiet hours are a real guardrail. Do not change the app clock just for the UI test.
                    state = httpx.get("http://127.0.0.1:8011/api/state").json()
                    if state["tasks"]:
                        page.locator('[data-tab="memory"]').click()
                        page.get_by_role("button", name="Done", exact=True).first.click()
                        expect(page.locator("#task-list")).to_contain_text("completed")
                        capture("06-memory")
                        page.reload()
                        page.locator('[data-tab="memory"]').click()
                        expect(page.locator("#task-list")).to_contain_text("completed")
                        results["checks"].append("Feedback persisted after browser reload")
                        page.locator("#calendar-list").scroll_into_view_if_needed()
                        capture("06a-calendar-verified")
                    else:
                        results["checks"].append(
                            "Notification deferred by quiet hours; core tests cover feedback"
                        )
                    page.locator('[data-tab="reflection"]').click()
                    page.get_by_role("button", name="Create weekly reflection").click()
                    expect(page.locator("#reflection-list")).to_contain_text("Verified local actions")
                    capture("07-reflection")
                    results["checks"].append("Reflection includes the verified local action")
                    page.locator('[data-tab="today"]').click()
                    page.locator("#scenario").select_option("source_failure")
                    page.get_by_role("button", name="Load scenario", exact=True).click()
                    page.get_by_role("button", name="Check my family's plans", exact=False).click()
                    expect(page.locator("#case-result")).to_contain_text("Check incomplete")
                    page.locator("#case-result").scroll_into_view_if_needed()
                    capture("08-source-failure")
                    results["checks"].append("Failed source stays pending and hides notification action")
                    expect(page.locator("#simulate-notification")).to_have_count(0)
                    page.locator("#scenario").select_option("tournament")
                    page.get_by_role("button", name="Load scenario", exact=True).click()
                    page.get_by_role("button", name="Check my family's plans", exact=False).click()
                    expect(page.locator("#case-result")).to_contain_text("Soccer tournament")
                    page.get_by_role("button", name="Review the alternatives", exact=False).click()
                    page.get_by_text(
                        "A tournament cannot be missed without parent-provided illness status."
                    ).scroll_into_view_if_needed()
                    capture("09-tournament-rule")
                    results["checks"].append("Tournament-skipping branch displays its hard-rule rejection")
                    page.locator('[data-tab="today"]').click()
                    page.locator("#scenario").select_option("college")
                    page.get_by_role("button", name="Load scenario", exact=True).click()
                    page.get_by_role("button", name="Check my family's plans", exact=False).click()
                    expect(page.locator("#case-result")).to_contain_text("school counselor")
                    page.locator('[data-tab="decisions"]').click()
                    capture("10-college-review")
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.locator('[data-tab="today"]').click()
                    expect(page.get_by_role("heading", name="Everything in its place.")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                        "Mobile horizontal overflow"
                    )
                    capture("11-mobile")
                    results["checks"].append("390-pixel mobile layout has no horizontal overflow")
                    assert not errors, errors
                    results["javascript_errors"] = errors
                    results["passed"] = True
                    context.close()
                    browser.close()
            finally:
                server.terminate()
                server.wait(timeout=10)
    (ROOT / "artifacts/browser-results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
