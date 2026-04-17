import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config import get_google_credentials_path, get_google_token_path, load_config
from src.models.model import CalendarEvent

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def authenticate(config: dict | None = None):
    """Authenticate with Google Calendar API and return the service object."""
    if config is None:
        config = load_config()
    token_path = get_google_token_path(config)
    creds_path = get_google_credentials_path(config)
    auth_mode = config.get("google", {}).get("auth_mode", "desktop")

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"Google OAuth credentials not found at {creds_path}. "
                    "Download your OAuth client credentials JSON from Google Cloud Console "
                    "and save it there, then run 'ccal setup' again."
                )
            client_config = _load_client_config(creds_path)
            if auth_mode == "device":
                creds = _run_device_flow(client_config)
            else:
                if _should_use_device_flow():
                    raise RuntimeError(
                        "This machine has no browser available for Google desktop OAuth. "
                        "Either run setup on a machine with a browser, or create a "
                        "'TVs and Limited Input devices' OAuth client and use device mode."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                try:
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    if _looks_like_browser_error(e):
                        raise RuntimeError(
                            "No runnable browser detected for Google desktop OAuth. "
                            "Use a machine with a browser, or switch to device mode with a "
                            "'TVs and Limited Input devices' OAuth client."
                        ) from e
                    else:
                        raise

        token_path.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def create_event(service, event: CalendarEvent, calendar_id: str | None = None) -> dict:
    """Create an event on Google Calendar. Returns the created event."""
    if calendar_id is None:
        config = load_config()
        calendar_id = config["google"]["calendar_id"]

    google_event = event.to_google_event()
    result = service.events().insert(calendarId=calendar_id, body=google_event).execute()
    return result


def list_calendars(service) -> list[dict]:
    """List all calendars accessible by the authenticated user."""
    result = service.calendarList().list().execute()
    return result.get("items", [])


def _load_client_config(creds_path) -> dict:
    """Load the OAuth client configuration from the downloaded JSON file."""
    with open(creds_path) as f:
        data = json.load(f)
    if "installed" in data:
        return data["installed"]
    if "web" in data:
        return data["web"]
    raise ValueError("Google credentials JSON must contain an 'installed' or 'web' client configuration.")


def _should_use_device_flow() -> bool:
    """Prefer device flow on headless Linux environments."""
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _looks_like_browser_error(error: Exception) -> bool:
    """Detect browser-launch errors from the OAuth helper."""
    message = str(error).lower()
    return "browser" in message or "xdg-open" in message or "open a web browser" in message


def _extract_error_name(exc: urllib.error.HTTPError) -> str | None:
    """Best-effort extraction of Google OAuth error names from an HTTPError body."""
    try:
        body = exc.read().decode()
        if not body:
            return None
        payload = json.loads(body)
        if isinstance(payload, dict):
            return payload.get("error")
    except Exception:
        return None
    return None


def _run_device_flow(client_config: dict) -> Credentials:
    """Authenticate using Google's device authorization flow."""
    client_id = client_config.get("client_id")
    client_secret = client_config.get("client_secret")
    token_uri = client_config.get("token_uri", "https://oauth2.googleapis.com/token")

    if not client_id:
        raise ValueError("Google credentials JSON does not include a client_id.")

    request_data = urllib.parse.urlencode({
        "client_id": client_id,
        "scope": " ".join(SCOPES),
    }).encode()
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/device/code",
        data=request_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(request) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        error_name = _extract_error_name(exc)
        if exc.code == 401:
            raise RuntimeError(
                "Google rejected the device authorization request. "
                "This usually means the JSON came from a Desktop app OAuth client, "
                "but device mode requires a 'TVs and Limited Input devices' OAuth client."
            ) from exc
        if exc.code == 403 and error_name == "org_internal":
            raise RuntimeError(
                "Google blocked this OAuth client because the project is restricted to an organization. "
                "Set the OAuth consent screen user type to External, or sign in with an account in that organization."
            ) from exc
        raise

    device_code = payload["device_code"]
    user_code = payload["user_code"]
    verification_url = payload.get("verification_url") or payload.get("verification_uri")
    interval = int(payload.get("interval", 5))
    expires_in = int(payload.get("expires_in", 1800))

    print("\n[yellow]Headless login mode:[/yellow]")
    print(f"  Visit: {verification_url}")
    print(f"  Code:  {user_code}")

    deadline = time.time() + expires_in
    poll_data = {
        "client_id": client_id,
        "client_secret": client_secret or "",
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }

    while time.time() < deadline:
        time.sleep(interval)
        token_request = urllib.request.Request(
            token_uri,
            data=urllib.parse.urlencode(poll_data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(token_request) as response:
                token_payload = json.load(response)
            access_token = token_payload["access_token"]
            refresh_token = token_payload.get("refresh_token")
            token = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri=token_uri,
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES,
            )
            return token
        except urllib.error.HTTPError as exc:
            error_name = _extract_error_name(exc)

            if error_name in {"authorization_pending", "slow_down"}:
                if error_name == "slow_down":
                    interval += 5
                continue
            if error_name == "access_denied":
                raise RuntimeError(
                    "Google blocked the authorization request. "
                    "If the OAuth consent screen is in Testing, add this Google account to the Test users list. "
                    "If the project is Internal, switch it to External or use an account inside the organization."
                ) from exc
            if error_name == "expired_token":
                raise RuntimeError("Google device authorization expired. Please run setup again.")
            raise RuntimeError(f"Google device authorization failed: {error_name or exc}")

    raise RuntimeError("Google device authorization timed out. Please run setup again.")
