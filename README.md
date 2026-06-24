# Concert Price & Availability Tracker

An end-to-end data pipeline that tracks concert ticket prices and availability over time, revealing pricing patterns and helping fans find the best time to buy.

## Architecture

```
Ticketmaster API → Dagster (orchestration) → DuckDB (storage) → dbt (transform) → Streamlit (dashboard)
```

## What It Does

- **Ingests** daily snapshots of concert events from the Ticketmaster Discovery API
- **Stores** raw and transformed data in DuckDB (file-based, zero setup)
- **Transforms** data with dbt to compute price curves, sold-out velocity, and optimal buy windows
- **Serves** an interactive Streamlit dashboard with insights

## Key Insights Produced

- How ticket prices change as event date approaches (price curves)
- Sold-out velocity by genre, venue size, and day of week
- Best day/time to purchase tickets
- Event explorer with search and filters

## Tech Stack

| Layer | Tool |
|-------|------|
| Ingestion | Python + Ticketmaster Discovery API |
| Orchestration | Dagster |
| Storage | DuckDB |
| Transformation | dbt-core |
| Dashboard | Streamlit |

## Setup

### Prerequisites

- Python 3.11+
- Ticketmaster API key ([get one free](https://developer.ticketmaster.com))

### Quick Start

```bash
cd concert-price-tracker

# Copy env template and add your API key
cp .env.example .env
# Edit .env with your TICKETMASTER_API_KEY

# Install Python dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Launch Dagster (pipeline UI at http://localhost:3000)
dagster dev

# Materialize the raw_events asset in the Dagster UI, then run dbt:
cd transform && dbt run && cd ..

# Launch dashboard
streamlit run dashboard/app.py

# Once initial setup completed (for runs after first one)
cd ~/concert-price-tracker
git pull
source .venv/bin/activate
streamlit run dashboard/app.py

Or view directly at: https://concert-price-tracker.streamlit.app/
```

## Project Structure

```
concert-price-tracker/
├── requirements.txt
├── pyproject.toml
├── .env.example
├── ingestion/
│   ├── __init__.py
│   ├── ticketmaster_client.py  # API client with rate limiting
│   └── assets.py               # Dagster assets (ingestion logic)
├── transform/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── staging/
│   │   │   ├── sources.yml
│   │   │   ├── stg_events.sql
│   │   │   └── stg_price_snapshots.sql
│   │   └── marts/
│   │       ├── price_curves.sql
│   │       ├── soldout_velocity.sql
│   │       └── best_buy_windows.sql
│   └── seeds/
│       └── genre_mappings.csv
├── dashboard/
│   └── app.py                  # Streamlit dashboard
├── dagster_project/
│   ├── __init__.py
│   ├── definitions.py
│   └── schedules.py
└── tests/
    └── test_ingestion.py
```

## How It Works

1. **Daily ingestion**: Dagster triggers the Ticketmaster API client to fetch all music events in Seattle for the next 90 days
2. **Snapshot storage**: Each day's data is stored as a snapshot in DuckDB, allowing price comparison over time
3. **Transformation**: dbt models compute derived metrics (price changes, sell-out speed, optimal buy windows)
4. **Visualization**: Streamlit reads from DuckDB and presents interactive charts

The key insight comes from accumulating daily snapshots — after 1-2 weeks, you can see real pricing trends.
