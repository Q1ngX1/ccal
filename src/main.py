import json as json_lib
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import Annotated, Optional

import typer
from rich import print
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.config import load_config, save_config, set_api_key, get_api_key
from src.connections.ics import export_to_ics
from src.input.ocr import is_image_file
from src.models.llm import parse_event
from src.models.model import CalendarEvent, ParsedCalendarEvent, EventLike


def version_callback(value: bool):
    if value:
        from importlib.metadata import version
        print(f"ccal {version('ccal')}")
        raise typer.Exit()




import click

class CcalTyper(typer.Typer):
    def __call__(self, *args, **kwargs):
        try:
            return super().__call__(*args, **kwargs)
        except click.exceptions.UsageError as e:
            if str(e).strip() == "Missing command.":
                print(Panel("[red]未指定命令。请输入 [bold]ccal --help[/bold] 查看可用命令。[/red]", title="错误", border_style="red"))
                raise typer.Exit(1)
            raise

app = CcalTyper(
    help="ccal - CLI tool for adding calendar events from text or images",
    callback=lambda version: None,
)


@app.callback()
def main_callback(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", help="Show version and exit.", callback=version_callback, is_eager=True),
    ] = None,
):
    pass


def _as_list(events: EventLike | list[EventLike]) -> list[EventLike]:
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
    event_list = _as_list(events)
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


def _require_complete_event(event: EventLike) -> CalendarEvent:
    if isinstance(event, CalendarEvent):
        return event
    return event.to_calendar_event()


def output_event(event: EventLike, output: str | None) -> None:
    """Output event to the chosen destination."""
    try:
        event = _require_complete_event(event)
    except ValueError:
        print(f"[red]Event '{event.title}' is missing start_time. Edit it or remove it before output.[/red]")
        raise typer.Exit(1)

    config = load_config()
    output_method = output or config["output"]["default"]

    if output_method == "google":
        from src.connections.google_calendar import authenticate, create_event

        print("[cyan]Syncing to Google Calendar...[/cyan]")
        try:
            service = authenticate()
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


def output_events(events: EventLike | list[EventLike], output: str | None) -> None:
    """Output all selected events."""
    event_list = _as_list(events)
    for event in event_list:
        try:
            _require_complete_event(event)
        except ValueError:
            print(f"[red]Event '{event.title}' is missing start_time. Edit it or remove it before output.[/red]")
            raise typer.Exit(1)

    for event in event_list:
        output_event(event, output)


def confirm_and_output(event: EventLike | list[EventLike], output: str | None, yes: bool = False) -> None:
    """Show event(s), ask for confirmation, then output."""
    events = _as_list(event)
    if len(events) > 1:
        confirm_and_output_many(events, output, yes=yes)
        return

    event = events[0]
    display_event(event)

    if yes:
        output_event(event, output)
        return

    choice = Prompt.ask(
        "\n[bold]Confirm?[/bold] [Y]es / [N]o / [E]dit field",
        choices=["y", "n", "e"],
        default="y",
    )

    if choice == "n":
        print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    if choice == "e":
        while True:
            event = edit_event(event)
            display_event(event)
            next_choice = Prompt.ask(
                "\n[bold]Confirm?[/bold] [Y]es / [N]o / [E]dit again",
                choices=["y", "n", "e"],
                default="y",
            )
            if next_choice == "y":
                break
            if next_choice == "n":
                print("[yellow]Cancelled.[/yellow]")
                raise typer.Exit()
            # next_choice == "e" → loop again

    output_event(event, output)


def confirm_and_output_many(events: list[EventLike], output: str | None, yes: bool = False) -> None:
    """Confirm, edit, remove, and output multiple parsed events."""
    display_events(events)

    if yes:
        output_events(events, output)
        return

    while True:
        choice = Prompt.ask(
            "\n[bold]Confirm all?[/bold] [Y]es all / [N]o / [E]dit event / [R]emove event",
            choices=["y", "n", "e", "r"],
            default="y",
        )

        if choice == "y":
            output_events(events, output)
            return
        if choice == "n":
            print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()
        if choice == "e":
            index = _ask_event_index(events, "Event number to edit")
            events[index] = edit_event(events[index])
            display_events(events)
        if choice == "r":
            index = _ask_event_index(events, "Event number to remove")
            removed = events.pop(index)
            print(f"[yellow]Removed:[/yellow] {removed.title}")
            if not events:
                print("[yellow]No events left. Cancelled.[/yellow]")
                raise typer.Exit()
            display_events(events)


