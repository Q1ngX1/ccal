# ccal 命令参考

## 概览

```
ccal [OPTIONS] COMMAND [ARGS]
```

ccal 是一个 CLI 工具，接受自然语言文本或图片作为输入，通过 LLM 解析为结构化日历事件，然后同步到 Google Calendar、Apple Calendar 或导出为 ICS 文件。

### 全局选项

| 选项 | 缩写 | 说明 |
|------|------|------|
| `--version` | `-V` | 显示版本号并退出 |
| `--install-completion` | | 为当前 shell 安装自动补全 |
| `--show-completion` | | 显示自动补全脚本 |
| `--help` | | 显示帮助信息 |

---

## `ccal setup`

交互式初始配置向导。首次使用前运行一次即可。

```
ccal setup
```

### 配置流程

1. **选择 LLM 提供商** — 显示编号列表，输入编号或名称选择
2. **自动设置默认模型** — 根据 provider 自动选择推荐模型（运行时可用 `-m` 覆盖）
3. **输入 API Key** — 密码模式输入，存入系统密钥链（keyring），不允许空值；Ollama 无需 key，改为配置 API base URL
4. **选择默认输出方式** — `ics` / `google`（macOS 额外可选 `apple`）
5. **（按需）配置 Google Calendar** — 选择 `google` 输出时，提示放置 OAuth credentials 文件并选择 calendar ID
6. **（按需）配置 Apple Calendar** — 选择 `apple` 输出时，列出可用日历并选择

### 支持的 LLM 提供商

| # | Provider | 默认模型 | 需要 API Key |
|---|----------|---------|:---:|
| 1 | openai | `openai/gpt-4o` | ✓ |
| 2 | anthropic | `anthropic/claude-sonnet-4-20250514` | ✓ |
| 3 | gemini | `gemini/gemini-2.0-flash` | ✓ |
| 4 | openrouter | `openrouter/openai/gpt-4o` | ✓ |
| 5 | deepseek | `deepseek/deepseek-chat` | ✓ |
| 6 | groq | `groq/llama-3.3-70b-versatile` | ✓ |
| 7 | mistral | `mistral/mistral-large-latest` | ✓ |
| 8 | cohere | `cohere/command-r-plus` | ✓ |
| 9 | together_ai | `together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo` | ✓ |
| 10 | ollama | `ollama/llama3` | ✗（本地） |
| 11 | other | 用户自定义 | ✓ |

### 配置文件

- 路径：`~/.config/ccal/config.toml`（遵循 XDG 规范）
- API Key 存储：系统密钥链（macOS Keychain / Linux Secret Service / Windows Credential Manager）

---

## `ccal add`

解析输入并创建日历事件（核心命令）。

```
ccal add [ARG] [OPTIONS]
```

### 参数

| 参数 | 说明 |
|------|------|
| `ARG` | 文本描述、图片路径，或省略/`-` 从 stdin 读取 |

### 选项

| 选项 | 缩写 | 说明 |
|------|------|------|
| `--output` | `-o` | 输出目标：`ics`、`google` 或 `apple`（覆盖默认配置） |
| `--provider` | `-p` | 临时指定 LLM 提供商（覆盖 setup 配置） |
| `--model` | `-m` | 临时指定 LLM 模型（覆盖 setup 默认模型） |
| `--yes` | `-y` | 跳过确认，直接输出 |
| `--language` | `-l` | OCR 语言代码，如 `chi_sim`、`eng+chi_sim` |
| `--json` | | 以 JSON 格式输出解析结果（不执行输出动作） |

### 输入方式

```bash
# 1. 直接文本
ccal add "明天下午3点在星巴克和老王喝咖啡"

# 2. 图片（需要 pip install ccal[ocr]）
ccal add screenshot.png
ccal add flyer.jpg -l chi_sim     # 指定 OCR 语言

# 3. stdin 管道
echo "Friday team dinner at 7pm" | ccal add
cat email.txt | ccal add
pbpaste | ccal add                # macOS 剪贴板
```

### 交互流程

