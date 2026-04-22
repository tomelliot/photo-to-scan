# Code standards

These are the rules we've paid for. Each one exists because a bug shipped that wouldn't have shipped if we'd been following it. Treat them as defaults — deviate only with a note in the PR explaining why.

---

## 1. Every external system gets a named client module

**Rule.** Any call out to an external HTTP/RPC/file-system-of-record system goes through a single, purpose-named module (e.g. `app/paperless.py` exposing `PaperlessClient`). Construct the transport (`httpx.AsyncClient`) *once*, with `base_url`, `follow_redirects=True`, `timeout`, auth header, and any retry policy. Callers invoke typed methods (`post_document(pdf, tags)`), never raw `httpx` calls.

**Why.** `48483de` was a trailing-slash / no-redirect / short-timeout bug in `app/routes/submit.py`. The fix touched one callsite. If there had been two callers of Paperless, the second would still be broken. A named client makes the configuration invariant across the app.

**Don't**
```python
async with httpx.AsyncClient() as client:
    resp = await client.post(f"{settings.paperless_url}/api/...", ...)
```

**Do**
```python
async with paperless_client() as client:
    await client.post_document(pdf_bytes, tag_ids)
```

---

## 2. Mutating endpoints model state explicitly

**Rule.** Any endpoint with an external, non-idempotent side effect (upload to Paperless, send email, charge a card) models its target as a state machine with an irreversible terminal state. Re-entering the endpoint in that state returns an error, not a retry.

For sessions: `status ∈ {draft, submitting, submitted}`. Transitions are one-way. The status is persisted (disk marker, not just in-memory).

**Why.** `dd29358` fixed duplicate submissions by bolting on three mechanisms (in-memory flag, disk `.submitted` marker, submit guard) after the fact. "What if the user refreshes after submit?" is the first question to ask about any mutating endpoint — not the last.

**Checklist for a new mutating endpoint**
- What's the terminal state?
- Where is it persisted so it survives restart?
- What does a second call in the terminal state return?
- What does a second call while *in flight* return?

---

## 3. Functions have typed, explicit return contracts

**Rule.** Functions that can fail or return "nothing useful" return `Result | None` (or a discriminated union), not a sentinel of the same type. Callers must handle both paths. Don't use broad `try/except Exception` as a substitute for a return contract.

**Why.** `docprep.scan.scan_document` silently returned the *original image* when corners were missing or malformed — indistinguishable from a successful scan. `5f965c5` wrapped the caller in `try/except Exception` and set `page.status = "done"` on failure, meaning errors look like successes to the UI. Both the function's contract and the caller's response to failure were ambiguous.

**Don't**
```python
def scan_document(image):
    if polygon is None:
        return image  # caller can't tell success from failure
```

**Do**
```python
def scan_document(image) -> ScanResult | None:
    if polygon is None:
        return None
```

And in the route, handle `None` explicitly — render a distinct "could not detect document" state, not a silent "done".

---

## 4. HTMX and Alpine: one idiom per attribute, not two

**Rule.** When sending client-side state to the server via HTMX:

- **Prefer hidden form fields** (`<input type="hidden" name="tags" :value="...">`). HTMX serialises them natively; no JS scope involved.
- **If you need JS**, bind through Alpine: `:hx-vals="tagsParam()"`. Alpine evaluates in component scope.
- **Never use `hx-vals="js:..."`** if the referenced symbol lives in an Alpine `x-data`. HTMX's `js:` prefix evaluates in **global** scope; Alpine component properties are not globals.

**Why.** `74fcbd6` — `hx-vals="js:{tags: selectedTags}"` threw `ReferenceError: selectedTags is not defined` on every submit with a tag selected. Six lines below, `@htmx:after-request="... selectedTags = []"` worked fine, because `@` is an Alpine directive evaluated in component scope. Mixing the two idioms in one element is the shape of the bug.

## 5. Alpine state lives in a named data module, not inline `x-data`

**Rule.** Non-trivial Alpine components (more than ~3 properties, or any methods) are defined via `Alpine.data('name', () => ({...}))` in a `.js` file, then referenced with `x-data="name"`. Inline `x-data="{...}"` on `<body>` is reserved for truly tiny ad-hoc state.

**Why.** Inline `x-data` on `<body>` was where `selectedTags` lived. Nothing signals to a reader that it's component-scoped; it *looks* like a global. A named data module:
- makes scope explicit
- gives you IDE completion and lint
- puts helpers (`tagsParam()`) next to the state they close over
- makes the component unit-testable in JS

