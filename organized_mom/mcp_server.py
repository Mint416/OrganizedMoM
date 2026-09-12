"""Read-only MCP surface. Approval and external writes are intentionally not model tools."""

import os

from mcp.server.fastmcp import FastMCP

from .agents import FamilyCoordinator
from .store import Store

mcp = FastMCP("organized-mom")


def coordinator():
    return FamilyCoordinator(Store(os.getenv("MOM_DB", "runtime/mom.sqlite3")))


@mcp.tool()
def check_family_schedule(query: str, child: str | None = None, date: str | None = None) -> dict:
    """Retrieve family evidence and return a checked plan without external effects."""
    return coordinator().ask(query, child, date)


@mcp.tool()
def get_case(case_id: str) -> dict:
    """Read a saved case, its source citations, and observable decision trace."""
    return coordinator().store.get("cases", case_id) or {"status": "not_found"}


@mcp.tool()
def list_pending_tasks() -> list:
    """Read pending, snoozed, or blocked family tasks."""
    return [t for t in coordinator().store.all("tasks") if t["status"] not in ("completed", "rescheduled")]


if __name__ == "__main__":
    mcp.run(transport="stdio")
