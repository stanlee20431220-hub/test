"""콘텐츠(dict) + 이미지 -> 독립 실행형 상세페이지 HTML."""
import base64
import mimetypes
import os

from flask import render_template

THEMES = {
    "mint": {"label": "민트", "accent": "#12b886", "bg": "#f1fbf7"},
    "navy": {"label": "네이비", "accent": "#2b4c8c", "bg": "#f0f4fb"},
    "coral": {"label": "코랄", "accent": "#f0614f", "bg": "#fff3f1"},
    "mono": {"label": "모노", "accent": "#222222", "bg": "#f4f4f4"},
}

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def to_data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as fh:
        return f"data:{mime};base64,{base64.b64encode(fh.read()).decode()}"


def render_page(page, upload_dir, embed_images=False, image_url=None):
    """embed_images=True 면 이미지를 base64 로 내장(다운로드용)."""
    images = []
    for fname in page.images:
        if embed_images:
            path = os.path.join(upload_dir, fname)
            if os.path.exists(path):
                images.append(to_data_uri(path))
        else:
            images.append(image_url(fname))
    theme = THEMES.get(page.theme, THEMES["mint"])
    return render_template(
        "wizard/render.html",
        c=page.content,
        p=page.product,
        images=images,
        theme=theme,
    )
