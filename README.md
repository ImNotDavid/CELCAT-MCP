# CELCAT MCP Server

MCP server providing read-only access to Imperial College London's CELCAT timetable data (rooms).

## Quick Start

```bash
# Install
pip install .

# Run via stdio (for MCP clients like Claude Desktop)
celcat-mcp

# Or via Python module
python -m celcat_mcp.server
```

## Tools

| Tool | Description |
|------|-------------|
| `list_resource_types` | List available resource types and their access levels |
| `list_rooms` | List all bookable rooms in the timetable system |
| `get_room_timetable` | Get events for specific room(s) over a date range |
| `search_events` | Search events by keyword (name, module, room, staff) |
| `get_event_details` | Get full details of a specific event by ID |

## Usage with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "imperial-timetable": {
      "command": "celcat-mcp",
      "args": []
    }
  }
}
```

## Public Access

Only **Room** timetable data is publicly accessible. All other resource types (modules, staff, students, etc.) require an Imperial College login.

## Data Source

Imperial College uses **CELCAT Calendar v8.2** (Scientia), an ASP.NET MVC web application at:
`https://www.imperial.ac.uk/timetabling/calendar/`

## Limitations

- No public iCal/ICS feed available
- No bulk data export — only date-range queries
- Data is limited to the current academic year: 2025-06-30 to 2026-09-27
- Room list discovery depends on CELCAT's select2 autocomplete API
- Rate limiting may apply behind Imperial's HTTP proxy

## Project Structure

```
src/celcat_mcp/
├── __init__.py    Package exports
├── __main__.py    Entry point
├── cache.py       TTL-based caching
├── client.py      CELCAT HTTP API client
├── models.py      Data classes (Room, TimetableEvent)
└── server.py      FastMCP server definition
```
