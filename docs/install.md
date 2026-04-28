# ccal 安装指南

`ccal` 提供独立可执行文件，也提供一个官方的 shell 安装脚本，适用于 Linux 和 macOS。

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
curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh -s -- --version v0.1.10
```

## 直接下载

如果你更喜欢手动下载，可以去 GitHub Releases 页面下载对应平台的资产文件。

下载后：

```bash
chmod +x ccal
ccal --help
```

## 说明

- Linux 和 macOS 版本以独立可执行文件发布。
- Windows 用户请下载 GitHub Releases 页面中的 `.exe` 文件。
- 如果安装脚本找不到匹配的资产，请确认 release 已发布且平台受支持。
