"""
CLI for managing price alerts.

Usage:
    python -m alerts.manage add --artist "Taylor Swift" --price 100
    python -m alerts.manage add --event-id "abc123" --price 75
    python -m alerts.manage list
    python -m alerts.manage remove --index 0
"""
import argparse
import json
from datetime import datetime

from alerts.check_alerts import ALERTS_FILE, load_alerts, save_alerts


def add_alert(args):
    alerts = load_alerts()
    alert = {
        "target_price": args.price,
        "created_at": str(datetime.now()),
        "triggered": False,
    }
    if args.event_id:
        alert["event_id"] = args.event_id
    if args.artist:
        alert["artist_name"] = args.artist

    alerts.append(alert)
    save_alerts(alerts)
    print(f"Added alert: notify when price <= ${args.price}")
    if args.artist:
        print(f"  Artist: {args.artist}")
    if args.event_id:
        print(f"  Event ID: {args.event_id}")


def list_alerts(args):
    alerts = load_alerts()
    if not alerts:
        print("No alerts configured. Add one with: python -m alerts.manage add --artist 'Name' --price 50")
        return

    print(f"{'#':<4} {'Target':<10} {'Artist/Event':<30} {'Status':<12} {'Created'}")
    print("-" * 80)
    for i, a in enumerate(alerts):
        target = f"${a['target_price']:.0f}"
        identifier = a.get("artist_name") or a.get("event_id", "?")
        status = "TRIGGERED" if a.get("triggered") else "active"
        created = a.get("created_at", "?")[:10]
        print(f"{i:<4} {target:<10} {identifier:<30} {status:<12} {created}")


def remove_alert(args):
    alerts = load_alerts()
    if args.index >= len(alerts):
        print(f"Error: index {args.index} out of range (have {len(alerts)} alerts)")
        return
    removed = alerts.pop(args.index)
    save_alerts(alerts)
    identifier = removed.get("artist_name") or removed.get("event_id", "?")
    print(f"Removed alert #{args.index}: {identifier} <= ${removed['target_price']:.0f}")


def main():
    parser = argparse.ArgumentParser(description="Manage price alerts")
    sub = parser.add_subparsers(dest="command")

    add_p = sub.add_parser("add", help="Add a new price alert")
    add_p.add_argument("--artist", type=str, help="Artist name to watch")
    add_p.add_argument("--event-id", type=str, help="Specific event ID to watch")
    add_p.add_argument("--price", type=float, required=True, help="Target price threshold")

    sub.add_parser("list", help="List all alerts")

    rm_p = sub.add_parser("remove", help="Remove an alert by index")
    rm_p.add_argument("--index", type=int, required=True, help="Alert index to remove")

    args = parser.parse_args()
    if args.command == "add":
        add_alert(args)
    elif args.command == "list":
        list_alerts(args)
    elif args.command == "remove":
        remove_alert(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
