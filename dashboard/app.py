import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Concert Price Tracker",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("DUCKDB_PATH", str(PROJECT_ROOT / "data" / "concert_tracker.duckdb"))

COLORS = {
    "primary": "#6366F1",
    "secondary": "#8B5CF6",
    "accent": "#06B6D4",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "surface": "#1E293B",
    "text": "#F1F5F9",
    "muted": "#94A3B8",
}

CHART_TEMPLATE = "plotly_dark"
CHART_COLORS = ["#6366F1", "#8B5CF6", "#06B6D4", "#10B981", "#F59E0B", "#EF4444", "#EC4899"]

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1E293B 0%, #334155 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem 1.25rem;
    }
    [data-testid="stMetric"] label { color: #94A3B8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    [data-testid="stMetric"] [data-testid="stMetricValue"] { color: #F1F5F9; font-size: 1.8rem; font-weight: 700; }
    [data-testid="stMetric"] [data-testid="stMetricDelta"] { font-size: 0.85rem; }
    div[data-testid="stTabs"] button { font-weight: 600; font-size: 0.95rem; }
    div[data-testid="stTabs"] button[aria-selected="true"] { border-bottom-color: #6366F1; color: #6366F1; }
    .stDataFrame { border-radius: 8px; }
    section[data-testid="stSidebar"] > div { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)


def query(sql: str) -> pd.DataFrame:
    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        return conn.execute(sql).fetchdf()
    finally:
        conn.close()


def style_chart(fig, height=420):
    fig.update_layout(
        template=CHART_TEMPLATE,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color="#F1F5F9"),
        title_font=dict(size=16, color="#F1F5F9"),
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(gridcolor="#334155", zerolinecolor="#334155"),
        yaxis=dict(gridcolor="#334155", zerolinecolor="#334155"),
    )
    return fig


# --- Data availability check ---
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


# --- Header ---
st.markdown("# Concert Price Tracker")
st.markdown(
    '<p style="color: #94A3B8; margin-top: -1rem; margin-bottom: 1.5rem;">'
    "Track ticket prices over time. Find the best moment to buy.</p>",
    unsafe_allow_html=True,
)


# --- KPI Metrics ---
stats = query("""
    SELECT
        COUNT(DISTINCT event_id) AS total_events,
        COUNT(DISTINCT artist_name) AS total_artists,
        COUNT(DISTINCT snapshot_date) AS days_tracked,
        ROUND(AVG((min_price + max_price) / 2.0), 0) AS avg_price,
        ROUND(MIN(min_price), 0) AS lowest_price,
        MAX(snapshot_date) AS last_updated
    FROM raw.events
    WHERE min_price IS NOT NULL
""")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Events Tracked", f"{int(stats['total_events'].iloc[0]):,}")
col2.metric("Artists", f"{int(stats['total_artists'].iloc[0]):,}")
col3.metric("Days of Data", f"{int(stats['days_tracked'].iloc[0])}")
col4.metric("Avg Ticket Price", f"${int(stats['avg_price'].iloc[0])}")
col5.metric("Lowest Seen", f"${int(stats['lowest_price'].iloc[0])}")

st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)


# --- Sidebar Filters ---
with st.sidebar:
    st.markdown("### Filters")
    st.markdown("")

    genres = query("SELECT DISTINCT genre FROM raw.events WHERE genre IS NOT NULL ORDER BY genre")
    selected_genre = st.selectbox("Genre", ["All Genres"] + genres["genre"].tolist())

    cities = query("SELECT DISTINCT venue_city FROM raw.events WHERE venue_city IS NOT NULL ORDER BY venue_city")
    selected_city = st.selectbox("City", ["All Cities"] + cities["venue_city"].tolist())

    st.markdown("---")
    st.markdown(
        f'<p style="color: #64748B; font-size: 0.75rem;">Last updated: {stats["last_updated"].iloc[0]}</p>',
        unsafe_allow_html=True,
    )

genre_filter = f"AND genre = '{selected_genre}'" if selected_genre != "All Genres" else ""
city_filter = f"AND venue_city = '{selected_city}'" if selected_city != "All Cities" else ""


# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["Price Curves", "Sell-Out Speed", "Best Time to Buy", "Event Explorer"])


# --- Tab 1: Price Curves ---
with tab1:
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
                    ELSE 'Day of'
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
        cheapest_idx = price_data["mean_price"].idxmin()
        cheapest_bucket = price_data.loc[cheapest_idx, "days_bucket"]
        cheapest_price = price_data.loc[cheapest_idx, "mean_price"]

        left, right = st.columns([3, 1])
        with left:
            bar_colors = [
                COLORS["success"] if i == cheapest_idx else COLORS["primary"]
                for i in range(len(price_data))
            ]

            fig = go.Figure(data=[
                go.Bar(
                    x=price_data["days_bucket"],
                    y=price_data["mean_price"],
                    marker_color=bar_colors,
                    marker_line_width=0,
                    hovertemplate="<b>%{x}</b><br>Avg: $%{y:.2f}<extra></extra>",
                )
            ])
            fig.update_layout(
                title="Average Ticket Price by Time Until Event",
                xaxis_title="",
                yaxis_title="Avg Price ($)",
                yaxis_tickprefix="$",
                showlegend=False,
            )
            st.plotly_chart(style_chart(fig), use_container_width=True)

        with right:
            st.markdown("<div style='height: 3rem'></div>", unsafe_allow_html=True)
            st.metric("Best Buy Window", cheapest_bucket, f"${cheapest_price:.0f} avg")
            st.metric("Observations", f"{price_data['num_observations'].sum():,}")
            st.caption("Prices tend to rise closer to the event date. Buy early for the best deal.")
    else:
        st.info("No price curve data yet. Run the pipeline for a few days to see trends.")


