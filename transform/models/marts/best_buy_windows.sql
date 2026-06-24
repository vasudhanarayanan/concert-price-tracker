with daily_prices as (
    select
        genre,
        venue_city,
        extract(dow from snapshot_date) as day_of_week,
        extract(hour from ingested_at) as hour_of_day,
        days_until_event,
        avg_price,
        min_price
    from {{ ref('stg_price_snapshots') }}
    where avg_price is not null
),

by_day_of_week as (
    select
        genre,
        venue_city,
        day_of_week,
        case day_of_week
            when 0 then 'Sunday'
            when 1 then 'Monday'
            when 2 then 'Tuesday'
            when 3 then 'Wednesday'
            when 4 then 'Thursday'
            when 5 then 'Friday'
            when 6 then 'Saturday'
        end as day_name,
        count(*) as num_observations,
        round(avg(avg_price)::numeric, 2) as mean_price,
        round(avg(min_price)::numeric, 2) as mean_min_price
    from daily_prices
    group by genre, venue_city, day_of_week
),

ranked as (
    select
        *,
        rank() over (
            partition by genre, venue_city
            order by mean_price asc
        ) as price_rank
    from by_day_of_week
    where num_observations >= 5
)

select * from ranked
