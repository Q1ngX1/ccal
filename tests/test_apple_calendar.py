"""Tests for src/connections/apple_calendar.py — Apple Calendar via AppleScript."""
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from src.connections.apple_calendar import (
    is_macos,
    create_event,
    list_calendars,
    _format_applescript_date,
    _escape,
)
from src.models.model import CalendarEvent


class TestIsMacos:
    def test_on_darwin(self):
        with patch("src.connections.apple_calendar.platform.system", return_value="Darwin"):
            assert is_macos() is True

    def test_on_linux(self):
        with patch("src.connections.apple_calendar.platform.system", return_value="Linux"):
            assert is_macos() is False


class TestFormatApplescriptDate:
    def test_format(self):
        dt = datetime(2026, 4, 20, 15, 30, 0)
        result = _format_applescript_date(dt)
        assert result == 'date "April 20, 2026 03:30:00 PM"'

    def test_morning(self):
        dt = datetime(2026, 1, 5, 9, 0, 0)
        result = _format_applescript_date(dt)
        assert result == 'date "January 05, 2026 09:00:00 AM"'


class TestEscape:
    def test_no_special_chars(self):
        assert _escape("hello world") == "hello world"

    def test_quotes(self):
        assert _escape('say "hello"') == 'say \\"hello\\"'

    def test_backslash(self):
        assert _escape("path\\to\\file") == "path\\\\to\\\\file"


class TestCreateEvent:
    def test_not_macos_raises(self, sample_event):
        with patch("src.connections.apple_calendar.is_macos", return_value=False):
            with pytest.raises(RuntimeError, match="only available on macOS"):
                create_event(sample_event)

    def test_success_on_macos(self, sample_event):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with (
            patch("src.connections.apple_calendar.is_macos", return_value=True),
            patch("src.connections.apple_calendar.subprocess.run", return_value=mock_result) as mock_run,
        ):
            create_event(sample_event, calendar_name="Work")
            mock_run.assert_called_once()
            args = mock_run.call_args
            script = args[0][0][2]  # ["osascript", "-e", script]
            assert "Team Meeting" in script
            assert "Room 301" in script
            assert "Work" in script

    def test_applescript_error(self, sample_event):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "execution error"

        with (
            patch("src.connections.apple_calendar.is_macos", return_value=True),
            patch("src.connections.apple_calendar.subprocess.run", return_value=mock_result),
        ):
            with pytest.raises(RuntimeError, match="AppleScript error"):
                create_event(sample_event)

    def test_calendar_not_responding_error(self, sample_event):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Calendar doesn't understand the event"

        with (
            patch("src.connections.apple_calendar.is_macos", return_value=True),
            patch("src.connections.apple_calendar.subprocess.run", return_value=mock_result),
        ):
            with pytest.raises(RuntimeError, match="not available or not responding"):
                create_event(sample_event)

    def test_event_without_end_time(self):
        """Event without end_time should use start + 1 hour."""
        event = CalendarEvent(
            title="No End",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )
        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("src.connections.apple_calendar.is_macos", return_value=True),
            patch("src.connections.apple_calendar.subprocess.run", return_value=mock_result) as mock_run,
        ):
            create_event(event)
            script = mock_run.call_args[0][0][2]
            assert "11:00:00" in script  # end = start + 1hr

    def test_event_without_optional_fields(self):
        """Event without location/description should not include them in script."""
        event = CalendarEvent(
            title="Simple",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )
        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("src.connections.apple_calendar.is_macos", return_value=True),
            patch("src.connections.apple_calendar.subprocess.run", return_value=mock_result) as mock_run,
        ):
            create_event(event)
            script = mock_run.call_args[0][0][2]
            assert "location" not in script
            assert "description" not in script


class TestListCalendars:
    def test_not_macos_raises(self):
        with patch("src.connections.apple_calendar.is_macos", return_value=False):
            with pytest.raises(RuntimeError, match="only available on macOS"):
                list_calendars()

    def test_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Home, Work, Family"
        mock_result.stderr = ""

        with (
            patch("src.connections.apple_calendar.is_macos", return_value=True),
            patch("src.connections.apple_calendar.subprocess.run", return_value=mock_result),
        ):
            calendars = list_calendars()
            assert calendars == ["Home", "Work", "Family"]

    def test_empty_result(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with (
            patch("src.connections.apple_calendar.is_macos", return_value=True),
            patch("src.connections.apple_calendar.subprocess.run", return_value=mock_result),
        ):
            calendars = list_calendars()
            assert calendars == []
