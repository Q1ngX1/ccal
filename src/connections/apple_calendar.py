import platform
import subprocess
from datetime import datetime, timedelta

from src.models.model import CalendarEvent


def is_macos() -> bool:
    return platform.system() == "Darwin"


def create_event(event: CalendarEvent, calendar_name: str = "Home") -> None:
    """Create an event in Apple Calendar via AppleScript. macOS only."""
    if not is_macos():
        raise RuntimeError(
            "Apple Calendar integration is only available on macOS. "
            "Use 'ics' output instead (the .ics file can be opened by any calendar app)."
        )

    start = _format_applescript_date(event.start_time)

    if event.end_time:
        end = _format_applescript_date(event.end_time)
    else:
        end = _format_applescript_date(event.start_time + timedelta(hours=1))

    props = f'summary:"{_escape(event.title)}", start date:{start}, end date:{end}'
    if event.location:
        props += f', location:"{_escape(event.location)}"'
    if event.description:
        props += f', description:"{_escape(event.description)}"'

    script = f'''
    tell application "Calendar"
        tell calendar "{_escape(calendar_name)}"
            make new event at end with properties {{{props}}}
        end tell
        reload calendars
    end tell
    '''

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=15,
    )

    if result.returncode != 0:
        error = result.stderr.strip()
        if "Calendar" in error and "doesn't understand" in error:
            raise RuntimeError("Apple Calendar app is not available or not responding.")
        raise RuntimeError(f"AppleScript error: {error}")


def list_calendars() -> list[str]:
    """List available Apple Calendar names. macOS only."""
    if not is_macos():
        raise RuntimeError("Apple Calendar is only available on macOS.")

    script = '''
    tell application "Calendar"
        set calNames to {}
        repeat with c in calendars
            set end of calNames to name of c
        end repeat
        return calNames
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to list calendars: {result.stderr.strip()}")

    raw = result.stdout.strip()
    if not raw:
        return []
    return [name.strip() for name in raw.split(",")]


def _format_applescript_date(dt: datetime) -> str:
    """Format a datetime for AppleScript: date "April 16, 2026 3:00:00 PM"."""
    return f'date "{dt.strftime("%B %d, %Y %I:%M:%S %p")}"'


def _escape(s: str) -> str:
    """Escape a string for use inside AppleScript double quotes."""
    return s.replace("\\", "\\\\").replace('"', '\\"')
