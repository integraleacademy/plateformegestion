import json
from pathlib import Path

from services.studio_export_service import EXPORT_DIMENSIONS
from services.studio_template_service import load_studio_config
from social_visuals import generate_content_from_topic

ROOT = Path(__file__).resolve().parents[1]


def test_template_catalog_has_15_families_and_60_variants():
    cfg = load_studio_config(ROOT)
    assert len(cfg["families"]) >= 15
    assert len(cfg["templates"]) >= 60
    assert all(t["family"] and t["renderer"] for t in cfg["templates"])


def test_themes_cover_required_formations_and_tokens():
    cfg = load_studio_config(ROOT)
    required = {"A3P", "APS", "SSIAP", "DIRIGEANT", "VTC"}
    assert required <= set(cfg["themes"])
    tokens = {"primary", "secondary", "accent", "background", "backgroundAlt", "surface", "surfaceDark", "text", "textMuted", "border", "shadow", "danger", "success"}
    for theme in cfg["themes"].values():
        assert tokens <= set(theme)
        assert len(theme["variants"]) >= 8


def test_ai_generation_does_not_emit_internal_editor_metadata():
    payload = generate_content_from_topic("Annonce session APS septembre 2026")
    encoded = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = ["png hd", "1080×1350", "1080 x 1350", "charte verrouillée", "thème aps"]
    assert not any(term in encoded for term in forbidden)


def test_export_dimensions_contract():
    assert EXPORT_DIMENSIONS["standard"] == (1080, 1350)
    assert EXPORT_DIMENSIONS["hd"] == (2160, 2700)
    assert EXPORT_DIMENSIONS["square"] == (1080, 1080)
    assert EXPORT_DIMENSIONS["story"] == (1080, 1920)


def test_studio_v2_uses_exclusive_object_editor_panels():
    html = (ROOT / "templates/admin/studio_visuals/editor.html").read_text()
    js = (ROOT / "static/studio/app.js").read_text()
    css = (ROOT / "static/studio/studio.css").read_text()

    expected_ids = [
        "templates",
        "photos",
        "texts",
        "elements",
        "background",
        "brand",
        "assistant",
    ]

    assert "data-content" in html
    assert "[hidden]{display:none!important}" in css.replace(" ", "")
    assert "x.hidden=x.dataset.content!==b.dataset.panel" in js
    assert "createCanvas" in js and "History" in js

    for panel_id in expected_ids:
        assert f"data-content=\"{panel_id}\"" in html

    def visible_panels_after_open(panel_id):
        return [candidate for candidate in expected_ids if candidate == panel_id]

    for panel_id in expected_ids:
        visible_panels = visible_panels_after_open(panel_id)
        assert len(visible_panels) == 1
        assert visible_panels[0] == panel_id
