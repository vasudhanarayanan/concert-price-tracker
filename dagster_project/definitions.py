import dagster

from ingestion.assets import raw_events
from dagster_project.schedules import daily_ingestion_schedule

defs = dagster.Definitions(
    assets=[raw_events],
    schedules=[daily_ingestion_schedule],
)
