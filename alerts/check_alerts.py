"""
Price alert system — checks user-defined price targets and sends notifications.

Alerts are stored in a JSON file (alerts.json). When a tracked event's price
drops below the target, an email notification is sent via SendGrid.

Usage:
    python -m alerts.check_alerts              # check alerts and notify
    python -m alerts.check_alerts --dry-run    # check without sending
"""
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALERTS_FILE = PROJECT_ROOT / "data" / "alerts.json"
DB_PATH = os.environ.get("DUCKDB_PATH", str(PROJECT_ROOT / "data" / "concert_tracker.duckdb"))


def load_alerts() -> list[dict]:
    if not ALERTS_FILE.exists():
        return []
    with open(ALERTS_FILE) as f:
        return json.load(f)


def save_alerts(alerts: list[dict]):
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2, default=str)


def check_price_alerts(conn: duckdb.DuckDBPyConnection, alerts: list[dict]) -> list[dict]:
    triggered = []

    for alert in alerts:
        if alert.get("triggered"):
            continue

        event_id = alert.get("event_id")
        artist = alert.get("artist_name")
        target_price = alert["target_price"]

        if event_id:
            result = conn.execute("""
                SELECT event_id, name, artist_name, min_price, max_price,
                       (min_price + max_price) / 2.0 AS avg_price, venue_city, event_date
                FROM raw.events
                WHERE event_id = ? AND snapshot_date = (SELECT MAX(snapshot_date) FROM raw.events)
                LIMIT 1
            """, [event_id]).fetchone()
        elif artist:
            result = conn.execute("""
                SELECT event_id, name, artist_name, min_price, max_price,
                       (min_price + max_price) / 2.0 AS avg_price, venue_city, event_date
                FROM raw.events
                WHERE artist_name ILIKE ? AND min_price <= ?
                  AND snapshot_date = (SELECT MAX(snapshot_date) FROM raw.events)
                ORDER BY min_price ASC
                LIMIT 1
            """, [f"%{artist}%", target_price]).fetchone()
        else:
            continue

        if result is None:
            continue

        current_price = result[3]  # min_price
        if current_price is not None and current_price <= target_price:
            triggered.append({
                "alert": alert,
                "event_id": result[0],
                "event_name": result[1],
                "artist_name": result[2],
                "current_price": current_price,
                "avg_price": result[5],
                "venue_city": result[6],
                "event_date": str(result[7]),
            })

    return triggered


def check_anomaly_alerts(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    today = date.today()
    results = conn.execute("""
        WITH latest AS (
            SELECT
                event_id, name, artist_name, genre, venue_city,
                min_price, max_price, (min_price + max_price) / 2.0 AS avg_price,
                snapshot_date
            FROM raw.events
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM raw.events)
              AND min_price IS NOT NULL
        ),
        stats AS (
            SELECT
                event_id,
                AVG((min_price + max_price) / 2.0) AS mean_price,
                STDDEV((min_price + max_price) / 2.0) AS stddev_price,
                COUNT(*) AS n
            FROM raw.events
            WHERE min_price IS NOT NULL
            GROUP BY event_id
            HAVING COUNT(*) >= 3
        )
        SELECT
            l.event_id, l.name, l.artist_name, l.venue_city,
            l.avg_price, s.mean_price, s.stddev_price,
            (l.avg_price - s.mean_price) / s.stddev_price AS z_score
        FROM latest l
        INNER JOIN stats s ON l.event_id = s.event_id
        WHERE s.stddev_price > 0
          AND ABS((l.avg_price - s.mean_price) / s.stddev_price) >= 2.0
        ORDER BY ABS((l.avg_price - s.mean_price) / s.stddev_price) DESC
        LIMIT 20
    """).fetchall()

    anomalies = []
    for row in results:
        z = row[7]
        anomalies.append({
            "event_id": row[0],
            "event_name": row[1],
            "artist_name": row[2],
            "venue_city": row[3],
            "current_price": row[4],
            "mean_price": row[5],
            "z_score": round(z, 2),
            "type": "spike" if z > 0 else "drop",
        })

    return anomalies


def send_email(to_email: str, subject: str, body: str) -> bool:
    api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("ALERT_FROM_EMAIL", "alerts@concertpricetracker.app")

    if not api_key:
        print(f"[SKIP] No SENDGRID_API_KEY set. Would send to {to_email}:")
        print(f"  Subject: {subject}")
        print(f"  Body: {body[:200]}...")
        return False

    import requests
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email, "name": "Concert Price Tracker"},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        },
    )
    if resp.status_code in (200, 202):
        print(f"[SENT] Email to {to_email}: {subject}")
        return True
    else:
        print(f"[ERROR] SendGrid {resp.status_code}: {resp.text}")
        return False


