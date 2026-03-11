# Implementation Plan: Paperless App (FastAPI + HTMX + Alpine.js)

A mobile-first web app for processing document photos and uploading them to
Paperless-ngx as multi-page documents.

**Stack:** FastAPI, HTMX, Alpine.js, Tailwind CSS, Pillow (PDF assembly), pytest

**Commit policy:** Commit after each step passes its verification tests.
Use clear commit messages referencing the step number (e.g. `step-03: add /process endpoint`).

---

## Step 0: Project scaffold and test infrastructure

Create the app package structure, install dependencies, and wire up pytest.

```
photo-to-scan/
├── docprep/              # existing — unchanged
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app factory
│   ├── config.py         # Settings (pydantic-settings)
│   ├── routes/
│   │   ├── __init__.py
│   │   └── pages.py      # serves the HTML shell
│   ├── templates/
│   │   └── index.html    # single-page HTMX app
│   └── static/           # CSS overrides if needed
├── tests/
│   ├── conftest.py       # shared fixtures (TestClient, tmp dirs, sample images)
│   ├── test_health.py
│   └── ...
├── Dockerfile
├── pyproject.toml        # updated with new deps
```

### New dependencies
- `fastapi`, `uvicorn[standard]` — web server
- `python-multipart` — file uploads
- `jinja2` — templates
- `pillow` — PDF assembly
- `httpx` — paperless API client + test client
- `pytest`, `pytest-asyncio` — tests

### Verification

```
TEST: test_health.py::test_health_returns_ok
  GET /health → 200, body contains {"status": "ok"}

TEST: test_health.py::test_app_has_no_startup_errors
  TestClient(app) does not raise
```

**Commit: `step-00: project scaffold with health endpoint and test infra`**

---

## Step 1: Serve the HTML shell

`GET /` returns a Jinja2-rendered HTML page. It includes HTMX, Alpine.js,
and Tailwind via CDN. No interactive behaviour yet — just the static skeleton.

### Verification

```
TEST: test_pages.py::test_index_returns_html
  GET / → 200, content-type contains "text/html"

TEST: test_pages.py::test_index_includes_htmx
  response body contains "htmx.org"

TEST: test_pages.py::test_index_includes_alpine
  response body contains "alpinejs"
```

**Commit: `step-01: serve HTML shell with HTMX/Alpine/Tailwind`**

---

## Step 2: Image upload endpoint (no processing)

`POST /upload` accepts a multipart image file, saves it to a session
working directory (UUID-named), and returns an HTMX partial showing the
thumbnail.

Session state is stored in-memory (dict keyed by session ID cookie).
Each session holds an ordered list of page entries:
`{id: str, original: Path, processed: Path | None, status: "pending"|"done"|"error"}`.

### Verification

```
TEST: test_upload.py::test_upload_accepts_jpeg
  POST /upload with a valid JPEG → 200
  response body contains <img> tag

TEST: test_upload.py::test_upload_rejects_non_image
  POST /upload with a .txt file → 422

TEST: test_upload.py::test_upload_creates_session
  POST /upload → response sets a session cookie

TEST: test_upload.py::test_upload_stores_file_on_disk
  POST /upload → file exists in the session working directory
```

**Commit: `step-02: image upload endpoint with session management`**

---

## Step 3: Image processing endpoint

`POST /process/{page_id}` runs the existing `scan_document()` pipeline on
the uploaded original and stores the result. Returns an HTMX partial that
swaps the thumbnail to show the processed image.

The processing import is wrapped so tests can mock it (avoiding the heavy
ONNX model load in CI).

### Verification

```
TEST: test_process.py::test_process_returns_processed_image
  upload an image, then POST /process/{page_id}
  → 200, response contains updated <img> tag
  (scan_document is mocked to return a known transformed image)

TEST: test_process.py::test_process_unknown_page_returns_404
  POST /process/nonexistent → 404

TEST: test_process.py::test_process_updates_session_state
  after processing, session page entry has status "done"
  and processed path exists on disk
```

