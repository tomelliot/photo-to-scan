"""Browser-level tests that exercise the real JS.

These tests catch the class of bug where an HTMX/Alpine interaction silently
breaks — e.g. a `hx-vals="js:{tags: selectedTags}"` ReferenceError when the
symbol lives in Alpine's component scope. String-match tests on rendered HTML
cannot catch that.

Run requires Chromium: `uv run playwright install chromium`.
"""

from __future__ import annotations

import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from playwright.sync_api import Page, expect


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http(url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    return
        except Exception as exc:
            last_exc = exc
            time.sleep(0.1)
    raise RuntimeError(f"timed out waiting for {url}: {last_exc!r}")


def _ensure_tailwind_css() -> None:
    """Build app/static/tailwind.css if missing (gitignored, built artifact).

    Tailwind's `hidden` class drives real behaviour (e.g. the lightbox), so
    browser tests need the stylesheet present.
    """
    root = pathlib.Path(__file__).parent.parent
    if not (root / "app" / "static" / "tailwind.css").exists():
        subprocess.run([str(root / "scripts" / "build-css.sh")], check=True)


@pytest.fixture(scope="module")
def live_server(tmp_path_factory) -> str:
    """Spawn the real app on a free port. Yields the base URL.

    Paperless is deliberately left unconfigured. These tests assert client-side
    behaviour (no JS errors, correct request payloads); they do not rely on a
    successful server→Paperless round-trip.
    """
    _ensure_tailwind_css()
    port = _free_port()
    work_dir = tmp_path_factory.mktemp("sessions")
    env = {
        **os.environ,
        "WORK_DIR": str(work_dir),
    }
    env.pop("PAPERLESS_URL", None)
    env.pop("PAPERLESS_TOKEN", None)

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port),
            "--log-level", "warning",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_http(base_url + "/health")
    except Exception:
        proc.terminate()
        proc.wait(timeout=5)
        raise

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def test_submit_with_tag_does_not_throw_js_error(page: Page, live_server: str) -> None:
    """Regression for the `selectedTags is not defined` ReferenceError (74fcbd6).

    With a non-empty `selectedTags`, clicking submit must evaluate the
    `:hx-vals` binding cleanly in Alpine scope, emit a POST, and raise no
    uncaught JS error. Before the fix, HTMX evaluated `hx-vals="js:..."` in
    global scope where `selectedTags` wasn't defined, throwing during the click.
    """
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(live_server + "/")

    # Wait until Alpine has wired up the <body> component.
    page.wait_for_function(
        "() => window.Alpine && window.Alpine.$data(document.body) !== undefined"
    )

    # Simulate "the user selected a tag" by setting component state directly.
    # We don't drive the label popover here — the bug we're guarding against
    # fires at hx-vals evaluation time, not at popover-click time.
    page.evaluate("Alpine.$data(document.body).selectedTags = [42]")

    # Click submit and capture the outbound request. The server may reject
    # with a "Not configured" / "No pages" modal — that's orthogonal. The
    # only things we assert are: no JS error, and the request body carried
    # the tag (proving `:hx-vals` actually evaluated to the Alpine value).
    try:
        with page.expect_request("**/submit", timeout=3000) as req_info:
            page.click("#submit-btn")
        body = req_info.value.post_data or ""
    except Exception as exc:
        # If the request never fired, the JS errors (if any) tell us why.
        if errors:
            pytest.fail(f"submit request never sent; uncaught JS errors: {errors}")
        raise AssertionError(f"submit request never sent and no JS errors captured: {exc}")

    assert errors == [], f"uncaught JS errors during submit: {errors}"
    assert "tags=42" in body, f"expected tags=42 in POST body, got: {body!r}"


def test_label_popover_preserves_server_tag_order(page: Page, live_server: str) -> None:
    """The picker must render /tags in the order the server sent it.

    The server sorts tags by document count descending. Nothing client-side
    may re-sort or reverse that — `filteredTags()` passes the array through
    and Alpine's keyed `x-for` follows source order. `live_server` has no
    Paperless, so stub /tags with an order that is neither alphabetical nor
    by id: any accidental client-side sort would produce a different order.
    """
    page.route(
        "**/tags",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps([
                {"id": 7, "name": "Receipt"},    # most used
                {"id": 2, "name": "Aardvark"},
                {"id": 9, "name": "Invoice"},
                {"id": 4, "name": "Zebra"},      # least used
            ]),
        ),
    )

    page.goto(live_server + "/")

    # The button is disabled until /tags resolves; clicking it proves the fetch
    # landed as well as opening the popover.
    button = page.locator("#label-selector-btn")
    expect(button).to_be_enabled()
    button.click()

    def rendered_names() -> list[str]:
        # Each item wraps a checkmark SVG next to the name, so the element's
        # text carries surrounding whitespace.
        return [t.strip() for t in page.locator(".label-popover__item").all_text_contents()]

    expect(page.locator(".label-popover__item")).to_have_count(4)
    assert rendered_names() == ["Receipt", "Aardvark", "Invoice", "Zebra"]

    # Filtering must not reorder the survivors either.
    page.fill("#label-search", "e")
    assert rendered_names() == ["Receipt", "Invoice", "Zebra"]


def test_page_loads_without_js_errors(page: Page, live_server: str) -> None:
    """The index page must initialise cleanly — no uncaught JS on load."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(live_server + "/")

    # Submit button is always present; use it as a "page ready" signal.
    expect(page.locator("#submit-btn")).to_be_visible()

    # Give Alpine a tick to initialise and /tags to resolve (or fail) so any
    # deferred errors surface before we assert.
    page.wait_for_load_state("networkidle")

    assert errors == [], f"uncaught JS errors on page load: {errors}"
