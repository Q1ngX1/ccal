import json as json_lib
import os
import re
import subprocess
import tempfile
from datetime import datetime
from typing import Callable

import typer
from rich import print
from rich.prompt import Prompt
from rich.table import Table

from src.config import load_config
from src.connections.ics import export_to_ics
from src.models.model import CalendarEvent, EventLike, ParsedCalendarEvent


class IncompleteEventError(Exception):
    """Raised when an event cannot be output yet because it is still incomplete."""


def as_list(events: EventLike | list[EventLike]) -> list[EventLike]:
    return events if isinstance(events, list) else [events]


def display_event(event: EventLike, as_json: bool = False) -> None:
    """Display a parsed CalendarEvent."""
    if as_json:
        data = event.model_dump(mode="json")
        data["timezone"] = event.get_timezone()
        print(json_lib.dumps(data, indent=2, ensure_ascii=False))
        return

    table = Table(title="Parsed Event", show_header=False, border_style="cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Title", event.title)
    table.add_row("All Day", "Yes" if event.all_day else "No")
    if event.start_time is None:
        table.add_row("Start", "[yellow]Missing[/yellow]")
        table.add_row("End", event.end_time.strftime("%Y-%m-%d %H:%M") if event.end_time else "-")
    elif event.all_day:
        table.add_row("Start", event.start_time.strftime("%Y-%m-%d"))
        table.add_row("End", event.end_time.strftime("%Y-%m-%d") if event.end_time else "-")
    else:
        table.add_row("Start", event.start_time.strftime("%Y-%m-%d %H:%M"))
        table.add_row("End", event.end_time.strftime("%Y-%m-%d %H:%M") if event.end_time else "-")
    table.add_row("Location", event.location or "-")
    table.add_row("Description", event.description or "-")
    table.add_row("Reminder", f"{event.reminder_minutes} min" if event.reminder_minutes else "-")
    table.add_row("Recurrence", event.recurrence or "-")
    table.add_row("Timezone", event.get_timezone())
    table.add_row("Attendees", ", ".join(event.attendees) if event.attendees else "-")

    print(table)


def display_events(events: EventLike | list[EventLike], as_json: bool = False) -> None:
    """Display one or more parsed events."""
    event_list = as_list(events)
    if as_json:
        data = []
        for event in event_list:
            item = event.model_dump(mode="json")
            item["timezone"] = event.get_timezone()
            data.append(item)
        print(json_lib.dumps(data[0] if len(data) == 1 else data, indent=2, ensure_ascii=False))
        return

    if len(event_list) == 1:
        display_event(event_list[0])
        return

    for index, event in enumerate(event_list, 1):
        print(f"\n[bold cyan]Event {index}/{len(event_list)}[/bold cyan]")
        display_event(event)


def require_complete_event(event: EventLike) -> CalendarEvent:
    if isinstance(event, CalendarEvent):
        return event
    return event.to_calendar_event()


def output_event(
    event: EventLike,
    output: str | None,
    *,
    load_config_fn: Callable[[], dict] = load_config,
) -> None:
    """Output event to the chosen destination."""
    try:
        event = require_complete_event(event)
    except ValueError:
        print(f"[red]Event '{event.title}' is missing start_time. Edit it or remove it before output.[/red]")
        raise IncompleteEventError(event.title)

    config = load_config_fn()
    output_method = output or config["output"]["default"]

    if output_method == "google":
        from src.connections.google_calendar import authenticate, create_event

        print("[cyan]Syncing to Google Calendar...[/cyan]")
        try:
            service = authenticate(config)
            result = create_event(service, event)
        except (FileNotFoundError, Exception) as e:
            print(f"[red]Google Calendar error:[/red] {e}")
            raise typer.Exit(1)
        print(f"[green]Event created![/green] Link: {result.get('htmlLink', 'N/A')}")
    elif output_method == "apple":
        from src.connections.apple_calendar import create_event as apple_create, is_macos

        if not is_macos():
            print("[red]Apple Calendar is only available on macOS.[/red]")
            print("[yellow]Falling back to ICS export...[/yellow]")
            path = export_to_ics(event)
            print(f"[green]ICS file saved:[/green] {path}")
        else:
            print("[cyan]Adding to Apple Calendar...[/cyan]")
            apple_create(event, calendar_name=config.get("apple", {}).get("calendar_name", "Home"))
            print("[green]Event added to Apple Calendar![/green]")
    else:
        path = export_to_ics(event)
        print(f"[green]ICS file saved:[/green] {path}")


