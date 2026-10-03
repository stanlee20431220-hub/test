import json
import os
import uuid

from flask import (Blueprint, Response, current_app, flash, redirect,
                   render_template, request, url_for)

from extensions import db
from models import DetailPage

from .generator import TONES, generate_content, parse_lines, parse_specs
from .renderer import ALLOWED_EXT, THEMES, render_page

bp = Blueprint("wizard", __name__, url_prefix="/wizard")

MAX_IMAGES = 8


def _upload_dir():
    path = os.path.join(current_app.static_folder, "uploads")
    os.makedirs(path, exist_ok=True)
    return path


def _image_url(fname):
    return url_for("static", filename=f"uploads/{fname}")


def _save_images(files):
    saved = []
    for f in files[:MAX_IMAGES]:
        if not f or not f.filename:
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            continue
        name = f"{uuid.uuid4().hex}{ext}"
        f.save(os.path.join(_upload_dir(), name))
        saved.append(name)
    return saved


@bp.route("/")
def index():
    pages = DetailPage.query.order_by(DetailPage.updated_at.desc()).all()
    return render_template("wizard/index.html", pages=pages)


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "GET":
        return render_template("wizard/new.html", tones=TONES, themes=THEMES)

    form = request.form
    name = form.get("name", "").strip()
    if not name:
        flash("상품명은 꼭 입력해주세요.", "error")
        return render_template("wizard/new.html", tones=TONES, themes=THEMES), 400

    product = {
        "name": name,
        "category": form.get("category", "").strip(),
        "price": form.get("price", "").strip(),
        "target": form.get("target", "").strip(),
        "tone": form.get("tone", "friendly"),
        "features": parse_lines(form.get("features")),
        "specs": parse_specs(form.get("specs")),
        "notice": form.get("notice", "").strip(),
    }
    content, how = generate_content(product)

    page = DetailPage(
        title=name,
        theme=form.get("theme", "mint") if form.get("theme") in THEMES else "mint",
        product_json=json.dumps(product, ensure_ascii=False),
        generated_by=how,
    )
    page.content = content
    page.images = _save_images(request.files.getlist("images"))
    db.session.add(page)
    db.session.commit()

    if how == "template":
        flash("AI 키가 없어 기본 템플릿 문구로 만들었어요. 편집 화면에서 자유롭게 고쳐보세요.", "success")
    else:
        flash("AI가 문구를 작성했어요. 편집 화면에서 다듬어보세요.", "success")
    return redirect(url_for("wizard.edit", page_id=page.id))


@bp.route("/<int:page_id>", methods=["GET", "POST"])
def edit(page_id):
    page = DetailPage.query.get_or_404(page_id)

    if request.method == "POST":
        f = request.form
        c = page.content
        c["headline"] = f.get("headline", "").strip()
        c["subheadline"] = f.get("subheadline", "").strip()
        c["pains"] = parse_lines(f.get("pains"))
        c["features"] = [
            {"title": t.strip(), "desc": d.strip()}
            for t, d in zip(f.getlist("feature_title"), f.getlist("feature_desc"))
            if t.strip() or d.strip()
        ]
        c["specs"] = parse_specs(f.get("specs"))
        c["faqs"] = [
            {"q": q.strip(), "a": a.strip()}
            for q, a in zip(f.getlist("faq_q"), f.getlist("faq_a"))
            if q.strip() or a.strip()
        ]
        c["notice"] = f.get("notice", "").strip()
        c["cta"] = f.get("cta", "").strip()
        page.content = c
        if f.get("theme") in THEMES:
            page.theme = f["theme"]

        keep = set(f.getlist("keep_image"))
        page.images = [i for i in page.images if i in keep] + _save_images(
            request.files.getlist("images")
        )
        db.session.commit()
        flash("저장했습니다.", "success")
        return redirect(url_for("wizard.edit", page_id=page.id))

    return render_template(
        "wizard/edit.html",
        page=page,
        c=page.content,
        themes=THEMES,
        image_url=_image_url,
        specs_text="\n".join(f"{s['k']}: {s['v']}" for s in page.content.get("specs", [])),
    )


@bp.route("/<int:page_id>/preview")
def preview(page_id):
    page = DetailPage.query.get_or_404(page_id)
    return render_page(page, _upload_dir(), image_url=_image_url)


@bp.route("/<int:page_id>/export")
def export(page_id):
    page = DetailPage.query.get_or_404(page_id)
    html = render_page(page, _upload_dir(), embed_images=True)
    return Response(
        html,
        mimetype="text/html",
        headers={"Content-Disposition": f"attachment; filename=detail-{page.id}.html"},
    )


@bp.route("/<int:page_id>/delete", methods=["POST"])
def delete(page_id):
    page = DetailPage.query.get_or_404(page_id)
    for fname in page.images:
        try:
            os.remove(os.path.join(_upload_dir(), fname))
        except OSError:
            pass
    db.session.delete(page)
    db.session.commit()
    flash("삭제했습니다.", "success")
    return redirect(url_for("wizard.index"))
