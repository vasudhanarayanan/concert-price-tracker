from ingestion.ticketmaster_client import TicketmasterClient


SAMPLE_EVENT = {
    "id": "vvG1iZ4kFmTPLS",
    "name": "Taylor Swift | The Eras Tour",
    "dates": {
        "start": {"localDate": "2025-03-15", "dateTime": "2025-03-15T19:00:00Z"},
        "status": {"code": "onsale"},
    },
    "priceRanges": [{"min": 49.50, "max": 449.50, "currency": "USD"}],
    "classifications": [
        {
            "genre": {"name": "Pop"},
            "subGenre": {"name": "Pop"},
        }
    ],
    "_embedded": {
        "venues": [
            {
                "name": "SoFi Stadium",
                "city": {"name": "Los Angeles"},
                "state": {"stateCode": "CA"},
                "upcomingEvents": {"_total": 25},
            }
        ],
        "attractions": [{"name": "Taylor Swift"}],
    },
    "url": "https://www.ticketmaster.com/event/vvG1iZ4kFmTPLS",
}


def test_parse_event():
    client = TicketmasterClient.__new__(TicketmasterClient)
    result = client.parse_event(SAMPLE_EVENT)

    assert result["event_id"] == "vvG1iZ4kFmTPLS"
    assert result["artist_name"] == "Taylor Swift"
    assert result["venue_name"] == "SoFi Stadium"
    assert result["venue_city"] == "Los Angeles"
    assert result["venue_state"] == "CA"
    assert result["genre"] == "Pop"
    assert result["min_price"] == 49.50
    assert result["max_price"] == 449.50
    assert result["status"] == "onsale"


def test_parse_event_missing_fields():
    minimal_event = {
        "id": "abc123",
        "name": "Some Show",
        "dates": {"start": {}, "status": {}},
        "classifications": [{}],
    }
    client = TicketmasterClient.__new__(TicketmasterClient)
    result = client.parse_event(minimal_event)

    assert result["event_id"] == "abc123"
    assert result["artist_name"] == ""
    assert result["min_price"] is None
    assert result["venue_name"] == ""
