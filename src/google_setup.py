import os
import platform
from pathlib import Path

import typer
from rich import print
from rich.panel import Panel
from rich.prompt import Prompt


def setup_google_calendar(
    config: dict[str, object],
    *,
    validate_calendar_id_fn=None,
) -> None:
    """Interactive Google Calendar API configuration."""
    from src.config import get_google_credentials_path
    headless = is_headless_linux()

    print(google_calendar_setup_tutorial(headless=headless))

    default_auth_mode = "device" if headless else config.get("google", {}).get("auth_mode", "desktop")
    auth_mode = Prompt.ask(
        "Google auth mode",
        choices=["desktop", "device"],
        default=default_auth_mode,
    )
    config.setdefault("google", {})["auth_mode"] = auth_mode

    if auth_mode == "device":
        print(
            "[dim]Device mode needs a 'TVs and Limited Input devices' OAuth client. "
            "A Desktop app client JSON will not work here.[/dim]"
        )
    else:
        if headless:
            print(
                "[yellow]Desktop mode needs a browser on this machine. "
                "If that is not available, switch to device mode and create a device client.[/yellow]"
            )

    current_path = get_google_credentials_path(config)
    creds_input = Prompt.ask("Google credentials path or directory", default=str(current_path))
    creds_input_path = Path(creds_input).expanduser()

    if creds_input_path.exists() and creds_input_path.is_file():
        creds_path = creds_input_path
    elif creds_input_path.suffix.lower() == ".json":
        creds_path = creds_input_path
        creds_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        creds_input_path.mkdir(parents=True, exist_ok=True)
        creds_path = creds_input_path / "google_credentials.json"

    config.setdefault("google", {})["credentials_path"] = str(creds_path)

    if not creds_path.exists():
        print(f"\n[yellow]Place your OAuth credentials JSON at:[/yellow]")
        print(f"  {creds_path}")
    else:
        print("[green]Google OAuth credentials found.[/green]")
        service = None
        if typer.confirm("Authenticate with Google now?", default=True):
            from src.connections.google_calendar import authenticate
            try:
                service = authenticate(config)
                print("[green]Google Calendar authenticated successfully![/green]")
            except Exception as e:
                print(f"[red]Authentication failed:[/red] {e}")
                raise typer.Exit(1)
        if service is not None:
            while True:
                calendar_id = Prompt.ask("Google Calendar ID", default=config["google"]["calendar_id"])
                if looks_like_google_calendar_id_mistake(calendar_id):
                    print("[red]That looks like an OAuth client id or file path, not a Calendar ID.[/red]")
                    print("[dim]Use something like `primary` or your calendar's email-style ID.[/dim]")
                    continue
                validate_calendar_id = validate_calendar_id_fn or validate_google_calendar_id
                if validate_calendar_id(service, calendar_id):
                    config["google"]["calendar_id"] = calendar_id
                    break
                print("[yellow]That Calendar ID could not be found or accessed. Try another one.[/yellow]")
            return

    calendar_default = config["google"]["calendar_id"]
    if looks_like_google_calendar_id_mistake(calendar_default):
        calendar_default = "primary"
    while True:
        calendar_id = Prompt.ask("Google Calendar ID", default=calendar_default)
        if looks_like_google_calendar_id_mistake(calendar_id):
            print("[red]That looks like an OAuth client id or file path, not a Calendar ID.[/red]")
            print("[dim]Use something like `primary` or your calendar's email-style ID.[/dim]")
            calendar_default = "primary"
            continue
        config["google"]["calendar_id"] = calendar_id
        break


def validate_google_calendar_id(service, calendar_id: str) -> bool:
    """Return True if the authenticated user can access the given Google Calendar ID."""
    from googleapiclient.errors import HttpError

    try:
        service.calendarList().get(calendarId=calendar_id).execute()
        return True
    except HttpError as exc:
        status = getattr(exc.resp, "status", None)
        if status in {400, 403, 404}:
            return False
        raise


def google_calendar_setup_tutorial(headless: bool) -> Panel:
    """Build the Google Calendar setup guidance panel."""
    auth_mode_note = (
        "Device mode works on headless Linux."
        if headless
        else "Desktop mode uses a browser on the local machine."
    )
    text = (
        "[bold]Google Calendar setup[/bold]\n"
        "1. Enable the Google Calendar API and configure the OAuth consent screen.\n"
        "2. Pick the right OAuth client type:\n"
        "   - [bold]Desktop app[/bold] for a machine with a browser.\n"
        "   - [bold]TVs and Limited Input devices[/bold] for a headless Linux server.\n"
        "3. Set the OAuth consent screen user type correctly:\n"
        "   - [bold]External[/bold] for personal Gmail accounts or users outside your Workspace.\n"
        "   - [bold]Internal[/bold] only if every account belongs to the same Google Workspace or Cloud Identity organization.\n"
        "   - If you see [bold]org_internal[/bold], the project is organization-restricted; switch the consent screen to External or use an account inside that organization.\n"
        "4. If the app is in [bold]Testing[/bold] status, add your Google account to the [bold]Test users[/bold] list before authenticating.\n"
        "   Otherwise Google may show [bold]Access blocked[/bold] / [bold]access_denied[/bold] even when the client looks correct.\n"
        "   This is the common reason a personal Gmail account is rejected even after the device code step works.\n"
        "5. Download the OAuth client JSON. ccal needs the JSON file, not just the client id.\n"
        "6. For headless Linux, choose [bold]device[/bold] auth mode and use a device-client JSON.\n"
        "   For a normal desktop machine, choose [bold]desktop[/bold] auth mode.\n"
        "7. Enter either the JSON file path directly or the directory that contains it.\n"
        "8. To find a shared calendar's ID, open Google Calendar on the web, open that calendar's [bold]Settings and sharing[/bold], then look under [bold]Integrate calendar[/bold].\n"
        "   The main calendar can always use [bold]primary[/bold].\n"
        "9. Enter a Calendar ID such as [bold]primary[/bold] or the Integrate calendar value; do not paste the OAuth client id or JSON path there.\n"
        "10. Keep the OAuth JSON file around after setup. It is the client credential, not the login token, and ccal may need it again if the token expires or is revoked.\n"
        "    The login token is cached separately under ccal's config directory and can be regenerated.\n"
        f"11. {auth_mode_note}\n"
    )
    return Panel(text, border_style="cyan", title="Google Calendar")


def looks_like_google_calendar_id_mistake(value: object) -> bool:
    """Detect obvious misconfigured calendar IDs."""
    if not isinstance(value, str):
        return False
    return value.endswith(".json") or ".apps.googleusercontent.com" in value or "/" in value


def is_headless_linux() -> bool:
    """Detect a Linux environment without a GUI display."""
    if platform.system() != "Linux":
        return False
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
