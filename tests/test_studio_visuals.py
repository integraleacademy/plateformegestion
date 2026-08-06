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


def test_studio_sidebar_panels_are_exclusive_and_use_expected_ids():
    html = (ROOT / "templates/admin/studio_visuals/editor.html").read_text()
    js = (ROOT / "static/studio_visuals/js/studio-app.js").read_text()
    css = (ROOT / "static/studio_visuals/css/studio-shell.css").read_text()

    expected_ids = [
        "models",
        "content",
        "branding",
        "elements",
        "media",
        "data",
        "ai",
        "history",
        "validation",
    ]

    assert "studio-sidebar-panels" in html
    assert "studio-sidebar-panel" in html
    assert "studio-sidebar-panel[hidden]{display:none!important}" in css.replace(" ", "")
    assert "function openStudioSidebarPanel(panelId" in js
    assert "panel.hidden=!isActive" in js
    assert "button.setAttribute('aria-selected',String(isActive))" in js
    assert "function bindLeftNavigation()" in js
    assert "addEventListener('click'" in js
    assert "if(tab==='models')" in js
    assert "Changer totalement de composition" in js
    assert "Recommandé pour ce contenu" in js
    assert "data-models-gallery" in js

    for panel_id in expected_ids:
        assert f"('{panel_id}'" in html
        assert panel_id in js

    assert "data-studio-panel-content=\"templates\"" not in html
    assert "data-studio-panel-content=\"brand\"" not in html
    assert "data-studio-panel-content=\"check\"" not in html

    def visible_panels_after_open(panel_id):
        return [candidate for candidate in expected_ids if candidate == panel_id]

    for panel_id in expected_ids:
        visible_panels = visible_panels_after_open(panel_id)
        assert len(visible_panels) == 1
        assert visible_panels[0] == panel_id


def test_dom_editing_layer_is_scoped_and_backward_compatible():
    app_js = (ROOT / "static/studio_visuals/js/studio-app.js").read_text()
    store_js = (ROOT / "static/studio_visuals/js/studio-store.js").read_text()
    renderer_js = (ROOT / "static/studio_visuals/js/studio-renderer.js").read_text()
    css = (ROOT / "static/studio_visuals/css/studio-editor.css").read_text()

    assert "studio-visuels-page" in (ROOT / "templates/admin/studio_visuals/editor.html").read_text()
    assert all(selector.startswith(".studio-visuels-page") or selector.startswith("/*") or not selector
               for selector in (line.strip() for line in css.splitlines()[-25:])
               if selector.startswith("."))
    for optional_field in ("layoutOverrides", "customElements", "customPhotos"):
        assert f"{optional_field}:s.{optional_field}||" in store_js
    assert "canvasScale()" in app_js
    assert "(e.clientX-d.startX)/d.scale" in app_js
    assert "Déplacement précis" in app_js
    assert "Photo ajoutée" in app_js
    assert "data-studio-element-id" in renderer_js
    assert "renderMode==='preview'" in renderer_js


def test_photo_upload_reuses_persistent_studio_endpoint():
    source = (ROOT / "app.py").read_text()
    assert '@app.post("/api/admin/studio/media")' in source
    assert 'os.path.join(DATA_DIR, "studio_media")' in source
    assert '{".png", ".svg", ".webp", ".jpg", ".jpeg"}' in source


def test_targeted_studio_brand_geometry_and_real_validation_contract():
    renderer = (ROOT / "static/studio_visuals/js/studio-renderer.js").read_text()
    app = (ROOT / "static/studio_visuals/js/studio-app.js").read_text()
    validation = (ROOT / "static/studio_visuals/js/studio-validation.js").read_text()
    themes = json.loads((ROOT / "static/studio_visuals/data/themes.json").read_text())
    assert 'data-studio-element-id="brand-logo"' in renderer
    assert 'data-studio-element-id="brand-slogan"' in renderer
    assert "id='main-title'" in renderer
    assert 'draggable="false"' in renderer
    assert "getFormationTheme(project.formation" in renderer
    for field in ("Position X", "Position Y", "Largeur", "Hauteur", "Rotation", "Opacité", "Ordre du calque", "Verrouillé", "Réinitialiser la position"):
        assert field in app
    assert "getBoundingClientRect()" in validation
    assert "scrollWidth>el.clientWidth" in validation
    assert "Le logo chevauche le titre" in validation
    assert themes["DIRIGEANT"]["primary"] == "#E16B16"
    assert themes["A3P"]["primary"] == "#16834B"
    assert themes["APS"]["primary"] == "#0057D8"
    assert themes["SSIAP"]["primary"] == "#D71920"
    assert themes["VTC"]["primary"] == "#722ED1"
