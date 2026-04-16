from pathlib import Path

from src.models.model import CalendarEvent


def export_to_ics(event: CalendarEvent, output_path: str | None = None) -> str:
    """Export a CalendarEvent to an .ics file. Returns the output file path."""
    cal = event.to_ical()

    if output_path is None:
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in event.title)
        output_path = f"{safe_title.strip()}.ics"

    path = Path(output_path)
    path.write_bytes(cal.to_ical())
    return str(path.resolve())
