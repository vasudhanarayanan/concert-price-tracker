#!/bin/bash
cd /Users/vasnara/concert-price-tracker
source .venv/bin/activate

# Run ingestion
python -m dagster asset materialize --select raw_events -m dagster_project.definitions

# Run dbt transforms
cd transform && dbt run --profiles-dir . && cd ..
