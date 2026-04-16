# ccal

[中文文档](README-zh_cn.md)

A CLI tool that turns natural language text or images into calendar events. Powered by LLMs.

## Features

- **Text input** — describe an event in plain language, ccal parses it into structured fields
- **Image input** — extract text from screenshots/photos via OCR, then parse
- **Multi-LLM support** — works with OpenAI, Anthropic, Gemini, OpenRouter, Deepseek, Groq, Mistral, and more (via [litellm](https://github.com/BerriAI/litellm))
- **ICS export** — generate standard `.ics` files importable by any calendar app
- **Google Calendar sync** — create events directly on Google Calendar via API
- **Apple Calendar sync** — add events via AppleScript (macOS only, auto-fallback to ICS on other platforms)
- **Secure key storage** — API keys stored in your system keyring, never in plain text
- **Geolocation** — auto-detect timezone and location for accurate event scheduling
- **Stdin support** — pipe text from other commands

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (for image input)

## Installation

```bash
git clone https://github.com/your-username/ccal.git
cd ccal
uv sync
```

## Quick Start

### 1. Setup

```bash
ccal setup
```

This will walk you through configuring:
- LLM provider and model
- API key (stored securely in system keyring)
- Default output method (ICS file, Google Calendar, or Apple Calendar)

### 2. Add an event

From text:

```bash
ccal add "Team meeting tomorrow at 3pm in Conference Room A"
```

From an image:

```bash
ccal add flyer.png
```

From stdin:

```bash
echo "Lunch with Alice Friday noon" | ccal add
```

With options:

```bash
ccal add "Dinner Friday 7pm at Luigi's" -o google       # sync to Google Calendar
ccal add "Weekly standup Mon 9am" -o apple               # add to Apple Calendar (macOS)
ccal add "Weekly standup Mon 9am" -o ics                  # export as .ics file
ccal add "会议明天下午两点" -m anthropic/claude-sonnet-4-20250514  # use a specific model
ccal add screenshot.png -l chi_sim                        # OCR with Chinese language
ccal add "Demo at 2pm" -y                                 # skip confirmation
ccal add "Demo at 2pm" --json                             # output as JSON
```

### 3. Parse only (no save)

```bash
ccal parse "Workshop next Wednesday 10am-12pm, Room 301"
ccal parse "下周一上午10点团队周会" --json
```

### 4. View config

```bash
ccal config
```

## Commands

| Command | Description |
|---------|-------------|
| `ccal add [text\|image]` | Parse input and create a calendar event |
| `ccal parse [text\|image]` | Parse and display event fields without saving |
| `ccal setup` | Interactive configuration wizard |
| `ccal config` | Show current configuration and platform info |

### `ccal add` options

| Option | Description |
|--------|-------------|
| `-o`, `--output` | Output method: `ics`, `google`, or `apple` |
| `-p`, `--provider` | LLM provider name |
| `-m`, `--model` | LLM model (e.g. `openai/gpt-4o`) |
| `-y`, `--yes` | Skip confirmation, output directly |
| `-l`, `--language` | OCR language (e.g. `chi_sim`, `eng+chi_sim`) |
| `--json` | Output parsed event as JSON |

## Platform Support

| Feature | macOS | Linux | Windows |
|---------|-------|-------|---------|
| ICS export | ✅ | ✅ | ✅ |
| Google Calendar | ✅ | ✅ | ✅ |
| Apple Calendar | ✅ | ❌ fallback to ICS | ❌ fallback to ICS |

## Configuration

Config is stored at `~/.config/ccal/config.toml`. API keys are stored in your system's native keyring (macOS Keychain / Linux Secret Service / Windows Credential Locker).

For Google Calendar integration, place your OAuth client credentials JSON at `~/.config/ccal/google_credentials.json` (download from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)).

## Project Structure

```
src/
├── main.py                  # CLI entry point (Typer)
├── config.py                # Configuration & keyring management
├── models/
│   ├── model.py             # CalendarEvent Pydantic model
│   └── llm.py               # LLM parsing via litellm
├── input/
│   ├── ocr.py               # Image text extraction (pytesseract)
│   └── geo.py               # IP-based geolocation for timezone
└── connections/
    ├── google_calendar.py   # Google Calendar API integration
    ├── apple_calendar.py    # Apple Calendar via AppleScript (macOS)
    └── ics.py               # ICS file export
```

## License

MIT
