"""Standalone ingestion script for CI (no Dagster dependency)."""
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
from ingestion.ticketmaster_client import TicketmasterClient
from ingestion.assets import get_db_path, init_db, CITIES


def main():
    client = TicketmasterClient()
    print(f"Fetching events for cities: {CITIES}")

    raw = client.fetch_all_events(cities=CITIES, days_ahead=90)
    print(f"Fetched {len(raw)} raw events")

    parsed = [client.parse_event(e) for e in raw]
    print(f"Parsed {len(parsed)} events")

    db_path = get_db_path()
    conn = duckdb.connect(db_path)
    init_db(conn)

    today = date.today()
    conn.execute("DELETE FROM raw.events WHERE snapshot_date = ?", [today])

    for row in parsed:
        conn.execute("""
            INSERT INTO raw.events (
                event_id, name, event_date, venue_name, venue_city,
                venue_state, venue_capacity, genre, subgenre,
                artist_name, min_price, max_price, currency,
                status, url, snapshot_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            row["event_id"], row["name"], row["event_date"],
            row["venue_name"], row["venue_city"], row["venue_state"],
            row["venue_capacity"], row["genre"], row["subgenre"],
            row["artist_name"], row["min_price"], row["max_price"],
            row["currency"], row["status"], row["url"], today,
        ])

    conn.close()
    print(f"Ingested {len(parsed)} events for {today}")


if __name__ == "__main__":
    main()