def _ask_event_index(events: list[EventLike], prompt: str) -> int:
    while True:
        raw = Prompt.ask(prompt, default="1")
        if raw.isdigit() and 1 <= int(raw) <= len(events):
            return int(raw) - 1
        print(f"[red]Enter a number from 1 to {len(events)}.[/red]")


def edit_event(event: EventLike) -> EventLike:
    """Open event fields in the user's editor for direct editing."""
    data = event.model_dump(mode="json")
    tz = event.get_timezone()

    # Format fields as editable text
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
        f"start_time: {_format_datetime_for_edit(event.start_time, event.all_day)}",
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

    # Parse edited text back into fields
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
                parsed_dt = _parse_datetime_field(value)
                if parsed_dt is None:
                    errors.append(f"start_time: invalid format '{value}' (use YYYY-MM-DD HH:MM)")
                else:
                    updates["start_time"] = parsed_dt
        elif key == "end_time":
            if value:
                parsed_dt = _parse_datetime_field(value)
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

    # Check end_time > start_time if both set
    st = updates.get("start_time", event.start_time)
    et = updates.get("end_time", event.end_time)
    if st and et and et <= st:
        print("[red]Validation error: end_time must be after start_time.[/red]")
        print("[yellow]Keeping original event. Please try editing again.[/yellow]")
        return event

    # Merge updates into original data
    merged = event.model_dump()
    merged.update(updates)
    if merged.get("start_time"):
        return CalendarEvent(**merged)
    return ParsedCalendarEvent(**merged)


def _format_datetime_for_edit(value: datetime | None, all_day: bool) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d") if all_day else value.strftime("%Y-%m-%d %H:%M")


def _parse_datetime_field(value: str) -> datetime | None:
    """Parse a datetime string in common formats, returning None on failure."""
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def read_stdin() -> str | None:
    """Read text from stdin if piped."""
    if not sys.stdin.isatty():
        return sys.stdin.read().strip() or None
    return None


@app.command()
def add(
    arg: Annotated[Optional[str], typer.Argument(help="Text description or image path. Use '-' or omit for stdin.")] = None,
    output: Annotated[Optional[str], typer.Option("-o", "--output", help="Output: 'ics', 'google', or 'apple'")] = None,
    provider: Annotated[Optional[str], typer.Option("-p", "--provider", help="LLM provider name")] = None,
    model: Annotated[Optional[str], typer.Option("-m", "--model", help="LLM model (e.g. openai/gpt-4o)")] = None,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation, output directly.")] = False,
    language: Annotated[Optional[str], typer.Option("-l", "--language", help="OCR language (e.g. chi_sim, eng+chi_sim)")] = None,
    output_json: Annotated[bool, typer.Option("--json", help="Output parsed event as JSON.")] = False,
):
    """Add a calendar event from text, an image, or stdin."""
    text = _resolve_input(arg, language)

    print("[cyan]Parsing event with LLM...[/cyan]")
    event = _parse_with_retry(text, provider=provider, model=model)

    if output_json:
        display_events(event, as_json=True)
        return

    confirm_and_output(event, output, yes=yes)


@app.command()
def parse(
    arg: Annotated[Optional[str], typer.Argument(help="Text description or image path. Use '-' or omit for stdin.")] = None,
    provider: Annotated[Optional[str], typer.Option("-p", "--provider", help="LLM provider name")] = None,
    model: Annotated[Optional[str], typer.Option("-m", "--model", help="LLM model (e.g. openai/gpt-4o)")] = None,
    language: Annotated[Optional[str], typer.Option("-l", "--language", help="OCR language (e.g. chi_sim, eng+chi_sim)")] = None,
    output_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
):
    """Parse text into event fields without saving or syncing."""
    text = _resolve_input(arg, language)

    print("[cyan]Parsing event with LLM...[/cyan]")
    event = _parse_with_retry(text, provider=provider, model=model)

    display_events(event, as_json=output_json)


def _resolve_input(arg: str | None, language: str | None) -> str:
    """Resolve input from argument, file, or stdin."""
    # stdin
    if arg is None or arg == "-":
        stdin_text = read_stdin()
        if not stdin_text:
            print("[red]No input provided. Pass text, an image path, or pipe via stdin.[/red]")
            raise typer.Exit(1)
        return stdin_text

    # image file（仅当参数为实际存在的文件时才尝试）
    import os
    if os.path.exists(arg) and is_image_file(arg):
        from src.input.ocr import extract_text

        print(f"[cyan]Extracting text from image:[/cyan] {arg}")
        text = extract_text(arg, language=language)
        print(f"[dim]OCR result:[/dim] {text}")
        if not text:
            print("[red]No text could be extracted from the image.[/red]")
            raise typer.Exit(1)
        return text

    # plain text
    return arg


