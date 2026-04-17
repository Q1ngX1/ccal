"""Tests for src/models/llm.py — LLM-based event parsing."""
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from src.models.llm import parse_event
from src.models.model import CalendarEvent
from src.input.geo import get_geo_info


def _make_llm_response(content: str) -> MagicMock:
    """Create a mock litellm completion response."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


@pytest.fixture
def mock_config():
    return {
        "llm": {"provider": "openai", "model": "openai/gpt-4o"},
        "output": {"default": "ics"},
        "google": {"calendar_id": "primary"},
    }


@pytest.fixture
def mock_geo():
    geo = MagicMock()
    geo.summary.return_value = "Shanghai, China (timezone: Asia/Shanghai)"
    geo.timezone = "Asia/Shanghai"
    return geo


class TestParseEvent:
    def test_basic_parse(self, mock_config, mock_geo):
        event_json = json.dumps({
            "title": "Lunch with Alice",
            "start_time": "2026-04-20T12:00:00",
            "end_time": "2026-04-20T13:00:00",
            "location": "Cafe",
            "description": None,
            "reminder_minutes": None,
            "recurrence": None,
            "attendees": [],
            "timezone": None,
        })

        with (
            patch("src.models.llm.load_config", return_value=mock_config),
            patch("src.models.llm.get_api_key", return_value="sk-test"),
            patch("src.input.geo.get_geo_info", return_value=mock_geo),
            patch("src.models.llm.litellm.completion", return_value=_make_llm_response(event_json)),
        ):
            event = parse_event("Lunch with Alice tomorrow at noon")
        assert isinstance(event, CalendarEvent)
        assert event.title == "Lunch with Alice"
        assert event.location == "Cafe"

    def test_strips_markdown_fences(self, mock_config, mock_geo):
        event_json = json.dumps({
            "title": "Test",
            "start_time": "2026-04-20T10:00:00",
            "end_time": None,
            "location": None,
            "description": None,
            "reminder_minutes": None,
            "recurrence": None,
            "attendees": [],
            "timezone": None,
        })
        fenced = f"```json\n{event_json}\n```"

        with (
            patch("src.models.llm.load_config", return_value=mock_config),
            patch("src.models.llm.get_api_key", return_value="sk-test"),
            patch("src.input.geo.get_geo_info", return_value=mock_geo),
            patch("src.models.llm.litellm.completion", return_value=_make_llm_response(fenced)),
        ):
            event = parse_event("test event")
        assert event.title == "Test"

    def test_no_api_key_raises(self, mock_config, mock_geo):
        with (
            patch("src.models.llm.load_config", return_value=mock_config),
            patch("src.models.llm.get_api_key", return_value=None),
            patch("src.input.geo.get_geo_info", return_value=mock_geo),
        ):
            with pytest.raises(RuntimeError, match="No API key found"):
                parse_event("test")

    def test_ollama_no_key_needed(self, mock_config, mock_geo):
        mock_config["llm"]["provider"] = "ollama"
        mock_config["llm"]["model"] = "ollama/llama3"
        event_json = json.dumps({
            "title": "Test",
            "start_time": "2026-04-20T10:00:00",
            "end_time": None,
            "location": None,
            "description": None,
            "reminder_minutes": None,
            "recurrence": None,
            "attendees": [],
            "timezone": None,
        })

        with (
            patch("src.models.llm.load_config", return_value=mock_config),
            patch("src.models.llm.get_api_key", return_value=None),
            patch("src.input.geo.get_geo_info", return_value=mock_geo),
            patch("src.models.llm.litellm.completion", return_value=_make_llm_response(event_json)) as mock_comp,
        ):
            event = parse_event("test", provider="ollama", model="ollama/llama3")
            # api_key should not be in kwargs
            call_kwargs = mock_comp.call_args[1]
            assert "api_key" not in call_kwargs

    def test_custom_provider_and_model(self, mock_config, mock_geo):
        event_json = json.dumps({
            "title": "Test",
            "start_time": "2026-04-20T10:00:00",
            "end_time": None,
            "location": None,
            "description": None,
            "reminder_minutes": None,
            "recurrence": None,
            "attendees": [],
            "timezone": None,
        })

        with (
            patch("src.models.llm.load_config", return_value=mock_config),
            patch("src.models.llm.get_api_key", return_value="sk-anthro"),
            patch("src.input.geo.get_geo_info", return_value=mock_geo),
            patch("src.models.llm.litellm.completion", return_value=_make_llm_response(event_json)) as mock_comp,
        ):
            event = parse_event("test", provider="anthropic", model="anthropic/claude-sonnet-4-20250514")
            call_kwargs = mock_comp.call_args[1]
            assert call_kwargs["model"] == "anthropic/claude-sonnet-4-20250514"
            assert call_kwargs["api_key"] == "sk-anthro"

    def test_api_base_passed(self, mock_config, mock_geo):
        mock_config["llm"]["api_base"] = "http://localhost:11434"
        event_json = json.dumps({
            "title": "Test",
            "start_time": "2026-04-20T10:00:00",
            "end_time": None, "location": None, "description": None,
            "reminder_minutes": None, "recurrence": None, "attendees": [], "timezone": None,
        })

        with (
            patch("src.models.llm.load_config", return_value=mock_config),
            patch("src.models.llm.get_api_key", return_value="sk-test"),
            patch("src.input.geo.get_geo_info", return_value=mock_geo),
            patch("src.models.llm.litellm.completion", return_value=_make_llm_response(event_json)) as mock_comp,
        ):
            parse_event("test")
            call_kwargs = mock_comp.call_args[1]
            assert call_kwargs["api_base"] == "http://localhost:11434"

    def test_invalid_json_raises(self, mock_config, mock_geo):
        with (
            patch("src.models.llm.load_config", return_value=mock_config),
            patch("src.models.llm.get_api_key", return_value="sk-test"),
            patch("src.input.geo.get_geo_info", return_value=mock_geo),
            patch("src.models.llm.litellm.completion", return_value=_make_llm_response("not json at all")),
        ):
            with pytest.raises(Exception):
                parse_event("test")

    def test_multiple_events_parse(self, mock_config, mock_geo):
        event_json = json.dumps([
            {
                "title": "Prep Night",
                "start_time": "2026-04-20T18:00:00",
                "end_time": None,
                "location": "Andrew/Angela's home",
                "description": None,
                "reminder_minutes": None,
                "recurrence": None,
                "attendees": [],
                "timezone": None,
            },
            {
                "title": "Boba Chat",
                "start_time": "2026-04-21T15:00:00",
                "end_time": None,
                "location": None,
                "description": "Free boba or coffee",
                "reminder_minutes": None,
                "recurrence": None,
                "attendees": [],
                "timezone": None,
            },
        ])

        with (
            patch("src.models.llm.load_config", return_value=mock_config),
            patch("src.models.llm.get_api_key", return_value="sk-test"),
            patch("src.input.geo.get_geo_info", return_value=mock_geo),
            patch("src.models.llm.litellm.completion", return_value=_make_llm_response(event_json)),
        ):
            events = parse_event("two announcements")

        assert isinstance(events, list)
        assert [event.title for event in events] == ["Prep Night", "Boba Chat"]

    def test_missing_start_time_returns_editable_draft(self, mock_config, mock_geo):
        event_json = json.dumps({
            "title": "Needs Time",
            "start_time": None,
            "end_time": None,
            "location": "Cafe",
            "description": None,
            "reminder_minutes": None,
            "recurrence": None,
            "attendees": [],
            "timezone": None,
        })

        with (
            patch("src.models.llm.load_config", return_value=mock_config),
            patch("src.models.llm.get_api_key", return_value="sk-test"),
            patch("src.input.geo.get_geo_info", return_value=mock_geo),
            patch("src.models.llm.litellm.completion", return_value=_make_llm_response(event_json)),
        ):
            event = parse_event("event without time")

        assert event.title == "Needs Time"
        assert event.start_time is None
