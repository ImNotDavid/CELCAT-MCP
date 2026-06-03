# Imperial College Timetable - Exploration & MCP Plan

## 1. Source Overview

| Property | Value |
|----------|-------|
| **URL** | `https://www.imperial.ac.uk/timetabling/calendar/` |
| **Product** | CELCAT Calendar (Scientia) v8.2.5775.0 |
| **Framework** | ASP.NET MVC (.NET Framework) |
| **Auth** | Imperial College SSO (Shibboleth) for personal data; rooms are public |
| **Public browsing** | Rooms only (resType=102) — no login needed |
| **Authenticated browsing** | Modules, Staff, Groups, Students, Teams, Equipment, Programmes |

## 2. URL Structure

```
/timetabling/calendar/cal?vt={viewType}&dt={date}&et={entityType}
```

| Param | Values |
|-------|--------|
| `vt`  | `month`, `week`, `day`, `list` |
| `dt`  | `YYYY-MM-DD` |
| `et`  | entity type string (e.g. `room`) |

## 3. API Endpoints (all under `/timetabling/calendar/`)

### Data Endpoints (POST, require X-Requested-With: XMLHttpRequest)

| Endpoint | Purpose | Auth Required | Notes |
|----------|---------|---------------|-------|
| `Home/GetCalendarData` | Fetch calendar events | No (rooms only) | Returns `null` when no resource selected; 500 on bad params |
| `Home/GetSideBarEvent` | Get event details | No | Pass `eventId` |
| `Home/GetSideBarResources` | Get sidebar resources | No | |
| `Home/GetColourData` | Color scheme data | No | |
| `Home/GetSmartColourKey` | Color key | No | |
| `Home/ReadSecondaryFilterResourceTypes` | Get secondary filters | No | Body: `homeFilterResourceType={resType}`. Returns `[]` for rooms |
| `Home/ReadResourceListItems` | Get resource list items | No | 500 error — needs correct params |
| `Home/ReadFilterListItems` | Get filter list items | No | |
| `Home/LoadDisplayNames` | Load display names | No | |
| `Home/GetMenuText` | Menu text | No | |
| `Home/GetTitle` | Title text | No | |
| `BrowseSelection/LoadBrowseSelection` | Load current selection | No | Body: `resType=102`. Returns `[]` when none selected |
| `BrowseSelection/SaveBrowseSelection` | Save resource selection | No | Body: `resType=102&federationIds=` |

### Page Endpoints (GET)

| Endpoint | Purpose |
|----------|---------|
| `cal` | Main calendar page |
| `Login` | SSO login redirect |

### Parameters for GetCalendarData

```
POST /timetabling/calendar/Home/GetCalendarData
Content-Type: application/x-www-form-urlencoded

start=2026-06-01
end=2026-06-30
resType=102
calView=month
federationIds=     (empty when no selection)
colourScheme=3
```

## 4. Resource Types

| Code | Type | Public? |
|------|------|---------|
| 100  | Modules | No (auth required) |
| 101  | Staff | No |
| **102** | **Room** | **Yes (public)** |
| 103  | Groups | No |
| 104  | Students | No |
| 105  | Teams | No |
| 106  | Equipment | No |
| 107  | Programmes | No |

## 5. Event Data Fields (Public Room View)

| Field | Available? |
|-------|-----------|
| Event Name | Yes |
| Event Category | Yes |
| Department | No (only when logged in) |
| Modules | Yes |
| Rooms | Yes |
| Staff | Yes |
| Groups | Yes |
| Students | No |
| Teams | Yes (when logged in) |
| Notes | No (only when logged in) |
| Published Online Link | No (only when logged in) |
| Event ID | Yes |

## 6. Calendar Configuration

| Setting | Value |
|---------|-------|
| Business hours | 07:00 - 23:00 |
| Week starts on | Monday |
| Date extent | 2025-06-30 to 2026-09-27 |
| Color schemes | Department(1), Faculty(2), Event category(3), Register status(4), Campus(5), Module(6), Register mark(7) |
| Default color scheme | Event category (3) |
| Client cache | Enabled in browser session storage |

## 7. What is NOT Available

1. **No public iCal/ICS feed** — the system does not expose calendar subscriptions
2. **No REST API documentation** — the endpoints are internal AJAX in the ASP.NET MVC app
3. **No bulk data export** — only paginated month/week/day views
4. **No WebSocket/push** — data is polled on view change
5. **No rate limit info** — but Imperial's proxy (`http_x_icbs_proxy`) may enforce limits
6. **No public module/staff/student data** — these require Imperial SSO login
7. **No historical data** — only future timetables within the academic year (2025-06-30 to 2026-09-27)

## 8. Proposed MCP Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  MCP Client  │◄───►│  CELCAT-MCP MCP  │◄───►│  Imperial       │
│  (e.g. Claude)│     │  Server (Python)  │     │  CELCAT API      │
└──────────────┘     └──────────────────┘     └─────────────────┘
```

### MCP Tools / Resources

1. **`list_rooms(department?, campus?)`** — List all rooms with metadata
2. **`get_room_timetable(room_id, start_date, end_date)`** — Events for a room
3. **`search_events(query, start_date?, end_date?)`** — Full-text search across events
4. **`list_resource_types()`** — Available resource types and access levels

### Data Schema (Python dataclasses)

```python
@dataclass
class Room:
    id: str
    name: str
    department: str | None
    campus: str | None
    capacity: int | None

@dataclass
class TimetableEvent:
    id: str
    name: str
    start: datetime
    end: datetime
    category: str | None
    modules: list[str]
    rooms: list[str]
    staff: list[str]
    groups: list[str]
```

### Implementation Strategy

1. **Session management**: Maintain a `requests.Session` with cookies from initial page visit
2. **CSRF token**: Extract `__RequestVerificationToken` from initial HTML response
3. **Resource discovery**: Iteratively browse resource types (start with rooms = 102)
4. **Data fetching**: Call `Home/GetCalendarData` with date ranges and resource types
5. **Caching**: Use TTL-based in-memory cache (e.g., `cachetools.TTLCache`)
6. **Request throttling**: Respectful delay between requests (1s+)
7. **Error handling**: Retry with backoff on 429/503; clear session on 401

### Files to Create

| File | Purpose |
|------|---------|
| `src/celcat_mcp/server.py` | MCP server entry point |
| `src/celcat_mcp/client.py` | CELCAT API client (session, requests) |
| `src/celcat_mcp/models.py` | Data classes |
| `src/celcat_mcp/cache.py` | Caching layer |
| `pyproject.toml` | Dependencies (fastmcp, requests, cachetools) |
| `README.md` | Usage |

### Dependencies

- `fastmcp` (or `mcp`) — MCP protocol server
- `requests[socks]` — HTTP client with session/cookie support
- `cachetools` — TTL caching
- `beautifulsoup4` — HTML parsing for CSRF token extraction

## 9. Open Questions

1. Does the `GetCalendarData` endpoint support multiple resource IDs in `federationIds`?
2. What is the correct `__RequestVerificationToken` flow — one per session or per request?
3. Is there a per-IP rate limit behind Imperial's HTTP proxy?
4. Can the `IsValid` flag be set to `true` for any unauthenticated endpoints?
5. What does the response JSON schema look like exactly (need to get a successful response)?
6. Does the event filter (category, department, campus, module) work without auth?
