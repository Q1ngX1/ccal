"""Tests for src/models/model.py — CalendarEvent model."""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from pydantic import ValidationError

from src.models.model import CalendarEvent


# ── Construction & Defaults ──────────────────────────────────────────

class TestCalendarEventConstruction:
    def test_minimal(self):
        event = CalendarEvent(title="Test", start_time=datetime(2026, 1, 1, 9, 0))
        assert event.title == "Test"
        assert event.end_time is None
        assert event.location is None
        assert event.description is None
        assert event.reminder_minutes is None
        assert event.recurrence is None
        assert event.attendees == []
        assert event.timezone is None

    def test_full(self, full_event):
        assert full_event.title == "Sprint Review"
        assert full_event.attendees == ["alice@example.com", "bob@example.com"]
        assert full_event.recurrence == "FREQ=WEEKLY;BYDAY=FR"

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            CalendarEvent(start_time=datetime(2026, 1, 1))

    def test_missing_start_time_raises(self):
        with pytest.raises(ValidationError):
            CalendarEvent(title="No time")


# ── get_timezone ─────────────────────────────────────────────────────

class TestGetTimezone:
    def test_explicit_timezone(self, sample_event):
        assert sample_event.get_timezone() == "Asia/Shanghai"

    def test_geo_fallback(self, minimal_event):
        geo = MagicMock()
        geo.timezone = "Europe/London"
        with patch("src.input.geo.get_geo_info", return_value=geo):
            assert minimal_event.get_timezone() == "Europe/London"

    def test_utc_fallback(self, minimal_event):
        geo = MagicMock()
        geo.timezone = None
        with patch("src.input.geo.get_geo_info", return_value=geo):
            assert minimal_event.get_timezone() == "UTC"


# ── to_ical ──────────────────────────────────────────────────────────

class TestToIcal:
    def test_basic_ical(self, sample_event):
        cal = sample_event.to_ical()
        ical_str = cal.to_ical().decode()
        assert "BEGIN:VCALENDAR" in ical_str
        assert "BEGIN:VEVENT" in ical_str
        assert "Team Meeting" in ical_str
        assert "Room 301" in ical_str
        assert "Weekly sync" in ical_str

    def test_ical_with_alarm(self, sample_event):
        cal = sample_event.to_ical()
        ical_str = cal.to_ical().decode()
        assert "BEGIN:VALARM" in ical_str
        assert "TRIGGER" in ical_str

    def test_ical_no_alarm_when_no_reminder(self, minimal_event):
        with patch("src.input.geo.get_geo_info", return_value=MagicMock(timezone="UTC")):
            cal = minimal_event.to_ical()
            ical_str = cal.to_ical().decode()
            assert "VALARM" not in ical_str

    def test_ical_with_recurrence(self, full_event):
        cal = full_event.to_ical()
        ical_str = cal.to_ical().decode()
        assert "RRULE" in ical_str
        assert "FREQ=WEEKLY" in ical_str

    def test_ical_with_attendees(self, full_event):
        cal = full_event.to_ical()
        ical_str = cal.to_ical().decode()
        assert "mailto:alice@example.com" in ical_str
        assert "mailto:bob@example.com" in ical_str

    def test_ical_minimal_event(self, minimal_event):
        with patch("src.input.geo.get_geo_info", return_value=MagicMock(timezone="UTC")):
            cal = minimal_event.to_ical()
            ical_str = cal.to_ical().decode()
            assert "Quick Call" in ical_str
            # No DTEND for minimal event
            assert "DTEND" not in ical_str

    def test_ical_invalid_timezone_fallback(self):
        """Invalid timezone should fall back to tz=None (naive datetime)."""
        event = CalendarEvent(
            title="Bad TZ",
            start_time=datetime(2026, 4, 20, 10, 0),
            end_time=datetime(2026, 4, 20, 11, 0),
            timezone="Invalid/Timezone_That_Doesnt_Exist",
        )
        cal = event.to_ical()
        ical_str = cal.to_ical().decode()
        assert "Bad TZ" in ical_str
        assert "DTSTART" in ical_str
        assert "DTEND" in ical_str


# ── to_google_event ──────────────────────────────────────────────────

class TestToGoogleEvent:
    def test_basic_google_event(self, sample_event):
        ge = sample_event.to_google_event()
        assert ge["summary"] == "Team Meeting"
        assert ge["start"]["timeZone"] == "Asia/Shanghai"
        assert ge["end"]["timeZone"] == "Asia/Shanghai"
        assert ge["location"] == "Room 301"
        assert ge["description"] == "Weekly sync"

    def test_google_event_default_end(self, minimal_event):
        """When end_time is None, should default to start + 1 hour."""
        with patch("src.input.geo.get_geo_info", return_value=MagicMock(timezone="UTC")):
            ge = minimal_event.to_google_event()
            expected_end = (minimal_event.start_time + timedelta(hours=1)).isoformat()
            assert ge["end"]["dateTime"] == expected_end

    def test_google_event_recurrence(self, full_event):
        ge = full_event.to_google_event()
        assert ge["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=FR"]

    def test_google_event_reminders(self, sample_event):
        ge = sample_event.to_google_event()
        assert ge["reminders"]["useDefault"] is False
        assert ge["reminders"]["overrides"][0]["minutes"] == 15

    def test_google_event_attendees(self, full_event):
        ge = full_event.to_google_event()
        emails = [a["email"] for a in ge["attendees"]]
        assert "alice@example.com" in emails
        assert "bob@example.com" in emails

    def test_google_event_no_optional_fields(self, minimal_event):
        with patch("src.input.geo.get_geo_info", return_value=MagicMock(timezone="UTC")):
            ge = minimal_event.to_google_event()
            assert "location" not in ge
            assert "description" not in ge
            assert "recurrence" not in ge
            assert "reminders" not in ge
            assert "attendees" not in ge


# ── Serialization roundtrip ──────────────────────────────────────────

class TestSerialization:
    def test_model_dump_roundtrip(self, full_event):
        data = full_event.model_dump()
        restored = CalendarEvent(**data)
        assert restored.title == full_event.title
        assert restored.start_time == full_event.start_time
        assert restored.attendees == full_event.attendees

    def test_json_roundtrip(self, full_event):
        json_str = full_event.model_dump_json()
        restored = CalendarEvent.model_validate_json(json_str)
        assert restored == full_event
