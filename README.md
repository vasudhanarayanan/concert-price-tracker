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

## Anomaly Detection

The pipeline automatically detects unusual price movements using z-score analysis:

- Events with 3+ daily snapshots get a rolling mean and standard deviation
- Any price that moves more than 2 standard deviations from the mean is flagged
- Price **drops** (buying opportunities) and **spikes** (demand surges) are tracked separately
- Results are visible in the dashboard's Anomalies tab and included in email alerts

## Price Alerts & Notifications

Set price targets for artists or specific events. When the price drops below your target, you'll get an email.

```bash
# Add an alert
python -m alerts.manage add --artist "Radiohead" --price 80

# List active alerts
python -m alerts.manage list

# Remove an alert
python -m alerts.manage remove --index 0

# Check alerts manually (runs automatically in CI)
python -m alerts.check_alerts --dry-run
```

Notifications use SendGrid (free tier: 100 emails/day). Set `SENDGRID_API_KEY` and `ALERT_EMAIL` in your `.env` or as GitHub Secrets for automated delivery.

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
│   │       ├── best_buy_windows.sql
│   │       └── price_anomalies.sql
│   └── seeds/
│       └── genre_mappings.csv
├── alerts/
│   ├── __init__.py
│   ├── check_alerts.py         # Alert checker + anomaly detection + email
│   └── manage.py               # CLI to add/remove/list alerts
├── dashboard/
│   └── app.py                  # Streamlit dashboard (dark theme)
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
