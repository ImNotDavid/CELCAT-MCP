from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import CelcatClient
from .models import RESOURCE_TYPES

logger = logging.getLogger(__name__)
client = CelcatClient()

server = FastMCP(
    "celcat-mcp",
    instructions="Read-only access to Imperial College London CELCAT timetable data (rooms)",
)


def _format_event(ev: Any) -> str:
    lines = [
        f"Event: {ev.name}",
        f"  ID: {ev.id}",
        f"  Start: {ev.start.strftime('%a %d %b %Y %H:%M')}",
        f"  End: {ev.end.strftime('%a %d %b %Y %H:%M')}",
    ]
    if ev.category:
        lines.append(f"  Category: {ev.category}")
    if ev.rooms:
        lines.append(f"  Rooms: {', '.join(ev.rooms)}")
    if ev.staff:
        lines.append(f"  Staff: {', '.join(ev.staff)}")
    if ev.modules:
        lines.append(f"  Modules: {', '.join(ev.modules)}")
    if ev.groups:
        lines.append(f"  Groups: {', '.join(ev.groups)}")
    return "\n".join(lines)


@server.tool(
    description="List available timetable resource types (room, module, staff, etc.) and whether they are publicly accessible"
)
def list_resource_types() -> str:
    lines = ["Available resource types:\n"]
    for code, name in RESOURCE_TYPES.items():
        public = " (public)" if code == 102 else " (requires Imperial login)"
        lines.append(f"  {code:>3}: {name}{public}")
    lines.append(
        "\nNote: Only Room (102) data is accessible without Imperial College login."
    )
    return "\n".join(lines)


@server.tool(
    description="List bookable rooms. Optionally provide a search query to find specific rooms (e.g. 'Beit', 'Lecture', 'Meeting'). Without a query, returns rooms matching 'Lecture'."
)
def list_rooms(query: str = "Lecture") -> str:
    rooms = client.search_rooms(query)
    if not rooms:
        return (
            f"No rooms found matching '{query}'. "
            "Try a different search term (e.g. 'Beit', 'Meeting', 'Lecture')."
        )
    lines = [f"Found {len(rooms)} room(s) matching '{query}':\n"]
    for r in rooms:
        dept = f" ({r.department})" if r.department else ""
        lines.append(f"  {r.id}: {r.name}{dept}")
    return "\n".join(lines)


@server.tool(
    description="Get timetable events for a specific room or rooms over a date range"
)
def get_room_timetable(
    room_ids: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    today = date.today()
    start = date.fromisoformat(start_date) if start_date else today
    end = date.fromisoformat(end_date) if end_date else start + timedelta(days=31)

    events = client.get_calendar_data(
        res_type=102,
        start=start,
        end=end,
        federation_ids=room_ids if room_ids else None,
    )

    if not events:
        return f"No events found between {start} and {end}."

    lines = [f"Found {len(events)} event(s) between {start} and {end}:\n"]
    for ev in events:
        lines.append(_format_event(ev))
        lines.append("")
    return "\n".join(lines)


@server.tool(description="Search for events by keyword across the timetable")
def search_events(
    query: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    today = date.today()
    start = date.fromisoformat(start_date) if start_date else today
    end = date.fromisoformat(end_date) if end_date else start + timedelta(days=31)

    results = client.search_events(query, start=start, end=end)

    if not results:
        return f"No events matching '{query}' between {start} and {end}."

    lines = [f"Found {len(results)} event(s) matching '{query}':\n"]
    for ev in results:
        lines.append(_format_event(ev))
        lines.append("")
    return "\n".join(lines)


@server.tool(description="Get full details of a specific event by its ID")
def get_event_details(event_id: str) -> str:
    data = client.get_event_details(event_id)
    if not data:
        return f"No details found for event ID {event_id}."
    lines = [f"Event details for {event_id}:\n"]
    elements = data.get("elements", [])
    for el in elements:
        label = el.get("label", "")
        value = el.get("value", "")
        if label or value:
            lines.append(f"  {label}: {value}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="CELCAT MCP server")
    parser.add_argument("--sse", action="store_true", help="Run SSE HTTP server")
    parser.add_argument(
        "--http", action="store_true",
        help="Run Streamable HTTP server (default mount: /mcp)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8001, help="Port")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.sse:
        import uvicorn
        app = server.sse_app()
        logger.info("Starting SSE server on %s:%s (/sse, /messages/)", args.host, args.port)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    elif args.http:
        import uvicorn
        app = server.streamable_http_app()
        logger.info("Starting Streamable HTTP on %s:%s (/mcp)", args.host, args.port)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