---

## 6. Every user-facing happy path has a browser test

**Rule.** Each route the user actually drives (upload, process, submit, select tags) has a Playwright test that exercises the real JS. String-presence assertions on rendered HTML don't count.

**Why.** `tests/test_ui.py:60-62` reads:
```python
assert "hx-vals" in resp.text
assert "selectedTags" in resp.text or "tags" in resp.text
```
This test **passed** while the app was broken. It verifies that the template contains the strings the author wrote, not that submitting a document with a tag works. One Playwright test (`upload → select tag → click submit → assert POST body`) would have caught `74fcbd6` and will catch the next bug of that shape.

**Minimum coverage for a new interactive feature**
- A server test for the endpoint (status, shape of response)
- A browser test for the user path that hits it
- Remove any string-in-HTML "smoke tests" that overlap — they give false confidence

---

## 7. Centralised exception handling, not per-route try/except

**Rule.** Errors that should show the user a message go through one FastAPI exception handler that renders the error-modal template. Route code lets exceptions propagate; it doesn't build error HTML inline.

**Why.** `caa1775` (error-modal Jinja template) was the codebase belatedly converging on this. Before it, each route hand-rolled its own `_error_html(...)` call. Once you have N hand-rolled error paths, inconsistency is inevitable.

**Don't**
```python
try:
    result = run_scan(image)
except Exception:
    return _error_html("Scan failed", ...)
```

**Do** — let it raise, and register:
```python
@app.exception_handler(ScanError)
def _(request, exc):
    return render_error_modal(title="Scan failed", detail=str(exc))
```

Only catch exceptions in a route when you're recovering (converting to a domain-specific exception, falling back to a default result), not when you're just re-formatting for the user.

---

## 8. Docker: reproducible from a clean clone, pinned on day one

**Rule.** `docker compose up --build` from a fresh clone must produce a working image. Native dependencies (`libturbojpeg0`, etc.), Python sub-dependency pins (`PyTurboJPEG<2.0`), and pre-downloaded model artefacts (ONNX weights) are declared in the `Dockerfile` from the first commit that needs them, not retrofitted.

**Why.** `ec850b9` was six separate fixes rolled into one commit — libturbojpeg, PyTurboJPEG pin, ONNX pre-download, capybara/docaligner permissions. Every one was foreseeable from "does a fresh `docker compose up` scan an image?"

**Checklist when adding a dependency**
- Does it need a native `apt` package? Add to `Dockerfile`.
- Does it pull sub-deps that need pinning? Add to `pyproject.toml` / `uv overrides`.
- Does it download model weights at first use? Pre-fetch at build time.
- Does it write to its own install directory? Fix perms at build time.

---

## 9. Config reads happen at boundaries, not inside business logic

**Rule.** `get_settings()` is called in the composition layer (client factories, route dependencies) and passed down. Business-logic modules receive already-resolved config as arguments.

**Why.** `get_settings()` sprinkled through the code couples every module to the settings schema and makes unit tests harder. Related to standard 1 (named clients): the client factory reads settings once and hands back a configured transport.

---

## 10. Commit messages explain *why*, not just *what*

**Rule.** A bug-fix commit describes the symptom, the root cause, and the reason the fix is correct. One-liners like "fix: Add error handling for scan failures and corner validation" don't help the next person ask "is this still needed?"

**Good example** (from this repo, `74fcbd6`):
> `hx-vals="js:..."` is evaluated by HTMX in global scope, where `selectedTags` — an Alpine component property on `<body>` — is not in scope, so submitting with a tag selected threw `"ReferenceError: selectedTags is not defined"`. Switch to `:hx-vals="tagsParam()"` so Alpine evaluates the attribute in component scope using the existing helper.

**Bad example** (from this repo, `5f965c5`):
> `fix: Add error handling for scan failures and corner validation`

The bad one tells you nothing about what was failing, under what conditions, or why this is the right fix.

---

## The meta-rule

**Bugs live at integration seams.** Every non-algorithm fix in this repo's history has been at a boundary: HTMX↔Alpine, FastAPI↔httpx↔Paperless, in-memory↔disk, Python↔ONNX-in-image. Code inside one layer is rarely the problem; the contract *between* layers is. When reviewing a PR, spend your attention on the seams, not the interiors.
