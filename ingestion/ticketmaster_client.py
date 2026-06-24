from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from typing import Optional

import requests


BASE_URL = "https://app.ticketmaster.com/discovery/v2"
RATE_LIMIT_DELAY = 0.2  # 5 requests/sec max


class TicketmasterClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ["TICKETMASTER_API_KEY"]
        self.session = requests.Session()

    def get_events(
        self,
        city: str | None = None,
        state_code: str | None = None,
        genre: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page: int = 0,
        size: int = 200,
    ) -> dict:
        params = {
            "apikey": self.api_key,
            "classificationName": "music",
            "page": page,
            "size": size,
            "sort": "date,asc",
        }

        if city:
            params["city"] = city
        if state_code:
            params["stateCode"] = state_code
        if genre:
            params["genreId"] = genre
        if start_date:
            params["startDateTime"] = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        if end_date:
            params["endDateTime"] = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        time.sleep(RATE_LIMIT_DELAY)
        response = self.session.get(f"{BASE_URL}/events.json", params=params)
        response.raise_for_status()
        return response.json()

    def fetch_all_events(
        self,
        cities: list[str] | None = None,
        state_code: str | None = None,
        days_ahead: int = 90,
    ) -> list[dict]:
        """Fetch all music events across specified cities for the next N days."""
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days_ahead)

        all_events = []
        locations = cities or [None]

        for city in locations:
            page = 0
            while True:
                data = self.get_events(
                    city=city,
                    state_code=state_code,
                    start_date=start_date,
                    end_date=end_date,
                    page=page,
                )

                embedded = data.get("_embedded", {})
                events = embedded.get("events", [])
                if not events:
                    break

                all_events.extend(events)

                page_info = data.get("page", {})
                total_pages = page_info.get("totalPages", 1)
                page += 1
                if page >= total_pages or page >= 5:  # cap at 5 pages per city
                    break

        return all_events

    def parse_event(self, raw_event: dict) -> dict:
        """Parse a raw Ticketmaster event into a flat row for storage."""
        venue = {}
        if "_embedded" in raw_event and "venues" in raw_event["_embedded"]:
            venue = raw_event["_embedded"]["venues"][0]

        artist = ""
        if "_embedded" in raw_event and "attractions" in raw_event["_embedded"]:
            artist = raw_event["_embedded"]["attractions"][0].get("name", "")

        genre_info = raw_event.get("classifications", [{}])[0]
        price_ranges = raw_event.get("priceRanges", [{}])[0] if raw_event.get("priceRanges") else {}

        event_date = None
        dates = raw_event.get("dates", {}).get("start", {})
        if dates.get("dateTime"):
            event_date = dates["dateTime"]
        elif dates.get("localDate"):
            event_date = dates["localDate"]

        return {
            "event_id": raw_event["id"],
            "name": raw_event.get("name", ""),
            "event_date": event_date,
            "venue_name": venue.get("name", ""),
            "venue_city": venue.get("city", {}).get("name", ""),
            "venue_state": venue.get("state", {}).get("stateCode", ""),
            "venue_capacity": venue.get("upcomingEvents", {}).get("_total"),
            "genre": genre_info.get("genre", {}).get("name", ""),
            "subgenre": genre_info.get("subGenre", {}).get("name", ""),
            "artist_name": artist,
            "min_price": price_ranges.get("min"),
            "max_price": price_ranges.get("max"),
            "currency": price_ranges.get("currency", "USD"),
            "status": raw_event.get("dates", {}).get("status", {}).get("code", ""),
            "url": raw_event.get("url", ""),
        }
