import json
from pathlib import Path

from services.studio_export_service import EXPORT_DIMENSIONS
from services.studio_template_service import load_studio_config
from social_visuals import generate_content_from_topic

ROOT = Path(__file__).resolve().parents[1]


def test_template_catalog_has_15_families_110_variants_and_50_new_designs():
    cfg = load_studio_config(ROOT)
    assert len(cfg["families"]) >= 15
    assert len(cfg["templates"]) >= 110
    assert all(t["family"] and t["renderer"] for t in cfg["templates"])
    new_templates = [template for template in cfg["templates"] if template.get("isNew")]
    assert len(new_templates) == 50
    assert len({template["id"] for template in new_templates}) == 50
    assert len({template["previewStyle"] for template in new_templates}) == 50
    assert len({template["brandLayout"] for template in new_templates}) >= 10
    assert all(template["name"].startswith("NEW") for template in new_templates)
    assert all(template["renderer"] == "renderNewTemplate" for template in new_templates)
    assert all(len(template["supportedFormats"]) == 4 for template in new_templates)


def test_themes_cover_required_formations_and_tokens():
    cfg = load_studio_config(ROOT)
    required = {"A3P", "APS", "SSIAP", "DIRIGEANT", "VTC"}
    assert required <= set(cfg["themes"])
    tokens = {"primary", "secondary", "accent", "background", "backgroundAlt", "surface", "surfaceDark", "text", "textMuted", "border", "shadow", "danger", "success"}
    for theme in cfg["themes"].values():
        assert tokens <= set(theme)
        assert len(theme["variants"]) >= 8
    assert len({theme["primary"] for theme in cfg["themes"].values()}) == len(cfg["themes"])
    assert len({theme["surfaceDark"] for theme in cfg["themes"].values()}) == len(cfg["themes"])
    assert cfg["themes"]["APS"]["primary"] == "#0057D8"
    assert cfg["themes"]["A3P"]["primary"] == "#087A55"
    assert cfg["themes"]["VTC"]["primary"] == "#6D28D9"
    assert cfg["themes"]["DIRIGEANT"]["primary"] == "#D96900"
    assert cfg["themes"]["SSIAP"]["primary"] == "#D71920"


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
        "#020611",  # Group night
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
    assert "--formation-secondary" in renderer
    assert "--formation-dark" in renderer
    assert "theme.background||'#FFF8E1'" in renderer


def test_template_chrome_cannot_silently_clip_and_keeps_formation_identity():
    app = (ROOT / "static/studio_visuals/js/studio-app.js").read_text()
    store = (ROOT / "static/studio_visuals/js/studio-store.js").read_text()
    renderer = (ROOT / "static/studio_visuals/js/studio-renderer.js").read_text()
    fitting = (ROOT / "static/studio_visuals/js/studio-text-fit.js").read_text()
    validation = (ROOT / "static/studio_visuals/js/studio-validation.js").read_text()
    styles = (ROOT / "static/studio_visuals/css/studio-templates.css").read_text()

    assert 'class="sv-brand__formation"' in renderer
    assert 'data-fit="badge"' in renderer
    assert "replace(/^www\\./i,'')" in renderer
    assert "Math.min(320" in renderer
    assert "Math.min(320" in store
    assert 'max="320"' in app
    assert "a==='autoFix'" in app
    assert "export function fitLayoutFrame" in fitting
    assert "main.dataset.layoutScale" in fitting
    assert "kind==='badge'" in fitting
    assert "function isTextClipped" in validation
    assert ".sv-footer__site,.sv-footer__phone" in validation
    assert "Geometry and formation identity correction" in styles
    assert ".studio-v2 .poster-center:after{display:none!important}" in styles
    assert "white-space:nowrap" in styles
    assert "grid-template-columns:minmax(190px,.82fr) minmax(305px,1.2fr) max-content" in styles


