from __future__ import annotations

import logging
import re
from datetime import datetime, date, time, timedelta
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .cache import calendar_cache, resource_cache, room_list_cache
from .models import RESOURCE_TYPES, PUBLIC_RESOURCE_TYPES, Room, TimetableEvent

logger = logging.getLogger(__name__)

BASE_URL = "https://www.imperial.ac.uk/timetabling/calendar/"
API_ROOT = "/timetabling/calendar/"


class CelcatClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-GB,en;q=0.9",
            }
        )
        self._csrf_token: str | None = None
        self._initialised = False

    def _ensure_session(self) -> None:
        if self._initialised:
            return
        resp = self.session.get(BASE_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        token_input = soup.find("input", {"name": "__RequestVerificationToken"})
        if token_input:
            self._csrf_token = token_input.get("value")
        self._initialised = True

    def _api_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._ensure_session()
        url = urljoin(BASE_URL, path.lstrip("/"))
        headers = {"X-Requested-With": "XMLHttpRequest"}
        resp = self.session.get(url, params=params, headers=headers)
        resp.raise_for_status()
        if resp.status_code == 200 and resp.text:
            try:
                return resp.json()
            except requests.JSONDecodeError:
                logger.warning("Non-JSON response from %s: %s", path, resp.text[:200])
                return None
        return None

    def _api_post(self, path: str, data: dict[str, Any] | None = None) -> Any:
        self._ensure_session()
        url = urljoin(BASE_URL, path.lstrip("/"))
        headers = {"X-Requested-With": "XMLHttpRequest"}
        if self._csrf_token:
            if data is None:
                data = {}
            data.setdefault("__RequestVerificationToken", self._csrf_token)
        resp = self.session.post(url, data=data, headers=headers)
        resp.raise_for_status()
        if resp.status_code == 200 and resp.text:
            try:
                return resp.json()
            except requests.JSONDecodeError:
                logger.warning("Non-JSON response from %s: %s", path, resp.text[:200])
                return None
        return None

    def list_resource_types(self) -> dict[int, str]:
        return dict(RESOURCE_TYPES)

    def get_public_resource_types(self) -> dict[int, str]:
        return dict(PUBLIC_RESOURCE_TYPES)

    def _get_room(self, fed_id: str) -> Room | None:
        cache_key = f"room_{fed_id}"
        if cache_key in room_list_cache:
            return room_list_cache[cache_key]
        return None

    def search_rooms(self, query: str) -> list[Room]:
        cache_key = f"search_{query}"
        if cache_key in room_list_cache:
            return list(room_list_cache[cache_key])

        results_list: list[Room] = []
        batch_size = 50
        page = 1

        total = float("inf")
        while page * batch_size - batch_size < total:
            data = self._api_get(
                "Home/ReadResourceListItems",
                {
                    "resType": "102",
                    "searchTerm": query,
                    "pageSize": str(batch_size),
                    "pageNumber": str(page),
                },
            )
            if not data:
                break
            results = data.get("results", [])
            if not results:
                break
            for item in results:
                room = Room(
                    id=str(item.get("id", "")),
                    name=item.get("text", ""),
                    department=item.get("dept"),
                )
                results_list.append(room)
                room_list_cache[f"room_{room.id}"] = room
            total = data.get("total", 0) or 0
            if page * batch_size >= total:
                break
            page += 1

        room_list_cache[cache_key] = results_list
        return results_list

    def list_rooms(self) -> list[Room]:
        return self.search_rooms("Lecture")

    def get_calendar_data(
        self,
        res_type: int = 102,
        start: date | None = None,
        end: date | None = None,
        view: str = "month",
        federation_ids: list[str] | None = None,
        colour_scheme: int = 3,
    ) -> list[TimetableEvent]:
        if start is None:
            start = date.today()
        if end is None:
            end = start + timedelta(days=31)

        params = {
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "resType": str(res_type),
            "calView": view,
            "colourScheme": str(colour_scheme),
            "federationIds": ",".join(federation_ids) if federation_ids else "",
        }

        cache_key = tuple(sorted(params.items()))
        if cache_key in calendar_cache:
            return list(calendar_cache[cache_key])

        raw = self._api_post("Home/GetCalendarData", params)
        if not raw:
            return []

        events = self._parse_calendar_events(raw)
        calendar_cache[cache_key] = events
        return events

    def _parse_calendar_events(self, raw: list[dict[str, Any]]) -> list[TimetableEvent]:
        events: list[TimetableEvent] = []
        for item in raw:
            try:
                ev = self._parse_single_event(item)
                if ev:
                    events.append(ev)
            except Exception as e:
                logger.warning("Failed to parse event: %s - %s", item.get("id"), e)
        return events

    def _parse_single_event(self, item: dict[str, Any]) -> TimetableEvent | None:
        raw_id = item.get("id")
        if raw_id is None:
            return None
        event_id = str(raw_id)

        title = item.get("title", "") or ""

        raw_start = item.get("start")
        raw_end = item.get("end")
        if not raw_start or not raw_end:
            return None

        start_dt = self._parse_datetime(raw_start)
        end_dt = self._parse_datetime(raw_end)
        if start_dt is None or end_dt is None:
            return None

        description = item.get("description", "") or ""

        modules = self._extract_list(item, "modules")
        rooms = self._extract_list(item, "rooms")
        staff = self._extract_list(item, "staff")
        groups = self._extract_list(item, "groups")

        return TimetableEvent(
            id=event_id,
            name=title,
            start=start_dt,
            end=end_dt,
            category=item.get("eventCategory"),
            modules=modules,
            rooms=rooms,
            staff=staff,
            groups=groups,
        )

    @staticmethod
    def _parse_datetime(val: str) -> datetime | None:
        if isinstance(val, datetime):
            return val
        if isinstance(val, date):
            return datetime.combine(val, time.min)
        if not isinstance(val, str):
            return None

        for fmt in [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
        ]:
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _extract_list(item: dict[str, Any], key: str) -> list[str]:
        val = item.get(key)
        if val is None:
            return []
        if isinstance(val, list):
            return [str(v) for v in val]
        if isinstance(val, str):
            parts = [v.strip() for v in val.split(",")]
            return [v for v in parts if v]
        return [str(val)]

    def get_event_details(self, event_id: str) -> dict[str, Any] | None:
        return self._api_post("Home/GetSideBarEvent", {"eventId": event_id})

    def search_events(
        self,
        query: str,
        start: date | None = None,
        end: date | None = None,
        res_type: int = 102,
    ) -> list[TimetableEvent]:
        events = self.get_calendar_data(res_type=res_type, start=start, end=end)
        q = query.lower()
        results = []
        for ev in events:
            if q in ev.name.lower():
                results.append(ev)
                continue
            for mod in ev.modules:
                if q in mod.lower():
                    results.append(ev)
                    break
            else:
                for r in ev.rooms:
                    if q in r.lower():
                        results.append(ev)
                        break
                else:
                    for s in ev.staff:
                        if q in s.lower():
                            results.append(ev)
                            break
        return results
