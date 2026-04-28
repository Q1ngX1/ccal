# ccal Install Guide

`ccal` ships with standalone release binaries and an official shell installer for Linux and macOS.

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

## Direct release download

If you prefer to download the binary manually, use the GitHub Releases page and grab the asset for your platform.

After downloading:

```bash
chmod +x ccal
ccal --help
```

## Notes

- Linux and macOS builds are distributed as standalone executables.
- Windows users should download the `.exe` asset from GitHub Releases.
- If the installer cannot find a matching asset, check that the release exists and that your platform is supported.
