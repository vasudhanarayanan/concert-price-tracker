with status_changes as (
    select
        event_id,
        event_name,
        artist_name,
        genre,
        venue_name,
        venue_city,
        event_date,
        min(snapshot_date) as first_seen_date,
        min(case when status = 'offsale' then snapshot_date end) as soldout_date,
        min(days_until_event) filter (where status = 'offsale') as days_before_event_soldout
    from {{ ref('stg_price_snapshots') }}
    group by event_id, event_name, artist_name, genre, venue_name, venue_city, event_date
)

select
    *,
    soldout_date - first_seen_date as days_to_sellout,
    case
        when soldout_date is not null then true
        else false
    end as did_sell_out
from status_changes
