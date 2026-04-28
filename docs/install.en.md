# ccal Install Guide

`ccal` ships with standalone release binaries and an official installer for Linux, macOS, and Windows.

## Recommended installation

Run the installer from the repository:

```bash
curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh
```

This downloads the latest matching GitHub Release asset for your platform and installs it to a PATH directory.

By default, the installer uses:

- `/usr/local/bin` when run as root or when that directory is writable
- `~/.local/bin` otherwise

You can override the target directory:

```bash
curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh -s -- --prefix "$HOME/bin"
```

You can also pin a specific release:

```bash
curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh -s -- --version v0.1.10
```

## Windows installer

On Windows, run the PowerShell installer:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer downloads the Windows release asset and adds `ccal.exe` to your user PATH by default.

If you already have Tesseract installed and want `ccal` to use it, pass the installation directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -TesseractHome "C:\Program Files\Tesseract-OCR"
```

You can also point directly at `tesseract.exe`:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -TesseractCmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Current Windows release assets are built with OCR support when Tesseract is available on the build runner, so there is no separate OCR flag today.

## Direct release download

If you prefer to download the binary manually, use the GitHub Releases page and grab the asset for your platform.

After downloading:

```bash
chmod +x ccal
ccal --help
```

## Notes

- Linux and macOS builds are distributed as standalone executables.
- Windows users can use `install.ps1`, or download the `.exe` asset from GitHub Releases.
- If the installer cannot find a matching asset, check that the release exists and that your platform is supported.