**Commit: `step-03: image processing endpoint wired to scan_document`**

---

## Step 4: Auto-process on upload

Combine steps 2 and 3: `POST /upload` saves the file *and* immediately
processes it, returning the final thumbnail in one round-trip. The upload
endpoint calls `scan_document` synchronously (it's ~1-2s per image, acceptable
for the use case; async offloading can come later if needed).

### Verification

```
TEST: test_upload.py::test_upload_auto_processes
  POST /upload → response contains processed thumbnail
  session page status is "done"
  (scan_document mocked)

TEST: test_upload.py::test_upload_shows_original_on_process_failure
  mock scan_document to raise → response still 200
  page status is "error", thumbnail shows original image
```

**Commit: `step-04: auto-process on upload`**

---

## Step 5: Serve page images

`GET /pages/{page_id}/image?type=original|processed` serves the stored
image file. Used by `<img>` tags in the HTMX partials.

### Verification

```
TEST: test_images.py::test_get_original_image
  upload a file → GET /pages/{id}/image?type=original → 200
  content-type is image/jpeg

TEST: test_images.py::test_get_processed_image
  upload + process → GET /pages/{id}/image?type=processed → 200

TEST: test_images.py::test_get_unknown_page_returns_404
  GET /pages/nonexistent/image → 404

TEST: test_images.py::test_get_image_wrong_session_returns_404
  upload on session A → request from session B → 404
```

**Commit: `step-05: serve page images`**

---

## Step 6: Page list management (reorder + delete)

`DELETE /pages/{page_id}` removes a page from the session and deletes
its files.

`PUT /pages/reorder` accepts a JSON body `{"order": ["id1", "id2", ...]}`
and reorders the session's page list.

Both return an HTMX partial of the updated page list.

### Verification

```
TEST: test_pages_mgmt.py::test_delete_page
  upload 2 images → DELETE /pages/{first_id} → 200
  session has 1 page, deleted files are gone from disk

TEST: test_pages_mgmt.py::test_delete_unknown_page_returns_404
  DELETE /pages/nonexistent → 404

TEST: test_pages_mgmt.py::test_reorder_pages
  upload 3 images (A, B, C) → PUT /pages/reorder with [C, A, B]
  session page order is [C, A, B]

TEST: test_pages_mgmt.py::test_reorder_with_invalid_ids_returns_422
  PUT /pages/reorder with unknown IDs → 422
```

**Commit: `step-06: page delete and reorder endpoints`**

---

## Step 7: PDF assembly

`POST /assemble` takes the current session's processed images (in order),
combines them into a single PDF using Pillow, and returns the PDF file as
a download.

### Verification

```
TEST: test_assemble.py::test_assemble_single_page_pdf
  upload + process 1 image → POST /assemble → 200
  content-type is application/pdf
  PDF is valid (can be opened with Pillow)

TEST: test_assemble.py::test_assemble_multi_page_pdf
  upload + process 3 images → POST /assemble → 200
  PDF has 3 pages (verify with Pillow or pypdf page count)

TEST: test_assemble.py::test_assemble_empty_session_returns_422
  POST /assemble with no pages → 422

TEST: test_assemble.py::test_assemble_uses_session_order
  upload A, B, C → reorder to C, A, B → assemble
  PDF page order matches C, A, B
```

**Commit: `step-07: multi-page PDF assembly`**

---

## Step 8: Paperless-ngx upload

`POST /submit` assembles the PDF (reusing step 7 logic) and uploads it
to the Paperless-ngx API (`POST /api/documents/post_document/`).

Config: `PAPERLESS_URL` and `PAPERLESS_TOKEN` from environment variables.

After successful upload, the session is cleared.

### Verification

