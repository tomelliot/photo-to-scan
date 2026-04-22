"""Domain exceptions that render as the error modal.

Routes raise these instead of building error HTML inline. The central
handler registered in `app.main` turns any `AppError` into an
`error_modal.html` response. See STANDARDS.md rule 7.
"""

from __future__ import annotations


class AppError(Exception):
    """User-facing error rendered as an HTML modal.

    Subclasses set `title` and `detail` (class attributes or via __init__).
    """

    title: str = "Error"
    detail: str = "Something went wrong."


class NoPagesError(AppError):
    title = "No pages"
    detail = "Add at least one page before submitting."


class AlreadySubmittingError(AppError):
    title = "Submission in progress"
    detail = (
        "A previous submission for this document is still being sent to "
        "Paperless-ngx. Please wait a moment."
    )


class AlreadySubmittedError(AppError):
    title = "Already submitted"
    detail = "This document has already been sent to Paperless-ngx."


class PaperlessNotConfiguredError(AppError):
    title = "Not configured"
    detail = (
        "Paperless-ngx URL and API token are not set. "
        "Configure PAPERLESS_URL and PAPERLESS_TOKEN environment variables."
    )


class PaperlessRejectedError(AppError):
    title = "Upload failed"

    def __init__(self, status_code: int):
        super().__init__(f"Paperless rejected upload: HTTP {status_code}")
        self.detail = (
            f"Paperless-ngx returned status {status_code}. "
            "Check that the URL and token are correct."
        )


class PaperlessUnreachableError(AppError):
    title = "Connection error"

    def __init__(self, url: str, kind: str):
        super().__init__(f"Could not reach {url}: {kind}")
        self.detail = (
            f"Could not reach Paperless-ngx at {url}. Details: {kind}"
        )
