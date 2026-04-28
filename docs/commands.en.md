# ccal Command Reference
## Overview

```bash
ccal [OPTIONS] COMMAND [ARGS]
```

`ccal` is a CLI tool that accepts natural language text or images as input, uses an LLM to parse them into structured calendar events, and then syncs them to Google Calendar, Apple Calendar, or exports them as an ICS file.

### Global Options

| Option | Short | Description |
|------|------|------|
| `--version` | `-V` | Show the version and exit |
| `--install-completion` | | Install shell completion for the current shell |
| `--show-completion` | | Show the completion script |
| `--help` | | Show help information |

---

## `ccal setup`

Interactive first-run configuration wizard.

```bash
ccal setup
```

### Configuration Flow

1. Select an LLM provider. A numbered list is shown, and you can enter either the number or the provider name.
2. The default model is selected automatically based on the provider. You can override it later with `-m` at runtime.
3. Enter an API key in hidden input mode. The key is stored in the system keyring. Ollama does not require an API key, but you will be asked for its API base URL instead.
4. Choose the default output method: `ics`, `google`, or on macOS optionally `apple`.
5. Decide whether to configure the Google Calendar API. This is a separate step. If you accept, `ccal` shows a short tutorial and then asks for the credentials directory or JSON file and the Calendar ID.
6. Optionally configure Apple Calendar. If `apple` output is selected, available calendars are listed when possible.

### Supported LLM Providers

| # | Provider | Default Model | Requires API Key |
|---|----------|---------|:---:|
| 1 | openai | `openai/gpt-4o` | Yes |
| 2 | anthropic | `anthropic/claude-sonnet-4-20250514` | Yes |
| 3 | gemini | `gemini/gemini-2.0-flash` | Yes |
| 4 | openrouter | `openrouter/openai/gpt-4o` | Yes |
| 5 | deepseek | `deepseek/deepseek-chat` | Yes |
| 6 | groq | `groq/llama-3.3-70b-versatile` | Yes |
| 7 | mistral | `mistral/mistral-large-latest` | Yes |
| 8 | cohere | `cohere/command-r-plus` | Yes |
| 9 | together_ai | `together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo` | Yes |
| 10 | ollama | `ollama/llama3` | No, local only |
| 11 | other | User-defined | Yes |

### Config Files

- Path: `~/.config/ccal/config.toml` (follows XDG conventions)
- API keys: stored in the system keyring (macOS Keychain / Linux Secret Service / Windows Credential Manager)

---

## `ccal add`

Parse input and create a calendar event.

```bash
ccal add [ARG] [OPTIONS]
```

### Arguments

| Argument | Description |
|------|------|
| `ARG` | Text description, image path, or omit / use `-` to read from stdin |

### Options

| Option | Short | Description |
|------|------|------|
| `--output` | `-o` | Output target: `ics`, `google`, or `apple` (overrides the config default) |
| `--provider` | `-p` | Temporarily choose an LLM provider (overrides setup) |
| `--model` | `-m` | Temporarily choose an LLM model (overrides setup default) |
| `--yes` | `-y` | Skip confirmation and output immediately |
| `--language` | `-l` | OCR language code, such as `chi_sim` or `eng+chi_sim` |
| `--json` | | Print the parsed event as JSON instead of creating output |

### Input Examples

```bash
# 1. Direct text
ccal add "Meeting tomorrow at 3pm in the conference room"

# 2. Image input (requires `pip install ccal[ocr]`)
ccal add screenshot.png
ccal add flyer.jpg -l chi_sim

# 3. stdin
echo "Friday team dinner at 7pm" | ccal add
cat email.txt | ccal add
pbpaste | ccal add
```

### Interaction Flow

```
Parsed Event
Title       Friday team dinner
Start       2026-04-17 19:00
End         2026-04-17 21:00
Location    -
Description -
Reminder    15 min
Recurrence  -
Timezone    Asia/Shanghai
Attendees   -

Confirm? [Y]es / [N]o / [E]dit field
```

- `Y` (default) -> output to the selected target
- `N` -> cancel
- `E` -> enter field-edit mode, where you can modify title, start_time, end_time, location, description, and reminder_minutes; you can edit multiple fields in sequence

Use `-y` to skip confirmation, which is useful for scripts:

```bash
ccal add "standup at 9am" -y -o ics
```

### Runtime LLM Overrides

