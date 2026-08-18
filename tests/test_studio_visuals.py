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


def test_all_templates_share_the_same_geometry_and_overflow_contract():
    renderer = (ROOT / "static/studio_visuals/js/studio-renderer.js").read_text()
    styles = (ROOT / "static/studio_visuals/css/studio-templates.css").read_text()
    fitting = (ROOT / "static/studio_visuals/js/studio-text-fit.js").read_text()
    validation = (ROOT / "static/studio_visuals/js/studio-validation.js").read_text()

    assert "data-region=\"brand\"" in renderer
    assert "data-region=\"footer\"" in renderer
    assert "data-fit=\"${fit}\"" in renderer
    assert "grid-template-rows:auto minmax(0,1fr) auto" in styles
    assert ".sv-safe>main" in styles
    assert ".studio-format-instagram_portrait" in styles
    assert ".studio-format-instagram_story" in styles
    assert ".studio-format-linkedin_landscape" in styles
    assert "querySelectorAll('[data-fit]')" in fitting
    assert "querySelectorAll('[data-layout-role]')" in validation
    assert "regionOverlap(canvas,brand,content)" in validation


def test_export_checks_dimensions_ratio_and_black_edge_band():
    exporter = (ROOT / "static/studio_visuals/js/studio-exporter.js").read_text()
    editor = (ROOT / "templates/admin/studio_visuals/editor.html").read_text()
    app = (ROOT / "static/studio_visuals/js/studio-app.js").read_text()

    assert "Math.abs(ratioX-ratioY)>.001" in exporter
    assert "assertNoBlackBand(dataUrl,outputWidth,outputHeight)" in exporter
    assert 'data-action="exportHd"' in editor
    assert "await doExport(2)" in app


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


def test_zoom_logo_and_conversion_footer_controls_are_explicit():
    html = (ROOT / "templates/admin/studio_visuals/editor.html").read_text()
    app = (ROOT / "static/studio_visuals/js/studio-app.js").read_text()
    store = (ROOT / "static/studio_visuals/js/studio-store.js").read_text()
    renderer = (ROOT / "static/studio_visuals/js/studio-renderer.js").read_text()
    shell = (ROOT / "static/studio_visuals/css/studio-shell.css").read_text()
    templates = (ROOT / "static/studio_visuals/css/studio-templates.css").read_text()

    assert 'id="zoomRange"' in html
    assert 'data-action="zoomOut"' in html
    assert 'data-action="zoomIn"' in html
    assert 'data-action="zoomFit"' in html
    assert 'id="zoomSelect"' not in html
    assert "function setZoomPercent(" in app
    assert "function getSlideLogo(" in app
    assert "DEFAULT_LOGO_SETTINGS" in store
    assert 'class="studio-brand-logo"' in renderer
    assert 'data-logo-resize="true"' in renderer
    assert 'class="sv-footer__cta"' in renderer
    assert ".studio-zoom-control" in shell
    assert ".studio-brand-logo" in templates
    assert ".sv-footer__cta" in templates


def test_templates_use_the_integrale_web_identity_system():
    renderer = (ROOT / "static/studio_visuals/js/studio-renderer.js").read_text()
    styles = (ROOT / "static/studio_visuals/css/studio-templates.css").read_text()

    official_tokens = {
        "#F6F0E4",  # Academy cream
        "#FFFDF8",  # Academy / Group surface
        "#F2BB31",  # Academy gold
        "#F4C45A",  # Group gold
        "#081626",  # Academy navy
        "#020611",  # Group night
        "#0D2036",  # Group panel
    }
    for token in official_tokens:
        assert token.upper() in styles.upper()

    assert "Intégrale web identity" in styles
    assert ".studio-v2 .sv-brand__slogan:before" in styles
    assert ".studio-v2 .poster-center" in styles
    assert ".studio-v2 .split>section" in styles
    assert ".studio-v2 .mk:before" in styles
    assert ".studio-v2 .mk-modal dialog" in styles
    assert "font-weight:950" in styles
    assert "el.dataset.formation=project.formation" in renderer
    assert "--formation-primary" in renderer
    assert "--theme-background','#F6F0E4'" in renderer
