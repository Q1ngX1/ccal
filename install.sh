#!/usr/bin/env sh
set -eu

REPO="${CCAL_REPO:-Q1ngX1/ccal}"
VERSION="${CCAL_VERSION:-latest}"
INSTALL_DIR="${CCAL_INSTALL_DIR:-}"
BIN_NAME="${CCAL_BIN_NAME:-ccal}"
API_ROOT="https://api.github.com/repos/${REPO}/releases"

usage() {
  cat <<'EOF'
Usage: install.sh [options]

Install the latest ccal release binary for the current platform.

Options:
  --repo OWNER/REPO     GitHub repository to install from (default: Q1ngX1/ccal)
  --version TAG         Release tag to install, such as v0.1.12 (default: latest)
  --prefix DIR          Installation directory
  --bindir DIR          Alias for --prefix
  -h, --help            Show this help message

Environment variables:
  CCAL_REPO
  CCAL_VERSION
  CCAL_INSTALL_DIR
  CCAL_BIN_NAME
  CCAL_GITHUB_TOKEN

Examples:
  curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh
  curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh -s -- --version v0.1.12
  curl -fsSL https://raw.githubusercontent.com/Q1ngX1/ccal/main/install.sh | sh -s -- --prefix "$HOME/.local/bin"
EOF
}

die() {
  printf '%s\n' "install.sh: $*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

fetch() {
  url="$1"
  if have curl; then
    set -- curl -fsSL -H "Accept: application/vnd.github+json"
    if [ -n "${CCAL_GITHUB_TOKEN:-}" ]; then
      set -- "$@" -H "Authorization: Bearer ${CCAL_GITHUB_TOKEN}"
    fi
    "$@" "$url"
    return 0
  fi

  if have wget; then
    if [ -n "${CCAL_GITHUB_TOKEN:-}" ]; then
      wget -qO- --header='Accept: application/vnd.github+json' --header="Authorization: Bearer ${CCAL_GITHUB_TOKEN}" "$url"
    else
      wget -qO- --header='Accept: application/vnd.github+json' "$url"
    fi
    return 0
  fi

  die "curl or wget is required"
}

download() {
  url="$1"
  dest="$2"

  if have curl; then
    curl -fsSL -o "$dest" "$url"
    return 0
  fi

  if have wget; then
    wget -qO "$dest" "$url"
    return 0
  fi

  die "curl or wget is required"
}

normalize_tag() {
  case "$1" in
    latest) printf '%s' "latest" ;;
    v*) printf '%s' "$1" ;;
    *) printf 'v%s' "$1" ;;
  esac
}

normalize_os() {
  os_name="$(uname -s 2>/dev/null || echo unknown)"
  case "$os_name" in
    Linux*) printf '%s' "linux" ;;
    Darwin*) printf '%s' "macos" ;;
    MINGW*|MSYS*|CYGWIN*)
      die "install.sh supports Linux and macOS only (detected: ${os_name}); on Windows download the .exe release asset instead"
      ;;
    *) die "install.sh supports Linux and macOS only (detected: ${os_name})" ;;
  esac
}

normalize_arch() {
  arch_name="$(uname -m 2>/dev/null || echo unknown)"
  case "$arch_name" in
    x86_64|amd64) printf '%s' "x86_64" ;;
    arm64|aarch64) printf '%s' "arm64" ;;
    *) die "unsupported architecture: ${arch_name}" ;;
  esac
}

release_json() {
  tag="$1"
  if [ "$tag" = "latest" ]; then
    fetch "${API_ROOT}/latest"
  else
    fetch "${API_ROOT}/tags/${tag}"
  fi
}

asset_entries() {
  printf '%s' "$1" \
    | tr -d '\n' \
    | sed 's/},[[:space:]]*{/}\n{/g' \
    | sed -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*"browser_download_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1|\2/p'
}

find_asset_url() {
  entries="$1"
  shift

  for candidate in "$@"; do
    url=$(printf '%s\n' "$entries" | awk -F'|' -v name="$candidate" '$1 == name { print $2; exit }')
    if [ -n "$url" ]; then
      printf '%s' "$url"
      return 0
    fi
  done

  return 1
}

platform_candidates() {
  tag="$1"
  os="$2"
  arch="$3"

  case "${os}:${arch}" in
    linux:x86_64)
      cat <<EOF
ccal-${tag}-linux-x86_64
ccal-linux-x86_64
ccal-${tag}-linux-x64
ccal-linux-x64
ccal-${tag}-linux
ccal-linux
EOF
      ;;
    linux:arm64)
      cat <<EOF
ccal-${tag}-linux-arm64
ccal-linux-arm64
ccal-${tag}-linux-aarch64
ccal-linux-aarch64
ccal-${tag}-linux
ccal-linux
EOF
      ;;
    macos:x86_64)
      cat <<EOF