def test_every_rendered_element_can_be_selected_moved_resized_and_styled():
    app = (ROOT / "static/studio_visuals/js/studio-app.js").read_text()
    renderer = (ROOT / "static/studio_visuals/js/studio-renderer.js").read_text()
    store = (ROOT / "static/studio_visuals/js/studio-store.js").read_text()
    editor = (ROOT / "static/studio_visuals/js/studio-element-editor.js").read_text()
    styles = (ROOT / "static/studio_visuals/css/studio-new-templates.css").read_text()

    assert "decorateEditableElements(el,slide,{renderMode})" in renderer
    assert "elementOverrides" in store
    assert "data-studio-element-id" in editor
    assert "activeTemplatePrefix" in editor
    assert "id.startsWith(activeTemplatePrefix)" in editor
    assert "dataset.studioTextEditable" in app
    assert 'data-element-prop="scale"' in app
    assert 'data-element-prop="fontSize"' in app
    assert 'data-element-prop="rotation"' in app
    assert 'data-element-prop="opacity"' in app
    assert "function nudgeSelectedElement" in app
    assert "function handlePointerMove" in app
    assert "studio-element-resize" in styles
    assert "studio-selected" in styles
    fitting = (ROOT / "static/studio_visuals/js/studio-text-fit.js").read_text()
    assert "studioManualFont!=='true'" in fitting
    assert "studioManualLayout!=='true'" in fitting


def test_new_templates_have_their_own_renderer_and_site_inspired_visual_system():
    renderer = (ROOT / "static/studio_visuals/js/studio-renderer.js").read_text()
    bodies = (ROOT / "static/studio_visuals/js/studio-new-templates.js").read_text()
    styles = (ROOT / "static/studio_visuals/css/studio-new-templates.css").read_text()

    assert "function renderNewTemplate(ctx)" in renderer
    assert "renderNewTemplateBody(ctx)" in renderer
    assert bodies.count("new_") >= 100
    assert "'mark','new-highlight'" in bodies
    assert "new-phone-mockup" in bodies
    assert "new-question-hook" in bodies
    assert "Shared visual language from the two Intégrale websites" in styles
    assert ".brand-top-left" in styles
    assert ".brand-bottom-right" in styles
    assert ".new-manifesto" in styles
    assert ".new-future" in styles


def test_new_template_chrome_overrides_legacy_insets_and_reserves_logo_space():
    renderer = (ROOT / "static/studio_visuals/js/studio-renderer.js").read_text()
    fitting = (ROOT / "static/studio_visuals/js/studio-text-fit.js").read_text()
    styles = (ROOT / "static/studio_visuals/css/studio-new-templates.css").read_text()

    # The legacy Studio stylesheet uses `inset:auto!important` on the brand
    # block. Every NEW placement therefore needs an explicit important edge.
    assert "inset:auto!important;" in styles
    assert "top:var(--new-brand-top)!important;" in styles
    assert "left:50%!important;" in styles
    assert "left:38px!important" in styles
    assert "right:38px!important" in styles
    assert "bottom:112px!important;" in styles
    assert "inset:max(170px,calc(58px + var(--new-logo-size))) var(--new-edge) var(--new-footer-clearance)!important;" in styles
    assert "inset:auto var(--new-edge) var(--new-footer-bottom)!important;" in styles

    for placement in (
        "top-left",
        "top-center",
        "top-right",
        "side-left",
        "side-right",
        "floating-left",
        "floating-right",
        "bottom-left",
        "bottom-center",
        "bottom-right",
    ):
        assert f"brand-{placement}" in styles

    # Logo resizing must change both the visible logo and the space reserved
    # around it; the inspector role must describe the actual NEW placement.
    assert "el.style.setProperty('--studio-logo-size'" in renderer
    assert "el.style.setProperty('--studio-chrome-logo-size'" in renderer
    assert 'data-layout-role="brand-${brandLayout}"' in renderer
    assert "var(--studio-chrome-logo-size" in styles

    # Vertical side signatures use their own line and height measurements.
    assert "startsWith('vertical')" in fitting
    assert "vertical?rect.left:rect.top" in fitting
    assert "Math.min(520,parentHeight-40)" in fitting
