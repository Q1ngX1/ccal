import click
import os
import platform
import sys
from typing import Annotated, Optional

import typer
from rich import print
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.config import get_api_key, load_config, save_config, set_api_key
from src.event_workflow import (
    IncompleteEventError,
    ask_event_index,
    confirm_and_output as confirm_and_output_impl,
    confirm_and_output_many as confirm_and_output_many_impl,
    display_event as display_event_impl,
    display_events as display_events_impl,
    edit_event as edit_event_impl,
    output_event as output_event_impl,
    output_events as output_events_impl,
)
from src.google_setup import (
    google_calendar_setup_tutorial,
    is_headless_linux,
    looks_like_google_calendar_id_mistake,
    setup_google_calendar,
    validate_google_calendar_id,
)
from src.input.ocr import is_image_file
from src.models.llm import parse_event
from src.models.model import CalendarEvent, EventLike, ParsedCalendarEvent


def version_callback(value: bool):
    if value:
        from importlib.metadata import version

        print(f"ccal {version('ccal')}")
        raise typer.Exit()


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


def display_event(event: EventLike, as_json: bool = False) -> None:
    return display_event_impl(event, as_json=as_json)


def display_events(events: EventLike | list[EventLike], as_json: bool = False) -> None:
    return display_events_impl(events, as_json=as_json)


def output_event(event: EventLike, output: str | None) -> None:
    return output_event_impl(event, output, load_config_fn=load_config)


def output_events(events: EventLike | list[EventLike], output: str | None) -> bool:
    return output_events_impl(events, output, load_config_fn=load_config, output_event_fn=output_event)


def edit_event(event: EventLike) -> EventLike:
    return edit_event_impl(event)


def confirm_and_output(event: EventLike | list[EventLike], output: str | None, yes: bool = False) -> None:
    return confirm_and_output_impl(
        event,
        output,
        yes=yes,
        display_event_fn=display_event,
        display_events_fn=display_events,
        output_event_fn=output_event,
        edit_event_fn=edit_event,
        output_events_fn=output_events,
    )


def confirm_and_output_many(events: list[EventLike], output: str | None, yes: bool = False) -> None:
    return confirm_and_output_many_impl(
        events,
        output,
        yes=yes,
        display_events_fn=display_events,
        output_events_fn=output_events,
        edit_event_fn=edit_event,
    )


def _setup_google_calendar(config: dict[str, object]) -> None:
    return setup_google_calendar(config, validate_calendar_id_fn=_validate_google_calendar_id)


def _validate_google_calendar_id(service, calendar_id: str) -> bool:
    return validate_google_calendar_id(service, calendar_id)


def _google_calendar_setup_tutorial(headless: bool):
    return google_calendar_setup_tutorial(headless)


def _looks_like_google_calendar_id_mistake(value: object) -> bool:
    return looks_like_google_calendar_id_mistake(value)


def _is_headless_linux() -> bool:
    return is_headless_linux()


def read_stdin() -> str | None:
    """Read text from stdin if piped."""
    if not sys.stdin.isatty():
        return sys.stdin.read().strip() or None
    return None


def _resolve_input(arg: str | None, language: str | None) -> str:
    """Resolve input from argument, file, or stdin."""
    if arg is None or arg == "-":
        stdin_text = read_stdin()
        if not stdin_text:
            print("[red]No input provided. Pass text, an image path, or pipe via stdin.[/red]")
            raise typer.Exit(1)
        return stdin_text

    if os.path.exists(arg) and is_image_file(arg):
        from src.input.ocr import extract_text

        print(f"[cyan]Extracting text from image:[/cyan] {arg}")
        text = extract_text(arg, language=language)
        print(f"[dim]OCR result:[/dim] {text}")
        if not text:
            print("[red]No text could be extracted from the image.[/red]")
            raise typer.Exit(1)
        return text

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


@app.command()
def setup():
    """Interactive setup: configure LLM provider, API keys, and output preferences."""
    config = load_config()
    original_config = {section: (dict(vals) if isinstance(vals, dict) else vals) for section, vals in config.items()}

    api_key_changes: list[tuple[str, str | None]] = []

    print(Panel("[bold]ccal Setup[/bold]", border_style="cyan"))

    try:
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

        output_choices = ["ics", "google"]
        if platform.system() == "Darwin":
            output_choices.append("apple")
        output_default = Prompt.ask(
            "Default output method",
            choices=output_choices,
            default=config["output"]["default"],
        )
        config["output"]["default"] = output_default

        configure_google_calendar = typer.confirm(
            "Configure Google Calendar API now?",
            default=(output_default == "google"),
        )
        if configure_google_calendar:
            _setup_google_calendar(config)

        if output_default == "apple":
            _setup_apple_calendar(config)

        save_config(config)
        print(f"\n[green]Configuration saved![/green]")

    except KeyboardInterrupt:
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


def _setup_apple_calendar(config: dict[str, object]) -> None:
    """Interactive Apple Calendar setup."""
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

    provider = config["llm"]["provider"]
    has_key = get_api_key(provider) is not None
    status = "[green]configured[/green]" if has_key else "[red]not set[/red]"
    print(f"\nAPI key ({provider}): {status}")

    print(f"Platform: {platform.system()} ({platform.machine()})")
    apple_note = "available" if platform.system() == "Darwin" else "not available (macOS only)"
    print(f"Apple Calendar: {apple_note}")

    from src.config import get_google_credentials_path, get_google_token_path

    creds_path = get_google_credentials_path(config)
    token_path = get_google_token_path(config)
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
