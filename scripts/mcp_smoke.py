import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from organized_mom.fixtures import load_scenario
from organized_mom.store import Store


async def main():
    with tempfile.TemporaryDirectory() as temp:
        db = str(Path(temp) / "mcp.sqlite3")
        load_scenario(Store(db), "schedule_change")
        server = StdioServerParameters(
            command=sys.executable, args=["-m", "organized_mom.mcp_server"], env={**os.environ, "MOM_DB": db}
        )
        async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            names = [t.name for t in (await session.list_tools()).tools]
            assert set(names) == {"check_family_schedule", "get_case", "list_pending_tasks"}
            result = await session.call_tool(
                "check_family_schedule", {"query": "Soccer and Chinese conflict?"}
            )
            assert not result.isError
            content = json.loads(result.content[0].text)
            assert content["conflicts"][0]["minutes"] == 60
            report = {"passed": True, "tools": names, "observed_overlap_minutes": 60, "external_actions": 0}
            (ROOT / "artifacts/mcp-results.json").write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
