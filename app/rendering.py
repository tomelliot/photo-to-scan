"""Shared HTML rendering helpers."""

from time import time

from app.sessions import PageEntry

_THUMB_CLASS = "page-thumb relative flex-shrink-0 rounded-lg bg-gray-200"

_DELETE_BTN = (
    '<button hx-delete="/pages/{page_id}" hx-target="#page-{page_id}" '
    'hx-swap="delete" '
    'class="delete-btn absolute top-1 right-1 rounded-full w-6 h-6 '
    'flex items-center justify-center z-10">'
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" '
    'viewBox="0 0 16 16">'
    '<path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 '
    '.5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z">'
    '</path>'
    '<path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-'
    '.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.'
    '118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z">'
    '</path></svg></button>'
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

_ROTATE_BTN = (
    '<button hx-post="/pages/{page_id}/rotate" hx-target="#page-{page_id}" '
    'hx-swap="outerHTML" '
    'class="absolute -bottom-3 -right-3 bg-white text-gray-600 rounded-full w-7 h-7 '
    'flex items-center justify-center shadow-md border border-gray-200 hover:bg-gray-50 z-10">'
    '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
    'd="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 '
    '01-15.357-2m15.357 2H15"/></svg></button>'
)

_IMG_CLASS = "w-auto rounded-lg cursor-pointer"
_IMG_STYLE = "max-height: 70vh; max-width: 30vw;"


def render_thumbnail(page: PageEntry) -> str:
    img_type = "processed" if page.processed else "original"
    delete_btn = _DELETE_BTN.format(page_id=page.id)
    rotate_btn = _ROTATE_BTN.format(page_id=page.id)
    return (
        f'<div id="page-{page.id}" class="{_THUMB_CLASS}">'
        f'<img src="/pages/{page.id}/image?type={img_type}&v={int(time())}" '
        f'alt="page" class="{_IMG_CLASS}" style="{_IMG_STYLE}" '
        f'onclick="openLightbox(this.src)">'
        f'{delete_btn}'
        f'{rotate_btn}'
        f"</div>"
    )


def render_thumbnail_processing(page: PageEntry) -> str:
    """Thumbnail with spinner overlay that auto-triggers processing."""
    delete_btn = _DELETE_BTN.format(page_id=page.id)
    rotate_btn = _ROTATE_BTN.format(page_id=page.id)
    return (
        f'<div id="page-{page.id}" class="{_THUMB_CLASS}"'
        f' hx-post="/process/{page.id}" hx-trigger="load"'
        f' hx-target="#page-{page.id}" hx-swap="outerHTML">'
        f'<img src="/pages/{page.id}/image?type=original" '
        f'alt="page" class="{_IMG_CLASS}" style="{_IMG_STYLE}" '
        f'onclick="openLightbox(this.src)">'
        f'{_SPINNER}'
        f'{delete_btn}'
        f'{rotate_btn}'
        f"</div>"
    )
