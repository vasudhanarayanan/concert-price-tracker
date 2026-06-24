with source as (
    select * from {{ source('raw', 'events') }}
)

select
    event_id,
    name as event_name,
    event_date::timestamp as event_date,
    venue_name,
    venue_city,
    venue_state,
    venue_capacity,
    genre,
    subgenre,
    artist_name,
    min_price,
    max_price,
    (min_price + max_price) / 2.0 as avg_price,
    currency,
    status,
    url,
    snapshot_date,
    ingested_at,
    event_date::date - snapshot_date as days_until_event
from source
where event_date is not null
