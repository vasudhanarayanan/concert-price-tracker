with event_stats as (
    select
        event_id,
        event_name,
        artist_name,
        genre,
        venue_city,
        avg(avg_price) as mean_price,
        stddev(avg_price) as stddev_price,
        count(*) as num_snapshots
    from {{ ref('stg_price_snapshots') }}
    where avg_price is not null
    group by event_id, event_name, artist_name, genre, venue_city
    having count(*) >= 3
),

with_zscore as (
    select
        s.event_id,
        s.event_name,
        s.artist_name,
        s.genre,
        s.venue_city,
        s.snapshot_date,
        s.avg_price,
        s.min_price,
        s.max_price,
        s.price_change,
        s.price_change_pct,
        s.days_until_event,
        e.mean_price,
        e.stddev_price,
        case
            when e.stddev_price > 0
            then round(((s.avg_price - e.mean_price) / e.stddev_price)::numeric, 2)
            else 0
        end as z_score
    from {{ ref('stg_price_snapshots') }} s
    inner join event_stats e on s.event_id = e.event_id
    where s.avg_price is not null
)

select
    *,
    case
        when z_score >= 2.0 then 'spike'
        when z_score <= -2.0 then 'drop'
        else 'normal'
    end as anomaly_type,
    abs(z_score) >= 2.0 as is_anomaly
from with_zscore
