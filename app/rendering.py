"""Shared HTML rendering helpers."""

from app.sessions import PageEntry

_THUMB_CLASS = "page-thumb relative flex-shrink-0 rounded-lg overflow-hidden bg-gray-200"

_DELETE_BTN = (
    '<button hx-delete="/pages/{page_id}" hx-target="#page-{page_id}" '
    'hx-swap="delete" hx-confirm="Delete this page?" '
    'class="absolute top-1 right-1 bg-red-600 text-white rounded-full w-5 h-5 '
    'text-xs flex items-center justify-center shadow">X</button>'
)

_SPINNER = (
    '<div class="absolute inset-0 flex items-center justify-center '
    'bg-black/40 rounded-lg">'
    '<svg class="animate-spin h-8 w-8 text-white" xmlns="http://www.w3.org/2000/svg" '
    'fill="none" viewBox="0 0 24 24">'
    '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" '
    'stroke-width="4"></circle>'
    '<path class="opacity-75" fill="currentColor" '
    'd="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>'
    '</svg></div>'
)

_IMG_CLASS = "w-auto rounded-lg"
_IMG_STYLE = "max-height: 70vh; max-width: 30vw;"


def render_thumbnail(page: PageEntry) -> str:
    img_type = "processed" if page.processed else "original"
    delete_btn = _DELETE_BTN.format(page_id=page.id)
    return (
        f'<div id="page-{page.id}" class="{_THUMB_CLASS}">'
        f'<img src="/pages/{page.id}/image?type={img_type}" '
        f'alt="page" class="{_IMG_CLASS}" style="{_IMG_STYLE}">'
        f'{delete_btn}'
        f"</div>"
    )


def render_thumbnail_processing(page: PageEntry) -> str:
    """Thumbnail with spinner overlay that auto-triggers processing."""
    delete_btn = _DELETE_BTN.format(page_id=page.id)
    return (
        f'<div id="page-{page.id}" class="{_THUMB_CLASS}"'
        f' hx-post="/process/{page.id}" hx-trigger="load"'
        f' hx-target="#page-{page.id}" hx-swap="outerHTML">'
        f'<img src="/pages/{page.id}/image?type=original" '
        f'alt="page" class="{_IMG_CLASS}" style="{_IMG_STYLE}">'
        f'{_SPINNER}'
        f'{delete_btn}'
        f"</div>"
    )
