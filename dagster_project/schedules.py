import dagster

from ingestion.assets import raw_events


daily_ingestion_schedule = dagster.ScheduleDefinition(
    name="daily_ingestion",
    target=[raw_events],
    cron_schedule="0 8 * * *",  # every day at 8 AM
    default_status=dagster.DefaultScheduleStatus.STOPPED,
)