def format_price_alert_email(triggered: list[dict]) -> tuple[str, str]:
    subject = f"Price Alert: {len(triggered)} ticket(s) hit your target!"
    lines = ["Your concert price alerts have been triggered:\n"]
    for t in triggered:
        lines.append(
            f"  {t['artist_name']} — {t['event_name']}\n"
            f"  Current price: ${t['current_price']:.0f} (target: ${t['alert']['target_price']:.0f})\n"
            f"  {t['venue_city']} | {t['event_date']}\n"
        )
    lines.append("\n— Concert Price Tracker")
    return subject, "\n".join(lines)


def format_anomaly_email(anomalies: list[dict]) -> tuple[str, str]:
    drops = [a for a in anomalies if a["type"] == "drop"]
    spikes = [a for a in anomalies if a["type"] == "spike"]

    subject = f"Price Anomalies: {len(drops)} drops, {len(spikes)} spikes detected"
    lines = ["Unusual price movements detected today:\n"]

    if drops:
        lines.append("PRICE DROPS:")
        for a in drops[:10]:
            lines.append(
                f"  {a['artist_name']} — ${a['current_price']:.0f} "
                f"(avg ${a['mean_price']:.0f}, z={a['z_score']})"
            )
        lines.append("")

    if spikes:
        lines.append("PRICE SPIKES:")
        for a in spikes[:10]:
            lines.append(
                f"  {a['artist_name']} — ${a['current_price']:.0f} "
                f"(avg ${a['mean_price']:.0f}, z={a['z_score']})"
            )
        lines.append("")

    lines.append("— Concert Price Tracker")
    return subject, "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv

    conn = duckdb.connect(DB_PATH, read_only=True)

    # Check price alerts
    alerts = load_alerts()
    active_alerts = [a for a in alerts if not a.get("triggered")]
    print(f"Checking {len(active_alerts)} active price alerts...")

    triggered = check_price_alerts(conn, alerts)
    if triggered:
        print(f"  {len(triggered)} alert(s) triggered!")
        notify_email = os.environ.get("ALERT_EMAIL")
        if notify_email and not dry_run:
            subject, body = format_price_alert_email(triggered)
            send_email(notify_email, subject, body)
        elif dry_run:
            subject, body = format_price_alert_email(triggered)
            print(f"\n[DRY RUN] Would send:\n  Subject: {subject}\n  Body:\n{body}\n")

        # Mark alerts as triggered
        for t in triggered:
            for a in alerts:
                if a.get("event_id") == t["alert"].get("event_id") or \
                   a.get("artist_name") == t["alert"].get("artist_name"):
                    a["triggered"] = True
                    a["triggered_at"] = str(datetime.now())
                    a["triggered_price"] = t["current_price"]
        if not dry_run:
            save_alerts(alerts)
    else:
        print("  No alerts triggered.")

    # Check anomalies
    print("\nChecking for price anomalies...")
    anomalies = check_anomaly_alerts(conn)
    if anomalies:
        print(f"  {len(anomalies)} anomalies found!")
        notify_email = os.environ.get("ALERT_EMAIL")
        if notify_email and not dry_run:
            subject, body = format_anomaly_email(anomalies)
            send_email(notify_email, subject, body)
        elif dry_run:
            subject, body = format_anomaly_email(anomalies)
            print(f"\n[DRY RUN] Would send:\n  Subject: {subject}\n  Body:\n{body}\n")
    else:
        print("  No anomalies detected.")

    conn.close()


if __name__ == "__main__":
    main()