```
┌─ Parsed Event ─────────────────────┐
│ Title       周五团建聚餐              │
│ Start       2026-04-17 19:00       │
│ End         2026-04-17 21:00       │
│ Location    -                      │
│ Description -                      │
│ Reminder    15 min                 │
│ Recurrence  -                      │
│ Timezone    Asia/Shanghai          │
│ Attendees   -                      │
└────────────────────────────────────┘

Confirm? [Y]es / [N]o / [E]dit field
```

- **Y**（默认）→ 输出到目标
- **N** → 取消
- **E** → 进入字段编辑模式，可修改 title、start_time、end_time、location、description、reminder_minutes，支持连续编辑多个字段

使用 `-y` 跳过确认，适合脚本调用：

```bash
ccal add "standup at 9am" -y -o ics
```

### 运行时覆盖 LLM 配置

`-p` 和 `-m` 允许在不修改 setup 配置的情况下临时使用不同的 LLM：

```bash
# setup 配置了 openai，但这次想用 anthropic
ccal add "开会" -p anthropic -m anthropic/claude-sonnet-4-20250514

# 使用本地 ollama
ccal add "meeting" -p ollama -m ollama/llama3
```

---

## `ccal parse`

仅解析输入为结构化事件字段，**不保存、不同步**。用于调试或预览。

```
ccal parse [ARG] [OPTIONS]
```

### 参数

| 参数 | 说明 |
|------|------|
| `ARG` | 文本描述、图片路径，或省略/`-` 从 stdin 读取 |

### 选项

| 选项 | 缩写 | 说明 |
|------|------|------|
| `--provider` | `-p` | 临时指定 LLM 提供商 |
| `--model` | `-m` | 临时指定 LLM 模型 |
| `--language` | `-l` | OCR 语言代码 |
| `--json` | | 以 JSON 格式输出 |

### 示例

```bash
# 表格形式输出
ccal parse "next Monday 2pm project review in Room 301"

# JSON 输出（可管道给 jq 等工具）
ccal parse "下周一开会" --json
ccal parse "meeting" --json | jq '.title'
```

### `add` vs `parse` 的区别

| | `add` | `parse` |
|---|---|---|
| 解析输入 | ✓ | ✓ |
| 确认/编辑 | ✓（可 `-y` 跳过） | ✗ |
| 输出到日历/文件 | ✓ | ✗ |
| 用途 | 实际创建事件 | 调试、预览、脚本集成 |

---

## `ccal config`

显示当前配置信息。

```
ccal config
```

输出内容包括：

- LLM 提供商和模型
- API Key 状态（已配置 / 未配置，不显示实际值）
- 默认输出方式
- Google Calendar ID
- 配置文件路径
- 系统平台信息

---

## 输出目标

### ICS 文件（默认）

生成标准 `.ics` 文件，可导入任何日历应用。文件名由事件标题生成（自动清理特殊字符）。

### Google Calendar

通过 OAuth 2.0 认证同步事件。首次使用需：
1. 在 Google Cloud Console 创建 OAuth credentials
2. 下载 `credentials.json` 放到 `~/.config/ccal/`
3. 首次运行时浏览器授权

### Apple Calendar（仅 macOS）

通过 AppleScript 直接添加到 Apple Calendar。非 macOS 系统自动 fallback 到 ICS 导出。

---

## 安装变体

```bash
pip install ccal          # 基础安装：文本输入 → LLM 解析 → 输出
pip install ccal[ocr]     # + 图片 OCR 支持（pytesseract + Pillow）
```

未安装 `[ocr]` 时传入图片路径会提示：
```
OCR dependencies not installed. Install them with: pip install ccal[ocr]
```

---

## 事件字段

LLM 解析后的 `CalendarEvent` 包含以下字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `title` | string | ✓ | 事件标题 |
| `start_time` | datetime | ✓ | 开始时间 |
| `end_time` | datetime | | 结束时间 |
| `location` | string | | 地点 |
| `description` | string | | 描述 |
| `reminder_minutes` | int | | 提前提醒（分钟） |
| `recurrence` | string | | 重复规则（RRULE 格式，如 `FREQ=WEEKLY;BYDAY=FR`） |
| `attendees` | list[string] | | 参与者邮箱列表 |
| `timezone` | string | | IANA 时区（如 `Asia/Shanghai`），未指定时通过 IP 地理定位自动检测 |
