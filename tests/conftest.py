from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.models.model import CalendarEvent


@pytest.fixture
def sample_event() -> CalendarEvent:
    """A minimal CalendarEvent for testing."""
    return CalendarEvent(
        title="Team Meeting",
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        location="Room 301",
        description="Weekly sync",
        reminder_minutes=15,
        timezone="Asia/Shanghai",
    )


@pytest.fixture
def full_event() -> CalendarEvent:
    """A CalendarEvent with all fields populated."""
    return CalendarEvent(
        title="Sprint Review",
        start_time=datetime(2026, 5, 1, 14, 0),
        end_time=datetime(2026, 5, 1, 15, 30),
        location="Conference Room A",
        description="End-of-sprint demo and review",
        reminder_minutes=30,
        recurrence="FREQ=WEEKLY;BYDAY=FR",
        attendees=["alice@example.com", "bob@example.com"],
        timezone="America/New_York",
    )


@pytest.fixture
def minimal_event() -> CalendarEvent:
    """A CalendarEvent with only required fields."""
    return CalendarEvent(
        title="Quick Call",
        start_time=datetime(2026, 4, 20, 9, 0),
    )
