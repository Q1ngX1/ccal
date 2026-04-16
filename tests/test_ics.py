"""Tests for src/connections/ics.py — ICS file export."""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.connections.ics import export_to_ics


class TestExportToIcs:
    def test_default_filename(self, sample_event, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = export_to_ics(sample_event)
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "BEGIN:VCALENDAR" in content
        assert "Team Meeting" in content

    def test_custom_output_path(self, sample_event, tmp_path):
        out = tmp_path / "my_event.ics"
        path = export_to_ics(sample_event, output_path=str(out))
        assert Path(path).exists()
        assert path == str(out.resolve())

    def test_safe_title_sanitization(self, tmp_path, monkeypatch):
        """Special characters in title should be sanitized for filename."""
        from datetime import datetime
        from src.models.model import CalendarEvent

        monkeypatch.chdir(tmp_path)
        event = CalendarEvent(
            title="Meeting: Q1/Q2 Review!",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )
        path = export_to_ics(event)
        filename = Path(path).name
        assert "/" not in filename
        assert ":" not in filename
        assert filename.endswith(".ics")

    def test_ics_file_is_valid(self, full_event, tmp_path):
        out = tmp_path / "full.ics"
        path = export_to_ics(full_event, output_path=str(out))
        content = Path(path).read_bytes()
        # Should be parseable by icalendar
        from icalendar import Calendar
        cal = Calendar.from_ical(content)
        events = list(cal.walk("VEVENT"))
        assert len(events) == 1
        assert str(events[0]["summary"]) == "Sprint Review"
