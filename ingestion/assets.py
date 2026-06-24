import os
from datetime import date
from pathlib import Path

import dagster
import duckdb
from dotenv import load_dotenv

from ingestion.ticketmaster_client import TicketmasterClient

load_dotenv()

CITIES = ["Seattle"]


def get_db_path() -> str:
    db_path = os.environ.get("DUCKDB_PATH", "data/concert_tracker.duckdb")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return db_path


def init_db(conn: duckdb.DuckDBPyConnection):
    conn.execute("""
        CREATE SCHEMA IF NOT EXISTS raw;
        CREATE TABLE IF NOT EXISTS raw.events (
            event_id VARCHAR NOT NULL,
            name VARCHAR,
            event_date TIMESTAMP,
            venue_name VARCHAR,
            venue_city VARCHAR,
            venue_state VARCHAR,
            venue_capacity INTEGER,
            genre VARCHAR,
            subgenre VARCHAR,
            artist_name VARCHAR,
            min_price DOUBLE,
            max_price DOUBLE,
            currency VARCHAR,
            status VARCHAR,
            url VARCHAR,
            snapshot_date DATE NOT NULL,
            ingested_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(event_id, snapshot_date)
        );
    """)


@dagster.asset(
    description="Daily snapshot of concert events from Ticketmaster API",
    group_name="ingestion",
)
def raw_events(context: dagster.AssetExecutionContext) -> dagster.MaterializeResult:
    client = TicketmasterClient()
    context.log.info(f"Fetching events for cities: {CITIES}")

    raw_events_data = client.fetch_all_events(cities=CITIES, days_ahead=90)
    context.log.info(f"Fetched {len(raw_events_data)} raw events")

    parsed = [client.parse_event(e) for e in raw_events_data]
    context.log.info(f"Parsed {len(parsed)} events")

    today = date.today()
    conn = duckdb.connect(get_db_path())
    try:
        init_db(conn)

        # Delete existing rows for today (upsert pattern)
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

        context.log.info(f"Inserted {len(parsed)} rows for {today}")
    finally:
        conn.close()

    return dagster.MaterializeResult(
        metadata={
            "num_events": len(parsed),
            "snapshot_date": str(today),
            "cities": CITIES,
        }
    )
