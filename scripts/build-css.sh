#!/usr/bin/env bash
# Build app/static/tailwind.css with the Tailwind standalone CLI (no Node needed).
# Downloads the pinned binary to .cache/ on first run. Extra args are passed
# through, e.g. `scripts/build-css.sh --watch`.
set -euo pipefail

cd "$(dirname "$0")/.."

TAILWIND_VERSION=3.4.17  # keep in sync with TAILWIND_VERSION in Dockerfile

case "$(uname -s)" in
    Linux)  os=linux ;;
    Darwin) os=macos ;;
    *) echo "unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
case "$(uname -m)" in
    x86_64)        arch=x64 ;;
    arm64|aarch64) arch=arm64 ;;
    *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;;
esac

bin=".cache/tailwindcss-${TAILWIND_VERSION}-${os}-${arch}"
if [ ! -x "$bin" ]; then
    mkdir -p .cache
    echo "downloading tailwindcss v${TAILWIND_VERSION} (${os}-${arch})..." >&2
    curl -fsSL -o "$bin.tmp" \
        "https://github.com/tailwindlabs/tailwindcss/releases/download/v${TAILWIND_VERSION}/tailwindcss-${os}-${arch}"
    chmod +x "$bin.tmp"
    mv "$bin.tmp" "$bin"
fi

exec "$bin" -i tailwind.input.css -o app/static/tailwind.css --minify "$@"
