from datetime import datetime

from icalendar import Calendar, Event, vRecur
from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    title: str = Field(description="Event title")
    start_time: datetime = Field(description="Event start time")
    end_time: datetime | None = Field(default=None, description="Event end time")
    location: str | None = Field(default=None, description="Event location")
    description: str | None = Field(default=None, description="Event description")
    reminder_minutes: int | None = Field(default=None, description="Reminder in minutes before event")
    recurrence: str | None = Field(default=None, description="Recurrence rule in RRULE format")
    attendees: list[str] = Field(default_factory=list, description="List of attendee email addresses")
    timezone: str | None = Field(default=None, description="IANA timezone, e.g. Asia/Shanghai")

    def get_timezone(self) -> str:
        """Resolve timezone: explicit > geo-detected > UTC fallback."""
        if self.timezone:
            return self.timezone
        from src.input.geo import get_geo_info
        geo = get_geo_info()
        return geo.timezone or "UTC"

    def to_ical(self) -> Calendar:
        """Convert to an iCalendar Calendar object."""
        cal = Calendar()
        cal.add("prodid", "-//ccal//EN")
        cal.add("version", "2.0")

        event = Event()
        tz_name = self.get_timezone()
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            tz = None

        event.add("summary", self.title)
        if tz:
            event.add("dtstart", self.start_time.replace(tzinfo=tz))
        else:
            event.add("dtstart", self.start_time)
        if self.end_time:
            if tz:
                event.add("dtend", self.end_time.replace(tzinfo=tz))
            else:
                event.add("dtend", self.end_time)
        if self.location:
            event.add("location", self.location)
        if self.description:
            event.add("description", self.description)
        if self.recurrence:
            rrule_parts = {}
            for part in self.recurrence.split(";"):
                key, value = part.split("=", 1)
                rrule_parts[key.lower()] = value
            event.add("rrule", vRecur(rrule_parts))
        if self.reminder_minutes is not None:
            from icalendar import Alarm
            from datetime import timedelta

            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("trigger", timedelta(minutes=-self.reminder_minutes))
            alarm.add("description", f"Reminder: {self.title}")
            event.add_component(alarm)
        for attendee in self.attendees:
            event.add("attendee", f"mailto:{attendee}")

        cal.add_component(event)
        return cal

    def to_google_event(self) -> dict:
        """Convert to Google Calendar API event format."""
        tz_name = self.get_timezone()
        event: dict = {
            "summary": self.title,
            "start": {
                "dateTime": self.start_time.isoformat(),
                "timeZone": tz_name,
            },
        }
        if self.end_time:
            event["end"] = {
                "dateTime": self.end_time.isoformat(),
                "timeZone": tz_name,
            }
        else:
            from datetime import timedelta

            end = self.start_time + timedelta(hours=1)
            event["end"] = {
                "dateTime": end.isoformat(),
                "timeZone": tz_name,
            }
        if self.location:
            event["location"] = self.location
        if self.description:
            event["description"] = self.description
        if self.recurrence:
            event["recurrence"] = [f"RRULE:{self.recurrence}"]
        if self.reminder_minutes is not None:
            event["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": self.reminder_minutes}],
            }
        if self.attendees:
            event["attendees"] = [{"email": email} for email in self.attendees]
        return event