import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Concert Price Tracker", layout="wide")
st.title("Concert Price & Availability Tracker")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("DUCKDB_PATH", str(PROJECT_ROOT / "data" / "concert_tracker.duckdb"))


def query(sql: str) -> pd.DataFrame:
    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        return conn.execute(sql).fetchdf()
    finally:
        conn.close()


# --- Check if data exists ---
if not Path(DB_PATH).exists():
    st.warning("No database found. Run the Dagster pipeline first to ingest data.")
    st.stop()

try:
    event_count = query("SELECT COUNT(*) as n FROM raw.events")
    if event_count["n"].iloc[0] == 0:
        st.warning("Database is empty. Run the Dagster pipeline to ingest events.")
        st.stop()
except Exception:
    st.warning("Database not initialized. Run the Dagster pipeline first.")
    st.stop()


# --- Sidebar Filters ---
st.sidebar.header("Filters")

genres = query("SELECT DISTINCT genre FROM raw.events WHERE genre IS NOT NULL ORDER BY genre")
selected_genre = st.sidebar.selectbox("Genre", ["All"] + genres["genre"].tolist())

cities = query("SELECT DISTINCT venue_city FROM raw.events WHERE venue_city IS NOT NULL ORDER BY venue_city")
selected_city = st.sidebar.selectbox("City", ["All"] + cities["venue_city"].tolist())

genre_filter = f"AND genre = '{selected_genre}'" if selected_genre != "All" else ""
city_filter = f"AND venue_city = '{selected_city}'" if selected_city != "All" else ""


# --- Tab Layout ---
tab1, tab2, tab3, tab4 = st.tabs(["Price Curves", "Sell-Out Speed", "Best Time to Buy", "Event Explorer"])

