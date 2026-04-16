"""Tests for src/connections/google_calendar.py — Google Calendar integration."""
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from src.connections.google_calendar import authenticate, create_event, list_calendars


class TestAuthenticate:
    def test_existing_valid_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        token_file.write_text('{"token": "test"}')

        mock_creds = MagicMock()
        mock_creds.valid = True

        with (
            patch("src.connections.google_calendar.get_google_token_path", return_value=token_file),
            patch("src.connections.google_calendar.Credentials.from_authorized_user_file", return_value=mock_creds),
            patch("src.connections.google_calendar.build") as mock_build,
        ):
            service = authenticate()
            mock_build.assert_called_once_with("calendar", "v3", credentials=mock_creds)

    def test_expired_token_refreshes(self, tmp_path):
        token_file = tmp_path / "token.json"
        token_file.write_text('{"token": "expired"}')

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh-tok"
        mock_creds.to_json.return_value = '{"token": "refreshed"}'

        with (
            patch("src.connections.google_calendar.get_google_token_path", return_value=token_file),
            patch("src.connections.google_calendar.Credentials.from_authorized_user_file", return_value=mock_creds),
            patch("src.connections.google_calendar.Request"),
            patch("src.connections.google_calendar.build") as mock_build,
        ):
            authenticate()
            mock_creds.refresh.assert_called_once()

    def test_no_credentials_file_raises(self, tmp_path):
        token_file = tmp_path / "token.json"
        creds_file = tmp_path / "credentials.json"

        with (
            patch("src.connections.google_calendar.get_google_token_path", return_value=token_file),
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file),
        ):
            with pytest.raises(FileNotFoundError, match="Google OAuth credentials not found"):
                authenticate()

    def test_fresh_oauth_flow(self, tmp_path):
        """No token file, credentials exist → run OAuth flow."""
        token_file = tmp_path / "token.json"
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text('{"installed": {}}')

        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "new"}'
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds

        with (
            patch("src.connections.google_calendar.get_google_token_path", return_value=token_file),
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file),
            patch("src.connections.google_calendar.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow),
            patch("src.connections.google_calendar.build") as mock_build,
        ):
            authenticate()
            mock_flow.run_local_server.assert_called_once_with(port=0)
            assert token_file.exists()


class TestCreateEvent:
    def test_creates_event_with_default_calendar(self, sample_event):
        mock_service = MagicMock()
        mock_insert = mock_service.events.return_value.insert.return_value
        mock_insert.execute.return_value = {"id": "evt123", "htmlLink": "https://example.com"}

        with patch("src.connections.google_calendar.load_config", return_value={
            "google": {"calendar_id": "primary"}
        }):
            result = create_event(mock_service, sample_event)

        assert result["id"] == "evt123"
        mock_service.events.return_value.insert.assert_called_once()
        call_kwargs = mock_service.events.return_value.insert.call_args[1]
        assert call_kwargs["calendarId"] == "primary"

    def test_creates_event_with_custom_calendar(self, sample_event):
        mock_service = MagicMock()
        mock_insert = mock_service.events.return_value.insert.return_value
        mock_insert.execute.return_value = {"id": "evt456"}

        result = create_event(mock_service, sample_event, calendar_id="work@group.calendar.google.com")
        call_kwargs = mock_service.events.return_value.insert.call_args[1]
        assert call_kwargs["calendarId"] == "work@group.calendar.google.com"


class TestListCalendars:
    def test_list_calendars(self):
        mock_service = MagicMock()
        mock_service.calendarList.return_value.list.return_value.execute.return_value = {
            "items": [
                {"id": "primary", "summary": "Main"},
                {"id": "work@group.calendar.google.com", "summary": "Work"},
            ]
        }

        result = list_calendars(mock_service)
        assert len(result) == 2
        assert result[0]["summary"] == "Main"

    def test_list_calendars_empty(self):
        mock_service = MagicMock()
        mock_service.calendarList.return_value.list.return_value.execute.return_value = {}

        result = list_calendars(mock_service)
        assert result == []