# --- Tab 2: Sell-Out Speed ---
with tab2:
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
        left, right = st.columns([3, 1])

        with left:
            fig = px.histogram(
                soldout_data,
                x="days_to_sellout",
                nbins=15,
                color_discrete_sequence=[COLORS["secondary"]],
                labels={"days_to_sellout": "Days to Sell Out"},
            )
            fig.update_layout(
                title="Distribution: Days from Listing to Sell-Out",
                xaxis_title="Days to Sell Out",
                yaxis_title="Number of Events",
                bargap=0.1,
            )
            st.plotly_chart(style_chart(fig), use_container_width=True)

        with right:
            st.markdown("<div style='height: 3rem'></div>", unsafe_allow_html=True)
            median_sellout = soldout_data["days_to_sellout"].median()
            fastest = soldout_data["days_to_sellout"].min()
            st.metric("Median Sell-Out", f"{median_sellout:.0f} days")
            st.metric("Fastest Sell-Out", f"{fastest} days")
            st.caption("Events that sell out fastest are typically popular artists in smaller venues.")

        st.markdown("#### Fastest Sell-Outs")
        display_df = (
            soldout_data[["artist_name", "event_name", "venue_city", "days_to_sellout"]]
            .head(15)
            .rename(columns={
                "artist_name": "Artist",
                "event_name": "Event",
                "venue_city": "City",
                "days_to_sellout": "Days to Sell Out",
            })
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No sell-out data yet. This populates after events change to 'offsale' status.")


# --- Tab 3: Best Time to Buy ---
with tab3:
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
        cheapest_day = buy_data.loc[buy_data["mean_price"].idxmin(), "day_name"]
        cheapest_price = buy_data["mean_price"].min()
        priciest_day = buy_data.loc[buy_data["mean_price"].idxmax(), "day_name"]
        priciest_price = buy_data["mean_price"].max()
        savings = priciest_price - cheapest_price

        m1, m2, m3 = st.columns(3)
        m1.metric("Best Day to Buy", cheapest_day, f"${cheapest_price:.0f} avg")
        m2.metric("Most Expensive Day", priciest_day, f"${priciest_price:.0f} avg", delta_color="inverse")
        m3.metric("Potential Savings", f"${savings:.0f}", "per ticket")

        st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

        colors = [
            COLORS["success"] if day == cheapest_day
            else COLORS["danger"] if day == priciest_day
            else COLORS["primary"]
            for day in buy_data["day_name"]
        ]

        fig = go.Figure(data=[
            go.Bar(
                x=buy_data["day_name"],
                y=buy_data["mean_price"],
                marker_color=colors,
                marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>Avg: $%{y:.2f}<extra></extra>",
            )
        ])
        fig.update_layout(
            title="Average Ticket Price by Day of Week",
            xaxis_title="",
            yaxis_title="Avg Price ($)",
            yaxis_tickprefix="$",
            showlegend=False,
        )
        st.plotly_chart(style_chart(fig), use_container_width=True)
    else:
        st.info("Not enough data yet. Need at least 5 observations per day.")


# --- Tab 4: Event Explorer ---
with tab4:
    search = st.text_input("Search by artist or event name", placeholder="e.g. Taylor Swift, Coachella...")
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
        events_sorted = events.sort_values("event_date").head(100)

        upcoming_count = len(events_sorted)
        on_sale = len(events_sorted[events_sorted["status"] == "onsale"])
        avg_range = events_sorted[["min_price", "max_price"]].mean()

        c1, c2, c3 = st.columns(3)
        c1.metric("Upcoming Events", upcoming_count)
        c2.metric("On Sale Now", on_sale)
        c3.metric("Avg Price Range", f"${avg_range['min_price']:.0f} – ${avg_range['max_price']:.0f}")

        st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)

        display = events_sorted.rename(columns={
            "artist_name": "Artist",
            "event_name": "Event",
            "venue_name": "Venue",
            "venue_city": "City",
            "event_date": "Date",
            "min_price": "Min $",
            "max_price": "Max $",
            "status": "Status",
            "genre": "Genre",
        })

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.DatetimeColumn(format="MMM D, YYYY"),
                "Min $": st.column_config.NumberColumn(format="$%.0f"),
                "Max $": st.column_config.NumberColumn(format="$%.0f"),
                "Status": st.column_config.TextColumn(width="small"),
            },
        )
    else:
        st.info("No upcoming events found matching your filters.")