# --- Tab 1: Price Curves ---
with tab1:
    st.subheader("How Prices Change as Event Date Approaches")

    price_data = query(f"""
        WITH base AS (
            SELECT
                event_id,
                min_price,
                max_price,
                (min_price + max_price) / 2.0 AS avg_price,
                genre,
                venue_city,
                DATEDIFF('day', snapshot_date, event_date::DATE) AS days_until_event
            FROM raw.events
            WHERE event_date IS NOT NULL AND min_price IS NOT NULL
            {genre_filter} {city_filter}
        ),
        bucketed AS (
            SELECT *,
                CASE
                    WHEN days_until_event > 60 THEN '60+ days'
                    WHEN days_until_event > 30 THEN '30-60 days'
                    WHEN days_until_event > 14 THEN '14-30 days'
                    WHEN days_until_event > 7 THEN '7-14 days'
                    WHEN days_until_event > 3 THEN '3-7 days'
                    WHEN days_until_event > 1 THEN '1-3 days'
                    ELSE 'day of'
                END AS days_bucket,
                CASE
                    WHEN days_until_event > 60 THEN 1
                    WHEN days_until_event > 30 THEN 2
                    WHEN days_until_event > 14 THEN 3
                    WHEN days_until_event > 7 THEN 4
                    WHEN days_until_event > 3 THEN 5
                    WHEN days_until_event > 1 THEN 6
                    ELSE 7
                END AS bucket_order
            FROM base
        )
        SELECT
            days_bucket,
            bucket_order,
            COUNT(*) AS num_observations,
            ROUND(AVG(avg_price), 2) AS mean_price,
            ROUND(MEDIAN(avg_price), 2) AS median_price
        FROM bucketed
        GROUP BY days_bucket, bucket_order
        ORDER BY bucket_order
    """)

    if not price_data.empty:
        fig = px.bar(
            price_data,
            x="days_bucket",
            y="mean_price",
            title="Average Ticket Price by Time Until Event",
            labels={"days_bucket": "Days Until Event", "mean_price": "Avg Price ($)"},
            color="mean_price",
            color_continuous_scale="RdYlGn_r",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.metric(
            "Cheapest Window",
            price_data.loc[price_data["mean_price"].idxmin(), "days_bucket"],
        )
    else:
        st.info("No price curve data yet. Run the pipeline for a few days to see trends.")

# --- Tab 2: Sell-Out Speed ---
with tab2:
    st.subheader("How Fast Events Sell Out")

    soldout_data = query(f"""
        WITH status_changes AS (
            SELECT
                event_id,
                name AS event_name,
                artist_name,
                genre,
                venue_city,
                MIN(snapshot_date) AS first_seen_date,
                MIN(CASE WHEN status = 'offsale' THEN snapshot_date END) AS soldout_date
            FROM raw.events
            WHERE 1=1 {genre_filter} {city_filter}
            GROUP BY event_id, name, artist_name, genre, venue_city
        )
        SELECT
            artist_name,
            event_name,
            venue_city,
            genre,
            DATEDIFF('day', first_seen_date, soldout_date) AS days_to_sellout
        FROM status_changes
        WHERE soldout_date IS NOT NULL
        ORDER BY days_to_sellout ASC
        LIMIT 50
    """)

    if not soldout_data.empty:
        fig = px.histogram(
            soldout_data,
            x="days_to_sellout",
            nbins=20,
            title="Distribution: Days from First Listing to Sell-Out",
            labels={"days_to_sellout": "Days to Sell Out"},
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            soldout_data[["artist_name", "event_name", "venue_city", "days_to_sellout"]]
            .head(20)
            .rename(columns={
                "artist_name": "Artist",
                "event_name": "Event",
                "venue_city": "City",
                "days_to_sellout": "Days to Sell Out",
            }),
            use_container_width=True,
        )
    else:
        st.info("No sell-out data yet. This populates after events change to 'offsale' status.")

# --- Tab 3: Best Time to Buy ---
with tab3:
    st.subheader("Best Day of Week to Buy Tickets")

    buy_data = query(f"""
        WITH daily_prices AS (
            SELECT
                genre,
                venue_city,
                DAYOFWEEK(snapshot_date) AS day_of_week,
                DAYNAME(snapshot_date) AS day_name,
                (min_price + max_price) / 2.0 AS avg_price,
                min_price
            FROM raw.events
            WHERE min_price IS NOT NULL
            {genre_filter} {city_filter}
        )
        SELECT
            day_name,
            day_of_week,
            COUNT(*) AS num_observations,
            ROUND(AVG(avg_price), 2) AS mean_price,
            ROUND(AVG(min_price), 2) AS mean_min_price
        FROM daily_prices
        GROUP BY day_name, day_of_week
        HAVING COUNT(*) >= 5
        ORDER BY day_of_week
    """)

    if not buy_data.empty:
        fig = px.line(
            buy_data,
            x="day_name",
            y="mean_price",
            title="Average Price by Day of Week",
            labels={"day_name": "Day", "mean_price": "Avg Price ($)"},
            markers=True,
        )
        st.plotly_chart(fig, use_container_width=True)

        cheapest_day = buy_data.loc[buy_data["mean_price"].idxmin(), "day_name"]
        st.success(f"Best day to buy: **{cheapest_day}**")
    else:
        st.info("Not enough data yet. Need at least 5 observations per day.")

# --- Tab 4: Event Explorer ---
with tab4:
    st.subheader("Browse Upcoming Events")

    search = st.text_input("Search artist or event name")
    search_filter = f"AND (artist_name ILIKE '%{search}%' OR name ILIKE '%{search}%')" if search else ""

    events = query(f"""
        SELECT DISTINCT ON (event_id)
            artist_name, name AS event_name, venue_name, venue_city,
            event_date, min_price, max_price, status, genre
        FROM raw.events
        WHERE event_date > NOW() {genre_filter} {city_filter} {search_filter}
        ORDER BY event_id, snapshot_date DESC
    """)

    if not events.empty:
        st.dataframe(
            events.sort_values("event_date").head(100).rename(columns={
                "artist_name": "Artist",
                "event_name": "Event",
                "venue_name": "Venue",
                "venue_city": "City",
                "event_date": "Date",
                "min_price": "Min $",
                "max_price": "Max $",
                "status": "Status",
                "genre": "Genre",
            }),
            use_container_width=True,
        )
    else:
        st.info("No upcoming events found matching your filters.")


# --- Footer ---
st.divider()
stats = query("SELECT COUNT(DISTINCT snapshot_date) AS days, COUNT(DISTINCT event_id) AS events FROM raw.events")
st.caption(
    f"Tracking {stats['events'].iloc[0]:,} unique events "
    f"across {stats['days'].iloc[0]} days of snapshots"
)