def output_events(
    events: EventLike | list[EventLike],
    output: str | None,
    *,
    load_config_fn: Callable[[], dict] = load_config,
    output_event_fn: Callable[[EventLike, str | None], None] | None = None,
) -> bool:
    """Output all selected events. Returns False if any event is still incomplete."""
    event_list = as_list(events)
    output_event_fn = output_event_fn or (lambda event, out: output_event(event, out, load_config_fn=load_config_fn))

    for event in event_list:
        try:
            require_complete_event(event)
        except ValueError:
            print(f"[red]Event '{event.title}' is missing start_time. Edit it or remove it before output.[/red]")
            return False

    for event in event_list:
        output_event_fn(event, output)

    return True


def confirm_and_output(
    event: EventLike | list[EventLike],
    output: str | None,
    yes: bool = False,
    *,
    display_event_fn: Callable[[EventLike, bool], None] = display_event,
    display_events_fn: Callable[[EventLike | list[EventLike], bool], None] = display_events,
    output_event_fn: Callable[[EventLike, str | None], None] | None = None,
    edit_event_fn: Callable[[EventLike], EventLike] | None = None,
    output_events_fn: Callable[[EventLike | list[EventLike], str | None], bool] | None = None,
) -> None:
    """Show event(s), ask for confirmation, then output."""
    events = as_list(event)
    if len(events) > 1:
        confirm_and_output_many(
            events,
            output,
            yes=yes,
            display_events_fn=display_events_fn,
            output_events_fn=output_events_fn,
            edit_event_fn=edit_event_fn,
        )
        return

    event = events[0]
    display_event_fn(event)

    if yes:
        output_event_fn = output_event_fn or output_event
        output_event_fn(event, output)
        return

    choice = Prompt.ask(
        "\nConfirm? [Y]es / [N]o / [E]dit field",
        choices=["y", "n", "e"],
        default="y",
    )
    if choice == "n":
        print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    if choice == "e":
        edit_event_fn = edit_event_fn or edit_event
        while True:
            event = edit_event_fn(event)
            display_event_fn(event)
            next_choice = Prompt.ask(
                "\nConfirm? [Y]es / [N]o / [E]dit again",
                choices=["y", "n", "e"],
                default="y",
            )
            if next_choice == "y":
                break
            if next_choice == "n":
                print("[yellow]Cancelled.[/yellow]")
                raise typer.Exit()

    while True:
        try:
            output_event_fn = output_event_fn or output_event
            output_event_fn(event, output)
            return
        except IncompleteEventError:
            print("[yellow]Please edit the event before outputting it.[/yellow]")
            edit_event_fn = edit_event_fn or edit_event
            event = edit_event_fn(event)
            display_event_fn(event)


def confirm_and_output_many(
    events: list[EventLike],
    output: str | None,
    yes: bool = False,
    *,
    display_events_fn: Callable[[EventLike | list[EventLike], bool], None] = display_events,
    output_events_fn: Callable[[EventLike | list[EventLike], str | None], bool] | None = None,
    edit_event_fn: Callable[[EventLike], EventLike] | None = None,
) -> None:
    """Confirm, edit, remove, and output multiple parsed events."""
    display_events_fn(events)
    output_events_fn = output_events_fn or output_events
    edit_event_fn = edit_event_fn or edit_event

    while True:
        if yes:
            if output_events_fn(events, output):
                return
            raise typer.Exit(1)

        choice = Prompt.ask(
            "\nConfirm all? [Y]es all / [N]o / [E]dit event / [R]emove event",
            choices=["y", "n", "e", "r"],
            default="y",
        ).lower()

        if choice == "y":
            if output_events_fn(events, output):
                return
            display_events_fn(events)
            continue
        if choice == "n":
            print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()
        if choice == "e":
            index = ask_event_index(events, "Event number to edit")
            events[index] = edit_event_fn(events[index])
            display_events_fn(events)
        if choice == "r":
            index = ask_event_index(events, "Event number to remove")
            removed = events.pop(index)
            print(f"[yellow]Removed:[/yellow] {removed.title}")
            if not events:
                print("[yellow]No events left. Cancelled.[/yellow]")
                raise typer.Exit()
            display_events_fn(events)


def ask_event_index(events: list[EventLike], prompt: str) -> int:
    while True:
        raw = Prompt.ask(prompt, default="1")
        if raw.isdigit() and 1 <= int(raw) <= len(events):
            return int(raw) - 1
        print(f"[red]Enter a number from 1 to {len(events)}.[/red]")


