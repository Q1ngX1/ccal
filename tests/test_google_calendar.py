"""Tests for src/connections/google_calendar.py — Google Calendar integration."""
import json
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from src.connections.google_calendar import authenticate, create_event, list_calendars


def _mock_urlopen(payload: dict):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


class TestAuthenticate:
    def test_uses_configured_credentials_dir(self, tmp_path):
        creds_dir = tmp_path / "google-creds"
        token_file = creds_dir / "google_token.json"
        creds_file = creds_dir / "google_credentials.json"
        token_file.parent.mkdir(parents=True)
        token_file.write_text('{"token": "ok"}')
        creds_file.write_text('{"installed": {}}')

        mock_creds = MagicMock()
        mock_creds.valid = True

        with (
            patch("src.connections.google_calendar.get_google_token_path", return_value=token_file) as mock_token,
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file) as mock_creds_path,
            patch("src.connections.google_calendar.Credentials.from_authorized_user_file", return_value=mock_creds),
            patch("src.connections.google_calendar.build") as mock_build,
        ):
            authenticate({"google": {"credentials_path": str(creds_file)}})

        mock_token.assert_called_once()
        mock_creds_path.assert_called_once()
        mock_build.assert_called_once_with("calendar", "v3", credentials=mock_creds)

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
            patch("src.connections.google_calendar._should_use_device_flow", return_value=False),
            patch("src.connections.google_calendar._looks_like_browser_error", return_value=False),
            patch("src.connections.google_calendar.get_google_token_path", return_value=token_file),
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file),
            patch("src.connections.google_calendar.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow),
            patch("src.connections.google_calendar.build") as mock_build,
        ):
            authenticate({"google": {"auth_mode": "desktop", "credentials_path": str(creds_file)}})
            mock_flow.run_local_server.assert_called_once_with(port=0)
            assert token_file.exists()

    def test_headless_device_flow(self, tmp_path):
        token_file = tmp_path / "token.json"
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({
            "installed": {
                "client_id": "client-id",
                "client_secret": "client-secret",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }))

        device_payload = {
            "device_code": "device-code",
            "user_code": "ABCD-EFGH",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 1,
        }
        token_payload = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        }

        with (
            patch("src.connections.google_calendar.get_google_token_path", return_value=token_file),
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file),
            patch("src.connections.google_calendar.urllib.request.urlopen", side_effect=[
                _mock_urlopen(device_payload),
                _mock_urlopen(token_payload),
            ]),
            patch("src.connections.google_calendar.time.sleep"),
            patch("src.connections.google_calendar.build") as mock_build,
        ):
            authenticate({"google": {"auth_mode": "device", "credentials_path": str(creds_file)}})

        assert token_file.exists()
        assert "access-token" in token_file.read_text()
        mock_build.assert_called_once()

    def test_device_flow_unauthorized_is_clear(self, tmp_path):
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"installed": {"client_id": "client-id"}}))

        with (
            patch("src.connections.google_calendar._should_use_device_flow", return_value=True),
            patch("src.connections.google_calendar.get_google_token_path", return_value=tmp_path / "token.json"),
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file),
            patch("src.connections.google_calendar.urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                url="https://oauth2.googleapis.com/device/code",
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=None,
            )),
        ):
            with pytest.raises(RuntimeError, match="TVs and Limited Input devices"):
                authenticate({"google": {"auth_mode": "device", "credentials_path": str(creds_file)}})

    def test_device_flow_desktop_client_is_clear(self, tmp_path):
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"installed": {"client_id": "client-id", "client_secret": "client-secret"}}))

        with (
            patch("src.connections.google_calendar._should_use_device_flow", return_value=False),
            patch("src.connections.google_calendar.get_google_token_path", return_value=tmp_path / "token.json"),
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file),
            patch("src.connections.google_calendar.urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                url="https://oauth2.googleapis.com/device/code",
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=None,
            )),
        ):
            with pytest.raises(RuntimeError, match="Desktop app OAuth client"):
                authenticate({"google": {"auth_mode": "device", "credentials_path": str(creds_file)}})

    def test_desktop_mode_headless_is_clear(self, tmp_path):
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text('{"installed": {"client_id": "client-id"}}')

        with (
            patch("src.connections.google_calendar._should_use_device_flow", return_value=True),
            patch("src.connections.google_calendar.get_google_token_path", return_value=tmp_path / "token.json"),
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file),
        ):
            with pytest.raises(RuntimeError, match="desktop OAuth"):
                authenticate({"google": {"auth_mode": "desktop", "credentials_path": str(creds_file)}})

    def test_poll_access_denied_mentions_test_users(self, tmp_path):
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"installed": {"client_id": "client-id", "client_secret": "client-secret"}}))

        access_denied = urllib.error.HTTPError(
            url="https://oauth2.googleapis.com/token",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=None,
        )
        access_denied.read = lambda: json.dumps({"error": "access_denied"}).encode()  # type: ignore[attr-defined]

        device_payload = {
            "device_code": "device-code",
            "user_code": "ABCD-EFGH",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 1,
        }

        with (
            patch("src.connections.google_calendar.get_google_token_path", return_value=tmp_path / "token.json"),
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file),
            patch("src.connections.google_calendar.urllib.request.urlopen", side_effect=[
                _mock_urlopen(device_payload),
                access_denied,
            ]),
            patch("src.connections.google_calendar.time.sleep"),
        ):
            with pytest.raises(RuntimeError, match="Test users"):
                authenticate({"google": {"auth_mode": "device", "credentials_path": str(creds_file)}})

    def test_org_internal_mentions_organization(self, tmp_path):
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"installed": {"client_id": "client-id", "client_secret": "client-secret"}}))

        org_internal = urllib.error.HTTPError(
            url="https://oauth2.googleapis.com/device/code",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=None,
        )
        org_internal.read = lambda: json.dumps({"error": "org_internal"}).encode()  # type: ignore[attr-defined]

        with (
            patch("src.connections.google_calendar.get_google_token_path", return_value=tmp_path / "token.json"),
            patch("src.connections.google_calendar.get_google_credentials_path", return_value=creds_file),
            patch("src.connections.google_calendar.urllib.request.urlopen", side_effect=org_internal),
        ):
            with pytest.raises(RuntimeError, match="organization"):
                authenticate({"google": {"auth_mode": "device", "credentials_path": str(creds_file)}})


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