ccal-${tag}-macos-x86_64
ccal-macos-x86_64
ccal-${tag}-macos-x64
ccal-macos-x64
ccal-${tag}-macos
ccal-macos
EOF
      ;;
    macos:arm64)
      cat <<EOF
ccal-${tag}-macos-arm64
ccal-macos-arm64
ccal-${tag}-macos-aarch64
ccal-macos-aarch64
ccal-${tag}-macos
ccal-macos
EOF
      ;;
    *)
      die "unsupported platform combination: ${os}/${arch}"
      ;;
  esac
}

checksum_candidates() {
  asset_name="$1"
  cat <<EOF
${asset_name}.sha256
${asset_name}.sha256sum
EOF
}

verify_checksum() {
  binary="$1"
  checksum_file="$2"

  expected=$(awk 'NF >= 1 { print $1; exit }' "$checksum_file")
  [ -n "$expected" ] || die "checksum file is empty: $checksum_file"

  actual=""
  if have sha256sum; then
    actual=$(sha256sum "$binary" | awk '{ print $1 }')
  elif have shasum; then
    actual=$(shasum -a 256 "$binary" | awk '{ print $1 }')
  fi

  [ -n "$actual" ] || die "sha256 verification tool not found (need sha256sum or shasum)"
  [ "$expected" = "$actual" ] || die "checksum mismatch for $binary"
}

select_install_dir() {
  if [ -n "$INSTALL_DIR" ]; then
    printf '%s' "$INSTALL_DIR"
    return 0
  fi

  if [ "$(id -u 2>/dev/null || echo 1)" = "0" ]; then
    printf '%s' "/usr/local/bin"
    return 0
  fi

  if [ -w "/usr/local/bin" ]; then
    printf '%s' "/usr/local/bin"
    return 0
  fi

  printf '%s' "${HOME}/.local/bin"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || die "--repo requires a value"
      REPO="$2"
      API_ROOT="https://api.github.com/repos/${REPO}/releases"
      shift 2
      ;;
    --version)
      [ "$#" -ge 2 ] || die "--version requires a value"
      VERSION="$2"
      shift 2
      ;;
    --prefix|--bindir)
      [ "$#" -ge 2 ] || die "$1 requires a value"
      INSTALL_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

tag="$(normalize_tag "$VERSION")"
os="$(normalize_os)"
arch="$(normalize_arch)"

json="$(release_json "$tag")"
entries="$(asset_entries "$json")"

release_tag="$tag"
if [ "$tag" = "latest" ]; then
  release_tag="$(printf '%s' "$json" | tr -d '\n' | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  [ -n "$release_tag" ] || die "could not determine latest release tag"
fi

candidate_list="$(platform_candidates "$release_tag" "$os" "$arch")"
asset_url=""
asset_name=""

for candidate in $candidate_list; do
  asset_url="$(find_asset_url "$entries" "$candidate")" && {
    asset_name="$candidate"
    break
  }
done

[ -n "$asset_url" ] || die "could not find a release asset for ${os}/${arch}"

checksum_url=""
for checksum_name in $(checksum_candidates "$asset_name"); do
  checksum_url="$(find_asset_url "$entries" "$checksum_name")" && break
done

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT INT TERM HUP

binary_tmp="${tmpdir}/ccal"
checksum_tmp="${tmpdir}/ccal.sha256"

download "$asset_url" "$binary_tmp"
chmod +x "$binary_tmp"

if [ -n "$checksum_url" ]; then
  download "$checksum_url" "$checksum_tmp"
  verify_checksum "$binary_tmp" "$checksum_tmp"
fi

target_dir="$(select_install_dir)"
mkdir -p "$target_dir"
target_path="${target_dir}/${BIN_NAME}"

if [ -e "$target_path" ] && [ ! -w "$target_path" ]; then
  if [ "$(id -u 2>/dev/null || echo 1)" != "0" ] && [ "$target_dir" = "/usr/local/bin" ]; then
    die "cannot write to $target_path; rerun with sudo or choose another directory"
  fi
fi

install -m 755 "$binary_tmp" "$target_path"

printf '%s\n' "Installed ccal to $target_path"
if ! printf '%s' "$PATH" | tr ':' '\n' | grep -qx "$target_dir"; then
  printf '%s\n' "Note: $target_dir is not currently in PATH."
  printf '%s\n' "Add it to your shell profile or move ccal into a directory that is already in PATH."
fi

if [ "${CCAL_VERIFY_INSTALL:-0}" = "1" ]; then
  if output=$("$target_path" --version 2>/dev/null); then
    printf '%s\n' "Verified: $(printf '%s\n' "$output" | head -n 1)"
  else
    printf '%s\n' "Warning: installed binary could not be executed for verification."
  fi
fi
