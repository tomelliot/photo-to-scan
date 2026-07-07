# Build the Tailwind stylesheet with the standalone CLI (no Node toolchain)
FROM python:3.12-slim AS css
ARG TAILWIND_VERSION=3.4.17
# keep in sync with TAILWIND_VERSION in scripts/build-css.sh
RUN python -c "\
import platform, urllib.request, os; \
arch = {'x86_64': 'x64', 'aarch64': 'arm64'}[platform.machine()]; \
url = f'https://github.com/tailwindlabs/tailwindcss/releases/download/v${TAILWIND_VERSION}/tailwindcss-linux-{arch}'; \
urllib.request.urlretrieve(url, '/usr/local/bin/tailwindcss'); \
os.chmod('/usr/local/bin/tailwindcss', 0o755)"
WORKDIR /build
COPY tailwind.config.js tailwind.input.css ./
COPY app/ app/
RUN tailwindcss -i tailwind.input.css -o tailwind.css --minify

FROM python:3.12-slim

# System dependencies for OpenCV and TurboJPEG
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libturbojpeg0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY docprep/ docprep/
COPY app/ app/
COPY --from=css /build/tailwind.css app/static/tailwind.css
RUN uv sync --frozen --no-dev

# Pre-download the DocAligner ONNX model at build time,
# then fix permissions so the app can write cache files
RUN uv run python -c "from docaligner import DocAligner; DocAligner()" \
    && chmod -R a+rw /app/.venv/lib/python3.12/site-packages/docaligner/ \
    && chmod -R a+rw /app/.venv/lib/python3.12/site-packages/capybara/

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