def edit_event(event: EventLike) -> EventLike:
    """Open event fields in the user's editor for direct editing."""
    data = event.model_dump(mode="json")
    tz = event.get_timezone()

    lines = [
        "# Edit event fields below. Lines starting with # are ignored.",
        "# Leave a value empty (or as -) to clear it.",
        "# Save and close the editor to apply changes.",
        "#",
        "# Vim: press i to edit, then Esc followed by :wq to save and quit.",
        "# Nano: edit directly, then Ctrl+O to save and Ctrl+X to exit.",
        "",
        f"title: {data['title']}",
        f"all_day: {'yes' if event.all_day else 'no'}",
        f"start_time: {format_datetime_for_edit(event.start_time, event.all_day)}",
        f"end_time: {event.end_time.strftime('%Y-%m-%d') if event.all_day and event.end_time else (event.end_time.strftime('%Y-%m-%d %H:%M') if event.end_time else '-')}",
        f"location: {data['location'] or '-'}",
        f"description: {data['description'] or '-'}",
        f"reminder_minutes: {data['reminder_minutes'] if data['reminder_minutes'] is not None else '-'}",
        f"recurrence: {data['recurrence'] or '-'}",
        f"timezone: {tz}",
        f"attendees: {', '.join(data['attendees']) if data['attendees'] else '-'}",
    ]
    text = "\n".join(lines) + "\n"

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR", "vi")

    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write(text)
        tmp_path = f.name

    try:
        result = subprocess.run([editor, tmp_path])
        if result.returncode != 0:
            print("[red]Editor exited with an error. Keeping original event.[/red]")
            return event

        with open(tmp_path) as f:
            edited = f.read()
    finally:
        os.unlink(tmp_path)

    updates: dict = {}
    errors: list[str] = []
    for line in edited.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ": " not in line:
            continue
        key, _, value = line.partition(": ")
        key = key.strip()
        value = value.strip()

        if value in ("-", ""):
            value = None

        if key == "title":
            if not value:
                errors.append("title: cannot be empty")
            else:
                updates["title"] = value
        elif key == "all_day":
            if value and value.lower() in ("yes", "true", "1"):
                updates["all_day"] = True
            else:
                updates["all_day"] = False
        elif key == "start_time":
            if not value:
                errors.append("start_time: cannot be empty")
            else:
                parsed_dt = parse_datetime_field(value)
                if parsed_dt is None:
                    errors.append(f"start_time: invalid format '{value}' (use YYYY-MM-DD HH:MM)")
                else:
                    updates["start_time"] = parsed_dt
        elif key == "end_time":
            if value:
                parsed_dt = parse_datetime_field(value)
                if parsed_dt is None:
                    errors.append(f"end_time: invalid format '{value}' (use YYYY-MM-DD HH:MM)")
                else:
                    updates["end_time"] = parsed_dt
            else:
                updates["end_time"] = None
        elif key == "location":
            updates["location"] = value
        elif key == "description":
            updates["description"] = value
        elif key == "reminder_minutes":
            if value:
                if not re.fullmatch(r"\d+", value):
                    errors.append(f"reminder_minutes: '{value}' is not a valid integer")
                else:
                    updates["reminder_minutes"] = int(value)
            else:
                updates["reminder_minutes"] = None
        elif key == "recurrence":
            updates["recurrence"] = value
        elif key == "timezone":
            if value and not re.fullmatch(r"[A-Za-z_]+(/[A-Za-z_/]+)?", value):
                errors.append(f"timezone: '{value}' doesn't look like a valid IANA timezone (e.g. Asia/Shanghai)")
            else:
                updates["timezone"] = value
        elif key == "attendees":
            if value:
                emails = [a.strip() for a in value.split(",") if a.strip()]
                bad = [e for e in emails if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e)]
                if bad:
                    errors.append(f"attendees: invalid email(s): {', '.join(bad)}")
                else:
                    updates["attendees"] = emails
            else:
                updates["attendees"] = []

    if errors:
        print("[red]Validation errors:[/red]")
        for err in errors:
            print(f"  [red]• {err}[/red]")
        print("[yellow]Keeping original event. Please try editing again.[/yellow]")
        return event

    st = updates.get("start_time", event.start_time)
    et = updates.get("end_time", event.end_time)
    if st and et and et <= st:
        print("[red]Validation error: end_time must be after start_time.[/red]")
        print("[yellow]Keeping original event. Please try editing again.[/yellow]")
        return event

    merged = event.model_dump()
    merged.update(updates)
    if merged.get("start_time"):
        return CalendarEvent(**merged)
    return ParsedCalendarEvent(**merged)


def format_datetime_for_edit(value: datetime | None, all_day: bool) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d") if all_day else value.strftime("%Y-%m-%d %H:%M")


def parse_datetime_field(value: str) -> datetime | None:
    """Parse a datetime string in common formats, returning None on failure."""
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
