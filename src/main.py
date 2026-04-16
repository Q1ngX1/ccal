import json as json_lib
import platform
import sys
from typing import Annotated, Optional

import typer
from rich import print
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.config import load_config, save_config, set_api_key, get_api_key
from src.connections.ics import export_to_ics
from src.input.ocr import is_image_file, extract_text
from src.models.llm import parse_event
from src.models.model import CalendarEvent


def version_callback(value: bool):
    if value:
        from importlib.metadata import version
        print(f"ccal {version('ccal')}")
        raise typer.Exit()


app = typer.Typer(
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


def display_event(event: CalendarEvent, as_json: bool = False) -> None:
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
    table.add_row("Start", event.start_time.strftime("%Y-%m-%d %H:%M"))
    table.add_row("End", event.end_time.strftime("%Y-%m-%d %H:%M") if event.end_time else "-")
    table.add_row("Location", event.location or "-")
    table.add_row("Description", event.description or "-")
    table.add_row("Reminder", f"{event.reminder_minutes} min" if event.reminder_minutes else "-")
    table.add_row("Recurrence", event.recurrence or "-")
    table.add_row("Timezone", event.get_timezone())
    table.add_row("Attendees", ", ".join(event.attendees) if event.attendees else "-")

    print(table)


def output_event(event: CalendarEvent, output: str | None) -> None:
    """Output event to the chosen destination."""
    config = load_config()
    output_method = output or config["output"]["default"]

    if output_method == "google":
        from src.connections.google_calendar import authenticate, create_event

        print("[cyan]Syncing to Google Calendar...[/cyan]")
        service = authenticate()
        result = create_event(service, event)
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


def confirm_and_output(event: CalendarEvent, output: str | None, yes: bool = False) -> None:
    """Show event, ask for confirmation, then output."""
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
        event = edit_event(event)
        display_event(event)
        if not typer.confirm("Save this event?", default=True):
            print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()

    output_event(event, output)


def edit_event(event: CalendarEvent) -> CalendarEvent:
    """Allow user to interactively edit event fields. Supports editing multiple fields."""
    data = event.model_dump()
    editable_fields = ["title", "start_time", "end_time", "location", "description", "reminder_minutes"]

    while True:
        field = Prompt.ask(
            "Which field to edit?",
            choices=editable_fields,
        )

        current = data.get(field)
        new_value = Prompt.ask(f"[bold]{field}[/bold] (current: {current})")

        if field in ("start_time", "end_time"):
            from datetime import datetime
            data[field] = datetime.fromisoformat(new_value)
        elif field == "reminder_minutes":
            data[field] = int(new_value) if new_value else None
        else:
            data[field] = new_value if new_value else None

        if not typer.confirm("Edit another field?", default=False):
            break

    return CalendarEvent(**data)


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
        display_event(event, as_json=True)
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

    display_event(event, as_json=output_json)


def _resolve_input(arg: str | None, language: str | None) -> str:
    """Resolve input from argument, file, or stdin."""
    # stdin
    if arg is None or arg == "-":
        stdin_text = read_stdin()
        if not stdin_text:
            print("[red]No input provided. Pass text, an image path, or pipe via stdin.[/red]")
            raise typer.Exit(1)
        return stdin_text

    # image file
    if is_image_file(arg):
        print(f"[cyan]Extracting text from image:[/cyan] {arg}")
        text = extract_text(arg, language=language)
        print(f"[dim]OCR result:[/dim] {text}")
        if not text:
            print("[red]No text could be extracted from the image.[/red]")
            raise typer.Exit(1)
        return text

    # plain text
    return arg


def _parse_with_retry(text: str, provider: str | None = None, model: str | None = None, retries: int = 2) -> CalendarEvent:
    """Parse event with LLM, retrying on JSON parse failures."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return parse_event(text, provider=provider, model=model)
        except Exception as e:
            last_error = e
            if attempt < retries and "JSON" in str(e).__class__.__name__ or "json" in str(e).lower():
                print(f"[yellow]Parse attempt {attempt} failed, retrying...[/yellow]")
            else:
                break
    print(f"[red]Failed to parse event:[/red] {last_error}")
    raise typer.Exit(1)


@app.command()
def setup():
    """Interactive setup: configure LLM provider, API keys, and output preferences."""
    config = load_config()

    print(Panel("[bold]ccal Setup[/bold]", border_style="cyan"))

    # LLM provider
    providers = ["openai", "anthropic", "gemini", "openrouter", "deepseek", "groq", "mistral", "cohere", "together_ai", "ollama", "other"]
    provider = Prompt.ask(
        "LLM provider",
        choices=providers,
        default=config["llm"]["provider"],
    )
    config["llm"]["provider"] = provider

    # Model
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
    model = Prompt.ask(f"LLM model", default=default_model)
    config["llm"]["model"] = model

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
                api_key = Prompt.ask(f"Enter API key for {provider}", password=True)
                set_api_key(provider, api_key)
                print(f"[green]API key saved to system keyring.[/green]")
        else:
            api_key = Prompt.ask(f"Enter API key for {provider}", password=True)
            set_api_key(provider, api_key)
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


def main():
    app()


if __name__ == "__main__":
    main()
