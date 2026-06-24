with snapshots as (
    select
        event_id,
        event_name,
        artist_name,
        genre,
        venue_name,
        venue_city,
        event_date,
        snapshot_date,
        min_price,
        max_price,
        avg_price,
        status,
        days_until_event,
        lag(avg_price) over (
            partition by event_id order by snapshot_date
        ) as prev_avg_price,
        row_number() over (
            partition by event_id order by snapshot_date
        ) as snapshot_number
    from {{ ref('stg_events') }}
)

select
    *,
    avg_price - prev_avg_price as price_change,
    case
        when prev_avg_price > 0
        then round(((avg_price - prev_avg_price) / prev_avg_price * 100)::numeric, 2)
        else null
    end as price_change_pct
from snapshots