```
TEST: test_submit.py::test_submit_calls_paperless_api
  mock httpx.post to paperless URL
  upload + process image → POST /submit → 200
  assert the mock was called with correct URL, auth header, and PDF payload

TEST: test_submit.py::test_submit_clears_session
  after successful submit, session page list is empty

TEST: test_submit.py::test_submit_without_paperless_config_returns_503
  unset PAPERLESS_URL → POST /submit → 503

TEST: test_submit.py::test_submit_paperless_error_returns_502
  mock paperless to return 500 → POST /submit → 502
  session is NOT cleared (pages preserved for retry)
```

**Commit: `step-08: paperless-ngx API upload`**

---

## Step 9: Mobile-first UI

Build out the full interactive UI in `index.html`:

- Camera capture button (`<input type="file" accept="image/*" capture="environment">`)
- Page thumbnail grid with drag-to-reorder (SortableJS + Alpine.js)
- Delete button per page (with confirmation)
- "Submit to Paperless" button
- Loading spinners during upload/processing
- Responsive layout (Tailwind: single column on mobile, grid on desktop)

All interactivity via HTMX attributes (hx-post, hx-swap, hx-target)
and Alpine.js for local UI state (modals, drag state).

### Verification

```
TEST: test_ui.py::test_index_has_capture_input
  GET / → body contains 'capture="environment"'

TEST: test_ui.py::test_index_has_submit_button
  GET / → body contains 'Submit' or 'submit'

TEST: test_ui.py::test_index_has_sortable
  GET / → body contains 'Sortable' or 'sortablejs'

TEST: test_ui.py::test_full_flow_integration
  upload 2 images → verify page list partial has 2 thumbnails
  delete 1 → verify page list has 1 thumbnail
  submit → verify paperless API called (mocked)
```

**Commit: `step-09: mobile-first UI with camera capture and drag reorder`**

---

## Step 10: Dockerfile and docker-compose

```dockerfile
FROM python:3.12-slim
# install system deps (libgl1 for OpenCV)
# copy project, install with uv
# expose 8000, run uvicorn
```

`docker-compose.yml` with a single service and env vars for paperless config.

### Verification

```
TEST: (bash) docker build succeeds
  docker build -t docprep-app . → exit code 0

TEST: (bash) container starts and health check passes
  docker run -d -p 8000:8000 docprep-app
  curl http://localhost:8000/health → {"status": "ok"}
```

**Commit: `step-10: Dockerfile and docker-compose`**

---

## Step 11: Session cleanup

Add a background task that removes session working directories older than
a configurable TTL (default: 1 hour). Runs on a periodic interval using
FastAPI's lifespan.

### Verification

```
TEST: test_cleanup.py::test_expired_sessions_are_removed
  create a session with mocked timestamps in the past
  trigger cleanup → session directory is deleted

TEST: test_cleanup.py::test_active_sessions_are_preserved
  create a session with recent timestamp
  trigger cleanup → session directory still exists
```

**Commit: `step-11: session TTL cleanup`**

---

## Summary of test files

| Test file               | Step | What it covers                  |
|-------------------------|------|---------------------------------|
| test_health.py          | 0    | App starts, health endpoint     |
| test_pages.py           | 1    | HTML shell served correctly     |
| test_upload.py          | 2, 4 | File upload, auto-processing    |
| test_process.py         | 3    | Processing endpoint             |
| test_images.py          | 5    | Serving stored images           |
| test_pages_mgmt.py      | 6    | Delete, reorder                 |
| test_assemble.py        | 7    | PDF assembly                    |
| test_submit.py          | 8    | Paperless API upload            |
| test_ui.py              | 9    | UI elements and integration     |
| test_cleanup.py         | 11   | Session expiry                  |

## Running tests

```bash
uv run pytest tests/ -v
```

All processing-heavy tests mock `scan_document` to avoid loading the ONNX
model. Integration tests with the real model are out of scope for CI but
can be run locally with `uv run pytest tests/ -v -m integration`.
