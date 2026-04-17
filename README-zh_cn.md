# ccal

[English](README.md)

一个命令行工具，将自然语言文本或图片转换为日历事件。由 LLM 驱动。

## 功能特性

- **文本输入** — 用自然语言描述事件，ccal 自动解析为结构化字段
- **图片输入** — 通过 OCR 从截图/照片中提取文字，再进行解析
- **多 LLM 支持** — 支持 OpenAI、Anthropic、Gemini、OpenRouter、Deepseek、Groq、Mistral 等（通过 [litellm](https://github.com/BerriAI/litellm)）
- **ICS 导出** — 生成标准 `.ics` 文件，可被任何日历应用导入
- **Google 日历同步** — 通过 API 直接在 Google Calendar 创建事件
- **Apple 日历同步** — 通过 AppleScript 添加事件（仅 macOS，其他平台自动降级为 ICS）
- **安全密钥存储** — API key 存储在系统原生密钥链中，不以明文保存
- **地理定位** — 自动检测时区和位置，确保事件时间准确
- **管道输入** — 支持从其他命令管道传入文本

## 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)（图片输入需要）

## 安装

```bash
git clone https://github.com/your-username/ccal.git
cd ccal
uv sync
```

## 快速开始

### 1. 初始配置

```bash
ccal setup
```

将引导你配置：
- LLM 提供商和模型
- API key（安全存储在系统密钥链中）
- 默认输出方式（ICS 文件、Google 日历或 Apple 日历）

### 2. 添加事件

文本输入：

```bash
ccal add "明天下午3点在会议室A开团队会议"
```

图片输入：

```bash
ccal add flyer.png
```

管道输入：

```bash
echo "周五中午和 Alice 吃饭" | ccal add
```

更多选项：

```bash
ccal add "周五晚上7点在 Luigi's 餐厅聚餐" -o google       # 同步到 Google 日历
ccal add "每周一早上9点站会" -o apple                       # 添加到 Apple 日历 (macOS)
ccal add "每周一早上9点站会" -o ics                          # 导出为 .ics 文件
ccal add "Meeting tomorrow at 2pm" -m anthropic/claude-sonnet-4-20250514  # 指定模型
ccal add screenshot.png -l chi_sim                          # 使用中文 OCR
ccal add "下午2点演示" -y                                    # 跳过确认
ccal add "下午2点演示" --json                                # JSON 格式输出
```

### 3. 仅解析（不保存）

```bash
ccal parse "下周三上午10点到12点，301会议室，技术研讨会"
ccal parse "下周一上午10点团队周会" --json
```

### 4. 查看配置

```bash
ccal config
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `ccal add [文本\|图片]` | 解析输入并创建日历事件 |
| `ccal parse [文本\|图片]` | 解析并展示事件字段，不保存 |
| `ccal setup` | 交互式配置向导 |
| `ccal config` | 查看当前配置和平台信息 |

### `ccal add` 选项

| 选项 | 说明 |
|------|------|
| `-o`, `--output` | 输出方式：`ics`、`google` 或 `apple` |
| `-p`, `--provider` | LLM 提供商名称 |
| `-m`, `--model` | LLM 模型（如 `openai/gpt-4o`） |
| `-y`, `--yes` | 跳过确认，直接输出 |
| `-l`, `--language` | OCR 语言（如 `chi_sim`、`eng+chi_sim`） |
| `--json` | 以 JSON 格式输出解析结果 |

## 平台支持

| 功能 | macOS | Linux | Windows |
|------|-------|-------|---------|
| ICS 导出 | ✅ | ✅ | ✅ |
| Google 日历 | ✅ | ✅ | ✅ |
| Apple 日历 | ✅ | ❌ 降级为 ICS | ❌ 降级为 ICS |

## 配置说明

配置文件存储在 `~/.config/ccal/config.toml`。API key 存储在系统原生密钥链中（macOS Keychain / Linux Secret Service / Windows Credential Locker）。

使用 Google 日历功能时，请把 OAuth 客户端凭据 JSON 文件放到 `ccal setup` 中配置的目录里，文件名应为 `google_credentials.json`。

你也可以在 `ccal setup` 的中间步骤里单独配置 Google 日历，即使默认输出方式不是 Google 也可以先把 API 配好。

## 项目结构

```
src/
├── main.py                  # CLI 入口 (Typer)
├── config.py                # 配置与密钥链管理
├── models/
│   ├── model.py             # CalendarEvent Pydantic 模型
│   └── llm.py               # 通过 litellm 调用 LLM 解析
├── input/
│   ├── ocr.py               # 图片文字提取 (pytesseract)
│   └── geo.py               # 基于 IP 的地理定位与时区检测
└── connections/
    ├── google_calendar.py   # Google Calendar API 集成
    ├── apple_calendar.py    # Apple Calendar AppleScript 集成 (macOS)
    └── ics.py               # ICS 文件导出
```

## 许可证

MIT
