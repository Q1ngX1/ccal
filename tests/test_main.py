"""Tests for src/main.py — CLI commands and helpers."""
import json
import sys
from datetime import datetime
from io import StringIO
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
import typer
from typer.testing import CliRunner

from src.main import (
    app,
    display_event,
    display_events,
    output_event,
    confirm_and_output,
    edit_event,
    read_stdin,
    _resolve_input,
    _parse_with_retry,
)
from src.models.model import CalendarEvent, ParsedCalendarEvent

runner = CliRunner()


# ── Helper function tests ────────────────────────────────────────────

class TestResolveInput:
    def test_plain_text(self):
        result = _resolve_input("Meeting tomorrow at 3pm", None)
        assert result == "Meeting tomorrow at 3pm"

    def test_stdin_dash(self):
        with patch("src.main.read_stdin", return_value="stdin text"):
            result = _resolve_input("-", None)
            assert result == "stdin text"

    def test_stdin_none(self):
        with patch("src.main.read_stdin", return_value="piped text"):
            result = _resolve_input(None, None)
            assert result == "piped text"

    def test_stdin_empty_exits(self):
        with patch("src.main.read_stdin", return_value=None):
            with pytest.raises((SystemExit, typer.Exit)):
                _resolve_input(None, None)

    def test_image_file(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        with (
            patch("src.main.is_image_file", return_value=True),
            patch("src.input.ocr.extract_text", return_value="OCR text") as mock_ocr,
        ):
            result = _resolve_input(str(img), "chi_sim")
            mock_ocr.assert_called_once_with(str(img), language="chi_sim")
            assert result == "OCR text"

    def test_image_empty_ocr_exits(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        with (
            patch("src.main.is_image_file", return_value=True),
            patch("src.input.ocr.extract_text", return_value=""),
        ):
            with pytest.raises((SystemExit, typer.Exit)):
                _resolve_input(str(img), None)


class TestParseWithRetry:
    def test_success_first_try(self):
        event = CalendarEvent(title="Test", start_time=datetime(2026, 4, 20, 10, 0), timezone="UTC")
        with patch("src.main.parse_event", return_value=event):
            result = _parse_with_retry("test text")
            assert result.title == "Test"

    def test_retry_on_json_error(self):
        event = CalendarEvent(title="Test", start_time=datetime(2026, 4, 20, 10, 0), timezone="UTC")
        with patch("src.main.parse_event", side_effect=[
            json.JSONDecodeError("fail", "", 0),
            event,
        ]):
            result = _parse_with_retry("test text", retries=3)
            assert result.title == "Test"

    def test_all_retries_fail_exits(self):
        with patch("src.main.parse_event", side_effect=RuntimeError("LLM error")):
            with pytest.raises((SystemExit, typer.Exit)):
                _parse_with_retry("test text", retries=2)


class TestDisplayEvent:
    def test_json_output(self, sample_event, capsys):
        display_event(sample_event, as_json=True)
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["title"] == "Team Meeting"
        assert data["timezone"] == "Asia/Shanghai"

    def test_table_output(self, sample_event, capsys):
        display_event(sample_event, as_json=False)
        output = capsys.readouterr().out
        assert "Team Meeting" in output

    def test_multiple_json_output(self, capsys):
        events = [
            CalendarEvent(title="First", start_time=datetime(2026, 4, 20, 10, 0), timezone="UTC"),
            ParsedCalendarEvent(title="Second", start_time=None, timezone="UTC"),
        ]
        display_events(events, as_json=True)
        output = capsys.readouterr().out
        data = json.loads(output)
        assert [item["title"] for item in data] == ["First", "Second"]
        assert data[1]["start_time"] is None


# ── CLI command tests ────────────────────────────────────────────────

class TestAddCommand:
    def test_add_with_json_output(self):
        event = CalendarEvent(
            title="CLI Test",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )
        with (
            patch("src.main._resolve_input", return_value="test text"),
            patch("src.main._parse_with_retry", return_value=event),
        ):
            result = runner.invoke(app, ["add", "test text", "--json"])
            assert result.exit_code == 0
            assert "CLI Test" in result.output

    def test_add_with_yes_ics(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        event = CalendarEvent(
            title="Auto Event",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )
        with (
            patch("src.main._resolve_input", return_value="test"),
            patch("src.main._parse_with_retry", return_value=event),
            patch("src.main.load_config", return_value={"output": {"default": "ics"}}),
        ):
            result = runner.invoke(app, ["add", "test", "-y"])
            assert result.exit_code == 0
            assert "ICS file saved" in result.output


class TestParseCommand:
    def test_parse_json(self):
        event = CalendarEvent(
            title="Parsed Event",
            start_time=datetime(2026, 4, 20, 14, 0),
            timezone="UTC",
        )
        with (
            patch("src.main._resolve_input", return_value="test"),
            patch("src.main._parse_with_retry", return_value=event),
        ):
            result = runner.invoke(app, ["parse", "meeting tomorrow", "--json"])
            assert result.exit_code == 0
            assert "Parsed Event" in result.output

    def test_parse_table(self):
        event = CalendarEvent(
            title="Table Event",
            start_time=datetime(2026, 4, 20, 14, 0),
            timezone="UTC",
        )
        with (
            patch("src.main._resolve_input", return_value="test"),
            patch("src.main._parse_with_retry", return_value=event),
        ):
            result = runner.invoke(app, ["parse", "meeting"])
            assert result.exit_code == 0
            assert "Table Event" in result.output


class TestConfigCommand:
    def test_show_config(self):
        with (
            patch("src.main.load_config", return_value={
                "llm": {"provider": "openai", "model": "openai/gpt-4o"},
                "output": {"default": "ics"},
                "google": {"calendar_id": "primary"},
            }),
            patch("src.main.get_api_key", return_value="sk-test"),
        ):
            result = runner.invoke(app, ["config"])
            assert result.exit_code == 0
            assert "openai" in result.output


class TestVersionFlag:
    def test_version(self):
        with patch("importlib.metadata.version", return_value="0.1.0"):
            result = runner.invoke(app, ["--version"])
            assert "0.1.0" in result.output


# ── output_event tests ───────────────────────────────────────────────

class TestOutputEvent:
    def _event(self):
        return CalendarEvent(
            title="Output Test",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )

    def test_ics_output(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("src.main.load_config", return_value={"output": {"default": "ics"}}):
            output_event(self._event(), None)
        assert any(f.suffix == ".ics" for f in tmp_path.iterdir())

    def test_ics_explicit(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("src.main.load_config", return_value={"output": {"default": "google"}}):
            output_event(self._event(), "ics")
        assert any(f.suffix == ".ics" for f in tmp_path.iterdir())

    def test_google_output(self):
        mock_service = MagicMock()
        mock_result = {"id": "evt1", "htmlLink": "https://cal.google.com/evt1"}
        with (
            patch("src.main.load_config", return_value={"output": {"default": "google"}}),
            patch("src.connections.google_calendar.authenticate", return_value=mock_service),
            patch("src.connections.google_calendar.create_event", return_value=mock_result),
        ):
            output_event(self._event(), "google")

    def test_apple_fallback_on_linux(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with (
            patch("src.main.load_config", return_value={"output": {"default": "apple"}}),
            patch("src.connections.apple_calendar.is_macos", return_value=False),
        ):
            output_event(self._event(), "apple")
        # Should fall back to ICS
        assert any(f.suffix == ".ics" for f in tmp_path.iterdir())

    def test_apple_on_macos(self):
        with (
            patch("src.main.load_config", return_value={"output": {"default": "apple"}, "apple": {"calendar_name": "Work"}}),
            patch("src.connections.apple_calendar.is_macos", return_value=True),
            patch("src.connections.apple_calendar.create_event") as mock_create,
        ):
            output_event(self._event(), "apple")
            mock_create.assert_called_once()
            assert mock_create.call_args[1]["calendar_name"] == "Work"


# ── confirm_and_output tests ─────────────────────────────────────────

class TestConfirmAndOutput:
    def _event(self):
        return CalendarEvent(
            title="Confirm Test",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )

    def test_yes_skips_prompt(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("src.main.load_config", return_value={"output": {"default": "ics"}}):
            confirm_and_output(self._event(), "ics", yes=True)
        assert any(f.suffix == ".ics" for f in tmp_path.iterdir())

    def test_user_confirms_y(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with (
            patch("src.main.Prompt.ask", return_value="y"),
            patch("src.main.load_config", return_value={"output": {"default": "ics"}}),
        ):
            confirm_and_output(self._event(), "ics", yes=False)
        assert any(f.suffix == ".ics" for f in tmp_path.iterdir())

    def test_user_cancels_n(self):
        with patch("src.main.Prompt.ask", return_value="n"):
            with pytest.raises((SystemExit, typer.Exit)):
                confirm_and_output(self._event(), "ics", yes=False)

    def test_user_edits_then_saves(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        edited = CalendarEvent(
            title="Edited",
            start_time=datetime(2026, 4, 20, 11, 0),
            timezone="UTC",
        )
        with (
            patch("src.main.Prompt.ask", side_effect=["e", "y"]),
            patch("src.main.edit_event", return_value=edited),
            patch("src.main.load_config", return_value={"output": {"default": "ics"}}),
        ):
            confirm_and_output(self._event(), "ics", yes=False)

    def test_user_edits_then_cancels(self):
        edited = CalendarEvent(
            title="Edited",
            start_time=datetime(2026, 4, 20, 11, 0),
            timezone="UTC",
        )
        with (
            patch("src.main.Prompt.ask", side_effect=["e", "n"]),
            patch("src.main.edit_event", return_value=edited),
        ):
            with pytest.raises((SystemExit, typer.Exit)):
                confirm_and_output(self._event(), "ics", yes=False)

    def test_user_edits_twice_then_saves(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        edited1 = CalendarEvent(
            title="First Edit",
            start_time=datetime(2026, 4, 20, 11, 0),
            timezone="UTC",
        )
        edited2 = CalendarEvent(
            title="Second Edit",
            start_time=datetime(2026, 4, 20, 12, 0),
            timezone="UTC",
        )
        with (
            patch("src.main.Prompt.ask", side_effect=["e", "e", "y"]),
            patch("src.main.edit_event", side_effect=[edited1, edited2]),
            patch("src.main.load_config", return_value={"output": {"default": "ics"}}),
        ):
            confirm_and_output(self._event(), "ics", yes=False)

    def test_multiple_user_confirms_all(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        events = [
            CalendarEvent(title="First", start_time=datetime(2026, 4, 20, 10, 0), timezone="UTC"),
            CalendarEvent(title="Second", start_time=datetime(2026, 4, 21, 10, 0), timezone="UTC"),
        ]
        with (
            patch("src.main.Prompt.ask", return_value="y"),
            patch("src.main.load_config", return_value={"output": {"default": "ics"}}),
        ):
            confirm_and_output(events, "ics", yes=False)
        assert len(list(tmp_path.glob("*.ics"))) == 2

    def test_multiple_user_edits_one_event(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        events = [
            CalendarEvent(title="First", start_time=datetime(2026, 4, 20, 10, 0), timezone="UTC"),
            CalendarEvent(title="Second", start_time=datetime(2026, 4, 21, 10, 0), timezone="UTC"),
        ]
        edited = CalendarEvent(title="Edited Second", start_time=datetime(2026, 4, 21, 11, 0), timezone="UTC")
        with (
            patch("src.main.Prompt.ask", side_effect=["e", "2", "y"]),
            patch("src.main.edit_event", return_value=edited),
            patch("src.main.load_config", return_value={"output": {"default": "ics"}}),
        ):
            confirm_and_output(events, "ics", yes=False)
        assert (tmp_path / "Edited Second.ics").exists()

    def test_multiple_user_removes_event(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        events = [
            CalendarEvent(title="Keep", start_time=datetime(2026, 4, 20, 10, 0), timezone="UTC"),
            CalendarEvent(title="Remove", start_time=datetime(2026, 4, 21, 10, 0), timezone="UTC"),
        ]
        with (
            patch("src.main.Prompt.ask", side_effect=["r", "2", "y"]),
            patch("src.main.load_config", return_value={"output": {"default": "ics"}}),
        ):
            confirm_and_output(events, "ics", yes=False)
        assert (tmp_path / "Keep.ics").exists()
        assert not (tmp_path / "Remove.ics").exists()

    def test_multiple_missing_time_retries_after_edit(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        events = [
            CalendarEvent(title="Complete", start_time=datetime(2026, 4, 20, 10, 0), timezone="UTC"),
            ParsedCalendarEvent(title="Needs Time", start_time=None, timezone="UTC"),
        ]
        edited = CalendarEvent(title="Needs Time", start_time=datetime(2026, 4, 21, 10, 0), timezone="UTC")
        with (
            patch("src.main.Prompt.ask", side_effect=["y", "e", "2", "y"]),
            patch("src.main.edit_event", return_value=edited),
            patch("src.main.load_config", return_value={"output": {"default": "ics"}}),
        ):
            confirm_and_output(events, "ics", yes=False)
        assert len(list(tmp_path.glob("*.ics"))) == 2


# ── edit_event tests ─────────────────────────────────────────────────

class TestEditEvent:
    def _event(self):
        return CalendarEvent(
            title="Original",
            start_time=datetime(2026, 4, 20, 10, 0),
            end_time=datetime(2026, 4, 20, 11, 0),
            location="Room A",
            timezone="UTC",
        )

    def _mock_editor(self, edited_content):
        """Return a side_effect function that writes edited_content to the temp file."""
        def side_effect(args, **kwargs):
            # args[1] is the temp file path
            with open(args[1], "w") as f:
                f.write(edited_content)
            return MagicMock(returncode=0)
        return side_effect

    def test_edit_title(self):
        edited = (
            "title: New Title\n"
            "start_time: 2026-04-20 10:00\n"
            "end_time: 2026-04-20 11:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.title == "New Title"

    def test_edit_location_to_empty(self):
        edited = (
            "title: Original\n"
            "start_time: 2026-04-20 10:00\n"
            "end_time: 2026-04-20 11:00\n"
            "location: -\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.location is None

    def test_edit_start_time(self):
        edited = (
            "title: Original\n"
            "start_time: 2026-05-01 14:00\n"
            "end_time: 2026-05-01 15:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.start_time == datetime(2026, 5, 1, 14, 0)
            assert result.end_time == datetime(2026, 5, 1, 15, 0)

    def test_edit_reminder_minutes(self):
        edited = (
            "title: Original\n"
            "start_time: 2026-04-20 10:00\n"
            "end_time: 2026-04-20 11:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: 30\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.reminder_minutes == 30

    def test_edit_reminder_clear(self):
        event = CalendarEvent(
            title="Test",
            start_time=datetime(2026, 4, 20, 10, 0),
            reminder_minutes=15,
            timezone="UTC",
        )
        edited = (
            "title: Test\n"
            "start_time: 2026-04-20 10:00\n"
            "end_time: -\n"
            "location: -\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(event)
            assert result.reminder_minutes is None

    def test_edit_multiple_fields(self):
        edited = (
            "title: Updated Title\n"
            "start_time: 2026-04-20 10:00\n"
            "end_time: 2026-04-20 11:00\n"
            "location: New Room\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.title == "Updated Title"
            assert result.location == "New Room"

    def test_editor_error_returns_original(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=1)):
            result = edit_event(self._event())
            assert result.title == "Original"

    def test_edit_attendees(self):
        edited = (
            "title: Original\n"
            "start_time: 2026-04-20 10:00\n"
            "end_time: 2026-04-20 11:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: alice@test.com, bob@test.com\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.attendees == ["alice@test.com", "bob@test.com"]

    def test_comments_ignored(self):
        edited = (
            "# This is a comment\n"
            "title: Original\n"
            "start_time: 2026-04-20 10:00\n"
            "# Another comment\n"
            "end_time: 2026-04-20 11:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.title == "Original"

    def test_invalid_date_keeps_original(self):
        edited = (
            "title: Original\n"
            "start_time: not-a-date\n"
            "end_time: 2026-04-20 11:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.start_time == datetime(2026, 4, 20, 10, 0)

    def test_invalid_reminder_keeps_original(self):
        edited = (
            "title: Original\n"
            "start_time: 2026-04-20 10:00\n"
            "end_time: 2026-04-20 11:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: abc\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.reminder_minutes is None

    def test_invalid_email_keeps_original(self):
        edited = (
            "title: Original\n"
            "start_time: 2026-04-20 10:00\n"
            "end_time: 2026-04-20 11:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: not-an-email\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.attendees == []

    def test_end_before_start_keeps_original(self):
        edited = (
            "title: Original\n"
            "start_time: 2026-04-20 15:00\n"
            "end_time: 2026-04-20 10:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.start_time == datetime(2026, 4, 20, 10, 0)

    def test_empty_title_keeps_original(self):
        edited = (
            "title: -\n"
            "start_time: 2026-04-20 10:00\n"
            "end_time: 2026-04-20 11:00\n"
            "location: Room A\n"
            "description: -\n"
            "reminder_minutes: -\n"
            "recurrence: -\n"
            "timezone: UTC\n"
            "attendees: -\n"
        )
        with patch("subprocess.run", side_effect=self._mock_editor(edited)):
            result = edit_event(self._event())
            assert result.title == "Original"


# ── read_stdin tests ─────────────────────────────────────────────────

class TestReadStdin:
    def test_returns_none_when_tty(self):
        with patch("src.main.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert read_stdin() is None

    def test_reads_piped_input(self):
        with patch("src.main.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = "  piped text  \n"
            assert read_stdin() == "piped text"

    def test_empty_pipe_returns_none(self):
        with patch("src.main.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = "   "
            assert read_stdin() is None


# ── setup command tests ──────────────────────────────────────────────

class TestSetupCommand:
    def test_setup_openai_basic(self):
        with (
            patch("src.main.load_config", return_value={
                "llm": {"provider": "openai", "model": "openai/gpt-4o"},
                "output": {"default": "ics"},
                "google": {"calendar_id": "primary"},
            }),
            patch("src.main.Prompt.ask", side_effect=[
                "openai",          # provider
                "sk-test-key",     # api key
                "ics",             # output method
            ]),
            patch("src.main.get_api_key", return_value=None),
            patch("src.main.set_api_key") as mock_set_key,
            patch("src.main.save_config") as mock_save,
        ):
            result = runner.invoke(app, ["setup"])
            assert result.exit_code == 0
            mock_set_key.assert_called_once_with("openai", "sk-test-key")
            mock_save.assert_called_once()

    def test_setup_ollama_no_key(self):
        with (
            patch("src.main.load_config", return_value={
                "llm": {"provider": "openai", "model": "openai/gpt-4o"},
                "output": {"default": "ics"},
                "google": {"calendar_id": "primary"},
            }),
            patch("src.main.Prompt.ask", side_effect=[
                "ollama",                       # provider
                "http://localhost:11434",       # api base
                "ics",                          # output method
            ]),
            patch("src.main.save_config") as mock_save,
        ):
            result = runner.invoke(app, ["setup"])
            assert result.exit_code == 0
            saved = mock_save.call_args[0][0]
            assert saved["llm"]["provider"] == "ollama"
            assert saved["llm"]["api_base"] == "http://localhost:11434"

    def test_setup_existing_key_keep(self):
        with (
            patch("src.main.load_config", return_value={
                "llm": {"provider": "openai", "model": "openai/gpt-4o"},
                "output": {"default": "ics"},
                "google": {"calendar_id": "primary"},
            }),
            patch("src.main.Prompt.ask", side_effect=[
                "openai",          # provider
                "ics",             # output method
            ]),
            patch("src.main.get_api_key", return_value="sk-existing"),
            patch("src.main.typer.confirm", return_value=False),  # don't update
            patch("src.main.set_api_key") as mock_set_key,
            patch("src.main.save_config"),
        ):
            result = runner.invoke(app, ["setup"])
            assert result.exit_code == 0
            mock_set_key.assert_not_called()

    def test_setup_google_output(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        # No credentials file exists
        with (
            patch("src.main.load_config", return_value={
                "llm": {"provider": "openai", "model": "openai/gpt-4o"},
                "output": {"default": "ics"},
                "google": {"calendar_id": "primary"},
            }),
            patch("src.main.Prompt.ask", side_effect=[
                "openai",          # provider
                "sk-key",          # api key
                "google",          # output method
                "primary",         # calendar id
            ]),
            patch("src.main.get_api_key", return_value=None),
            patch("src.main.set_api_key"),
            patch("src.main.save_config") as mock_save,
            patch("src.config.get_google_credentials_path", return_value=creds_file),
        ):
            result = runner.invoke(app, ["setup"])
            assert result.exit_code == 0


# ── Additional CLI edge case tests ───────────────────────────────────

class TestAddCommandEdgeCases:
    def test_add_with_provider_and_model(self):
        event = CalendarEvent(
            title="Custom LLM",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )
        with (
            patch("src.main._resolve_input", return_value="test"),
            patch("src.main._parse_with_retry", return_value=event) as mock_parse,
        ):
            result = runner.invoke(app, [
                "add", "test", "--json",
                "-p", "anthropic",
                "-m", "anthropic/claude-sonnet-4-20250514",
            ])
            assert result.exit_code == 0
            mock_parse.assert_called_once_with(
                "test", provider="anthropic", model="anthropic/claude-sonnet-4-20250514"
            )

    def test_add_google_output(self):
        event = CalendarEvent(
            title="Google Event",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )
        mock_service = MagicMock()
        mock_result = {"id": "evt1", "htmlLink": "https://example.com"}
        with (
            patch("src.main._resolve_input", return_value="test"),
            patch("src.main._parse_with_retry", return_value=event),
            patch("src.main.load_config", return_value={"output": {"default": "google"}}),
            patch("src.connections.google_calendar.authenticate", return_value=mock_service),
            patch("src.connections.google_calendar.create_event", return_value=mock_result),
        ):
            result = runner.invoke(app, ["add", "test", "-y", "-o", "google"])
            assert result.exit_code == 0
            assert "Event created" in result.output

    def test_parse_with_language(self):
        event = CalendarEvent(
            title="OCR Event",
            start_time=datetime(2026, 4, 20, 10, 0),
            timezone="UTC",
        )
        with (
            patch("src.main._resolve_input", return_value="test") as mock_resolve,
            patch("src.main._parse_with_retry", return_value=event),
        ):
            result = runner.invoke(app, ["parse", "test", "-l", "chi_sim", "--json"])
            assert result.exit_code == 0
            mock_resolve.assert_called_once_with("test", "chi_sim")


class TestConfigCommandDetails:
    def test_config_shows_api_key_status_not_set(self):
        with (
            patch("src.main.load_config", return_value={
                "llm": {"provider": "anthropic", "model": "anthropic/claude-sonnet-4-20250514"},
                "output": {"default": "ics"},
                "google": {"calendar_id": "primary"},
            }),
            patch("src.main.get_api_key", return_value=None),
        ):
            result = runner.invoke(app, ["config"])
            assert result.exit_code == 0
            assert "not set" in result.output

    def test_config_shows_platform(self):
        with (
            patch("src.main.load_config", return_value={
                "llm": {"provider": "openai", "model": "openai/gpt-4o"},
                "output": {"default": "ics"},
                "google": {"calendar_id": "primary"},
            }),
            patch("src.main.get_api_key", return_value="sk-test"),
        ):
            result = runner.invoke(app, ["config"])
            assert "Platform" in result.output