def _parse_with_retry(text: str, provider: str | None = None, model: str | None = None, retries: int = 2) -> EventLike | list[EventLike]:
    """Parse event with LLM, retrying on JSON parse failures."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return parse_event(text, provider=provider, model=model)
        except Exception as e:
            last_error = e
            if attempt < retries and ("JSON" in type(e).__name__ or "json" in str(e).lower()):
                print(f"[yellow]Parse attempt {attempt} failed, retrying...[/yellow]")
            else:
                break
    print(f"[red]Failed to parse event:[/red] {last_error}")
    raise typer.Exit(1)


@app.command()
def setup():
    """Interactive setup: configure LLM provider, API keys, and output preferences."""
    config = load_config()
    original_config = {section: (dict(vals) if isinstance(vals, dict) else vals) for section, vals in config.items()}

    # Track API key changes for rollback
    api_key_changes: list[tuple[str, str | None]] = []  # [(provider, old_key)]

    print(Panel("[bold]ccal Setup[/bold]", border_style="cyan"))

    try:
        # LLM provider
        providers = ["openai", "anthropic", "gemini", "openrouter", "deepseek", "groq", "mistral", "cohere", "together_ai", "ollama", "other"]
        current_provider = config["llm"]["provider"]
        current_idx = providers.index(current_provider) + 1 if current_provider in providers else 1
        provider_list = Table(show_header=False, box=None, padding=(0, 2))
        for i, p in enumerate(providers, 1):
            marker = " [bold cyan]*[/bold cyan]" if p == current_provider else ""
            provider_list.add_row(f"[cyan]{i:>2}[/cyan]", f"{p}{marker}")
        print(provider_list)
        while True:
            choice = Prompt.ask("LLM provider (number or name)", default=str(current_idx))
            if choice.isdigit() and 1 <= int(choice) <= len(providers):
                provider = providers[int(choice) - 1]
                break
            elif choice in providers:
                provider = choice
                break
            print(f"[red]Invalid choice. Enter 1-{len(providers)} or a provider name.[/red]")
        config["llm"]["provider"] = provider

        # Model — use sensible default, user can override with -m flag
        default_models = {
            "openai": "openai/gpt-4o",
            "anthropic": "anthropic/claude-sonnet-4-20250514",
            "gemini": "gemini/gemini-2.0-flash",
            "openrouter": "openrouter/openai/gpt-4o",
            "deepseek": "deepseek/deepseek-chat",
            "groq": "groq/llama-3.3-70b-versatile",
            "mistral": "mistral/mistral-large-latest",
            "cohere": "cohere/command-r-plus",
            "together_ai": "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "ollama": "ollama/llama3",
        }
        default_model = default_models.get(provider, config["llm"]["model"])
        config["llm"]["model"] = default_model
        print(f"[dim]Default model: {default_model} (override with -m flag)[/dim]")

        # API key
        no_key_providers = {"ollama"}
        if provider in no_key_providers:
            print(f"[dim]'{provider}' runs locally, no API key needed.[/dim]")
            api_base = Prompt.ask("Ollama API base URL", default=config.get("llm", {}).get("api_base", "http://localhost:11434"))
            config["llm"]["api_base"] = api_base
        else:
            existing_key = get_api_key(provider)
            if existing_key:
                print(f"[green]API key for '{provider}' already configured.[/green]")
                if typer.confirm("Update API key?", default=False):
                    print("[dim]Input is hidden.[/dim]")
                    while True:
                        api_key = Prompt.ask(f"Enter API key for {provider}", password=True)
                        if api_key.strip():
                            break
                        print("[red]API key cannot be empty.[/red]")
                    api_key_changes.append((provider, existing_key))
                    set_api_key(provider, api_key.strip())
                    print(f"[green]API key saved to system keyring.[/green]")
            else:
                print("[dim]Input is hidden.[/dim]")
                while True:
                    api_key = Prompt.ask(f"Enter API key for {provider}", password=True)
                    if api_key.strip():
                        break
                    print("[red]API key cannot be empty.[/red]")
                api_key_changes.append((provider, None))
                set_api_key(provider, api_key.strip())
                print(f"[green]API key saved to system keyring.[/green]")

        # Output method
        output_choices = ["ics", "google"]
        if platform.system() == "Darwin":
            output_choices.append("apple")
        output_default = Prompt.ask(
            "Default output method",
            choices=output_choices,
            default=config["output"]["default"],
        )
        config["output"]["default"] = output_default

        # Apple Calendar setup (macOS)
        if output_default == "apple":
            from src.connections.apple_calendar import list_calendars as apple_list_calendars
            try:
                calendars = apple_list_calendars()
                if calendars:
                    print(f"[dim]Available calendars: {', '.join(calendars)}[/dim]")
                cal_name = Prompt.ask("Apple Calendar name", default=config.get("apple", {}).get("calendar_name", "Home"))
                config.setdefault("apple", {})["calendar_name"] = cal_name
            except Exception as e:
                print(f"[yellow]Could not list calendars: {e}[/yellow]")
                cal_name = Prompt.ask("Apple Calendar name", default="Home")
                config.setdefault("apple", {})["calendar_name"] = cal_name

        # Google Calendar setup
        if output_default == "google":
            from src.config import get_google_credentials_path

            creds_path = get_google_credentials_path()
            if not creds_path.exists():
                print(f"\n[yellow]To use Google Calendar, place your OAuth credentials JSON at:[/yellow]")
                print(f"  {creds_path}")
                print("[dim]Download it from Google Cloud Console > APIs & Services > Credentials[/dim]")
            else:
                print("[green]Google OAuth credentials found.[/green]")
                if typer.confirm("Authenticate with Google now?", default=True):
                    from src.connections.google_calendar import authenticate
                    try:
                        authenticate()
                        print("[green]Google Calendar authenticated successfully![/green]")
                    except Exception as e:
                        print(f"[red]Authentication failed:[/red] {e}")

            calendar_id = Prompt.ask("Google Calendar ID", default=config["google"]["calendar_id"])
            config["google"]["calendar_id"] = calendar_id

        save_config(config)
        print(f"\n[green]Configuration saved![/green]")

    except KeyboardInterrupt:
        # Rollback: restore original config and API keys
        print("\n[yellow]Setup cancelled. Restoring previous configuration...[/yellow]")
        save_config(original_config)
        for prov, old_key in api_key_changes:
            if old_key is None:
                try:
                    import keyring as kr
                    kr.delete_password("ccal", prov)
                except Exception:
                    pass
            else:
                set_api_key(prov, old_key)
        print("[yellow]Configuration restored.[/yellow]")
        raise typer.Exit(1)


@app.command(name="config")
def show_config():
    """Show current configuration."""
    config = load_config()

    table = Table(title="ccal Configuration", show_header=True, border_style="cyan")
    table.add_column("Section", style="bold")
    table.add_column("Key")
    table.add_column("Value")

    for section, values in config.items():
        if isinstance(values, dict):
            for key, val in values.items():
                table.add_row(section, key, str(val))
        else:
            table.add_row("-", section, str(values))

    print(table)

    # Show API key status
    provider = config["llm"]["provider"]
    has_key = get_api_key(provider) is not None
    status = "[green]configured[/green]" if has_key else "[red]not set[/red]"
    print(f"\nAPI key ({provider}): {status}")

    # Platform info
    print(f"Platform: {platform.system()} ({platform.machine()})")
    apple_note = "available" if platform.system() == "Darwin" else "not available (macOS only)"
    print(f"Apple Calendar: {apple_note}")

    # Google Calendar API 状态
    from src.config import get_google_credentials_path, get_google_token_path
    creds_path = get_google_credentials_path()
    token_path = get_google_token_path()
    if not creds_path.exists():
        gcal_status = "[red]credentials missing[/red]"
    elif not token_path.exists():
        gcal_status = "[yellow]not authenticated[/yellow] (run 'ccal setup')"
    else:
        try:
            from google.oauth2.credentials import Credentials
            from src.connections.google_calendar import SCOPES
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            if creds and creds.valid:
                gcal_status = "[green]authenticated[/green]"
            elif creds and creds.expired and creds.refresh_token:
                gcal_status = "[yellow]token expired, can refresh[/yellow]"
            else:
                gcal_status = "[red]token invalid[/red]"
        except Exception as e:
            gcal_status = f"[red]error: {e}[/red]"
    print(f"Google Calendar API: {gcal_status}")


def main():
    app()


if __name__ == "__main__":
    main()
