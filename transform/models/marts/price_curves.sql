with bucketed as (
    select
        genre,
        venue_city,
        case
            when days_until_event > 60 then '60+ days'
            when days_until_event > 30 then '30-60 days'
            when days_until_event > 14 then '14-30 days'
            when days_until_event > 7 then '7-14 days'
            when days_until_event > 3 then '3-7 days'
            when days_until_event > 1 then '1-3 days'
            else 'day of'
        end as days_bucket,
        case
            when days_until_event > 60 then 1
            when days_until_event > 30 then 2
            when days_until_event > 14 then 3
            when days_until_event > 7 then 4
            when days_until_event > 3 then 5
            when days_until_event > 1 then 6
            else 7
        end as bucket_order,
        avg_price,
        min_price,
        max_price
    from {{ ref('stg_price_snapshots') }}
    where avg_price is not null
)

select
    genre,
    venue_city,
    days_bucket,
    bucket_order,
    count(*) as num_observations,
    round(avg(avg_price)::numeric, 2) as mean_price,
    round(percentile_cont(0.5) within group (order by avg_price)::numeric, 2) as median_price,
    round(min(min_price)::numeric, 2) as lowest_price_seen,
    round(max(max_price)::numeric, 2) as highest_price_seen
from bucketed
group by genre, venue_city, days_bucket, bucket_order
order by genre, venue_city, bucket_order
