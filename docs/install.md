# ccal 安装指南

`ccal` 提供独立可执行文件，也提供一个官方安装脚本，适用于 Linux、macOS 和 Windows。

## 推荐安装方式

从仓库运行安装脚本：

```bash
curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh
```

脚本会自动从 GitHub Releases 中选择与你平台匹配的最新构建，并安装到 PATH 目录。

默认安装位置：

- 以 root 运行时，或者 `/usr/local/bin` 可写时，使用 `/usr/local/bin`
- 否则使用 `~/.local/bin`

你也可以指定安装目录：

```bash
curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh -s -- --prefix "$HOME/bin"
```

也可以固定安装某个版本：

```bash
curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh -s -- --version v0.1.12
```

## Windows 安装器

在 Windows 上运行 PowerShell 安装脚本：

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.ps1 | iex"
```

脚本会下载 Windows release 资产，并默认把 `ccal.exe` 加到当前用户 PATH。

如果你在 Git Bash 或 MinGW 里运行，也可以直接通过 `powershell.exe` 调用同一条命令。

如果你机器上已经安装了 Tesseract，并希望 `ccal` 使用它，可以传入安装目录：

```powershell
powershell -ExecutionPolicy Bypass -Command "$p = Join-Path $env:TEMP 'install-ccal.ps1'; irm https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.ps1 -OutFile $p; powershell -ExecutionPolicy Bypass -File $p -TesseractHome 'C:\Program Files\Tesseract-OCR'"
```

也可以直接指定 `tesseract.exe`：

```powershell
powershell -ExecutionPolicy Bypass -Command "$p = Join-Path $env:TEMP 'install-ccal.ps1'; irm https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.ps1 -OutFile $p; powershell -ExecutionPolicy Bypass -File $p -TesseractCmd 'C:\Program Files\Tesseract-OCR\tesseract.exe'"
```

当前 Windows 官方 release 在构建机安装了 Tesseract 时会自动带上 OCR 支持，所以今天不需要单独的 “OCR 开关”。

## 直接下载

如果你更喜欢手动下载，可以去 GitHub Releases 页面下载对应平台的资产文件。

下载后：

```bash
chmod +x ccal
ccal --help
```

## 说明

- Linux 和 macOS 版本以独立可执行文件发布。
- Windows 用户可以使用 `install.ps1`，也可以直接下载 GitHub Releases 页面中的 `.exe` 文件。
- 如果安装脚本找不到匹配的资产，请确认 release 已发布且平台受支持。