`-p` and `-m` let you use a different LLM temporarily without changing setup:

```bash
# Setup uses openai, but this run uses anthropic
ccal add "Launch meeting" -p anthropic -m anthropic/claude-sonnet-4-20250514

# Use local Ollama
ccal add "meeting" -p ollama -m ollama/llama3
```

---

## `ccal parse`

Parse input into structured event fields only. This command does **not** save or sync anything, so it is useful for debugging and previewing.

```bash
ccal parse [ARG] [OPTIONS]
```

### Arguments

| Argument | Description |
|------|------|
| `ARG` | Text description, image path, or omit / use `-` to read from stdin |

### Options

| Option | Short | Description |
|------|------|------|
| `--provider` | `-p` | Temporarily choose an LLM provider |
| `--model` | `-m` | Temporarily choose an LLM model |
| `--language` | `-l` | OCR language code |
| `--json` | | Print JSON output |

### Examples

```bash
# Table output
ccal parse "next Monday 2pm project review in Room 301"

# JSON output for piping into jq or other tools
ccal parse "meeting" --json | jq '.title'
```

### `add` vs `parse`

| | `add` | `parse` |
|---|---|---|
| Parse input | Yes | Yes |
| Confirm / edit | Yes, unless `-y` is used | No |
| Output to calendar file / service | Yes | No |
| Best for | Actual event creation | Debugging, previewing, automation |

---

## `ccal config`

Show the current configuration.

```bash
ccal config
```

The output includes:

- LLM provider and model
- API key status, shown only as configured / not configured
- Default output method
- Google Calendar ID
- Config file paths
- Platform information

---

## `ccal update`

Download and install the latest standalone release for the current platform.

```bash
ccal update
```

`ccal update` is intended for standalone binaries produced by the release workflow or the installer. It downloads the latest GitHub Release asset for your platform and replaces the current binary.

If you are running from source, reinstall with your package manager or development workflow instead.

---

## Output Targets

### ICS File

Generate a standard `.ics` file that can be imported into any calendar app. The filename is derived from the event title, with special characters cleaned up automatically.

### Google Calendar

Sync events through OAuth 2.0. `ccal` uses two local files:

- `google_credentials.json`: the OAuth client credential JSON downloaded from Google Cloud Console. It contains the client ID and client secret, and should be kept after setup.
- `google_token_*.json`: the cached login token created after the first authorization. The access token can expire, but it is usually refreshed automatically. `ccal` chooses the cache file based on the current credential path and auth mode.

First-time setup flow:

1. Create OAuth credentials in Google Cloud Console.
2. Enable the Google Calendar API and configure the OAuth consent screen.
3. Choose the correct OAuth client type:
   - `Desktop app` for a machine with a browser
   - `TVs and Limited Input devices` for a headless Linux server
4. If the project is in `Testing`, add your Google account to `Test users`.
5. Download the OAuth JSON, place it in the directory configured by `ccal setup`, and make sure the filename is `google_credentials.json`.
6. Complete authorization the first time you run it. Later runs will use the local token cache automatically.

Calendar ID is validated during setup. You can find it in the Google Calendar web UI under `Settings and sharing` -> `Integrate calendar`, or use `primary` for the main calendar.

### Apple Calendar

Use AppleScript to add events directly to Apple Calendar. On non-macOS systems, this automatically falls back to ICS export.

---

## Installation Variants

```bash
pip install ccal          # Core install: text input -> LLM parsing -> output
pip install ccal[ocr]     # + image OCR support (pytesseract + Pillow)
```

If `[ocr]` is not installed and you pass an image path, `ccal` prints:

```text
OCR dependencies not installed. Install them with: pip install ccal[ocr]
```

---

## Event Fields

The parsed `CalendarEvent` model contains these fields:

| Field | Type | Required | Description |
|------|------|:---:|------|
| `title` | string | Yes | Event title |
| `start_time` | datetime | Yes | Start time |
| `end_time` | datetime | No | End time |
| `location` | string | No | Event location |
| `description` | string | No | Additional notes |
| `reminder_minutes` | int | No | Reminder lead time in minutes |
| `recurrence` | string | No | RRULE recurrence string, for example `FREQ=WEEKLY;BYDAY=FR` |
| `attendees` | list[string] | No | List of attendee email addresses |
| `timezone` | string | No | IANA timezone, such as `Asia/Shanghai`; if omitted, timezone is resolved automatically |
