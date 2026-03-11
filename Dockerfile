FROM python:3.12-slim

# System dependencies for OpenCV and TurboJPEG
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libturbojpeg0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY docprep/ docprep/
COPY app/ app/
RUN uv sync --frozen --no-dev

# Pre-download the DocAligner ONNX model at build time,
# then fix permissions so the app can write cache files
RUN uv run python -c "from docaligner import DocAligner; DocAligner()" \
    && chmod -R a+rw /app/.venv/lib/python3.12/site-packages/docaligner/ \
    && chmod -R a+rw /app/.venv/lib/python3.12/site-packages/capybara/

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
