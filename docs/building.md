# 独立打包说明

`ccal` 可以使用 PyInstaller 打包成 Windows、Linux、macOS 上的独立程序。

## 推荐流程

1. 在目标平台上构建。PyInstaller 不能替代原生平台打包，尤其是 macOS 的签名和 notarization。
2. 使用仓库里的辅助脚本：

```bash
uv run python scripts/build_release.py
```

3. 如果本机 Tesseract 没有自动识别到，可以显式传入路径：

```bash
uv run python scripts/build_release.py --tesseract-home "C:\Program Files\Tesseract-OCR"
```

## OCR 打包内容

- Python 依赖：`pytesseract` 和 `Pillow`
- 原生程序：`tesseract` 可执行文件
- 语言数据：`tessdata` 目录，以及你需要的 `.traineddata` 文件

构建脚本会把 Tesseract 安装目录复制到冻结后的程序里，运行时 hook 会把 `pytesseract` 指向这个内置二进制。

如果你不想打包 OCR，可以使用：

```bash
uv run python scripts/build_release.py --no-ocr
```

## 平台说明

- Windows：可以直接打包 `C:\Program Files\Tesseract-OCR` 或其他本地安装目录。
- Linux：建议在 Linux 上构建，并打包系统 Tesseract 安装目录或可移植的 Tesseract 目录树。
- macOS：建议在 macOS 上构建，发布前再做签名和 notarization。

## GitHub Releases

仓库里已经加入了 GitHub Actions 发布流程，tag 推送到 `v*` 时会自动构建并上传到 GitHub Release。

- Windows 产物会在 runner 有 Tesseract 时捆绑 OCR。
- Linux 和 macOS 目前先发布核心 CLI，不强行打包系统级 Tesseract 二进制。
