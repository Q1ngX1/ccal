import json
from datetime import datetime

import litellm

from src.config import get_api_key, load_config
from src.models.model import CalendarEvent

SYSTEM_PROMPT = """You are a calendar event parser. Extract event details from the user's text and return a JSON object with these fields:

- title (string, required): Event title
- start_time (string, required): ISO 8601 datetime, e.g. "2026-04-16T15:00:00"
- end_time (string or null): ISO 8601 datetime, null if not specified
- location (string or null): Event location, null if not specified
- description (string or null): Additional details, null if not specified
- reminder_minutes (integer or null): Minutes before event for reminder, null if not specified
- recurrence (string or null): RRULE format recurrence rule (e.g. "FREQ=WEEKLY;BYDAY=MO"), null if not a recurring event
- attendees (array of strings): List of attendee email addresses, empty array if none
- timezone (string or null): IANA timezone (e.g. "Asia/Shanghai"), null to use user's local timezone

Important:
- The current date and time is: {now}
- The user's location is: {location}
- The user's timezone is: {timezone}
- Resolve relative dates like "tomorrow", "next Monday", "下周一" relative to the current date.
- If no year is specified, assume the current year (or next year if the date has already passed).
- If no end time is given, set end_time to null.
- Unless the text explicitly mentions a different timezone, set timezone to null (the user's local timezone will be used).
- Return ONLY valid JSON, no markdown fences or extra text."""


def parse_event(text: str, provider: str | None = None, model: str | None = None) -> CalendarEvent:
    """Parse natural language text into a CalendarEvent using an LLM."""
    config = load_config()

    llm_model = model or config["llm"]["model"]
    llm_provider = provider or config["llm"]["provider"]

    # Resolve API key — some providers (ollama) don't need one
    no_key_providers = {"ollama"}
    api_key = None
    if llm_provider not in no_key_providers:
        api_key = get_api_key(llm_provider)
        if not api_key:
            raise RuntimeError(
                f"No API key found for provider '{llm_provider}'. "
                f"Run 'ccal setup' to configure your API key."
            )

    from src.input.geo import get_geo_info

    geo = get_geo_info()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S (%A)")
    system_prompt = SYSTEM_PROMPT.format(
        now=now,
        location=geo.summary(),
        timezone=geo.timezone or "Unknown",
    )

    # Build litellm kwargs
    completion_kwargs: dict = {
        "model": llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
    }
    if api_key:
        completion_kwargs["api_key"] = api_key
    api_base = config["llm"].get("api_base")
    if api_base:
        completion_kwargs["api_base"] = api_base

    response = litellm.completion(**completion_kwargs)

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        content = "\n".join(lines)

    data = json.loads(content)
    return CalendarEvent(**data)
