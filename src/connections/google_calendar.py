from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config import get_google_credentials_path, get_google_token_path, load_config
from src.models.model import CalendarEvent

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def authenticate():
    """Authenticate with Google Calendar API and return the service object."""
    token_path = get_google_token_path()
    creds_path = get_google_credentials_path()

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
                    "and save it there, then run 'ccal setup'."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

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
