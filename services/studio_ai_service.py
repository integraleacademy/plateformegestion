import re
import unicodedata

from social_visuals import generate_content_from_topic


DESIGN_PRESETS = {
    "halloween": {
        "label": "Halloween premium",
        "palette": {"primary": "#F97316", "secondary": "#7C3AED", "accent": "#FDBA74", "background": "#160A22", "backgroundAlt": "#2B103B", "surface": "#2A1538", "surfaceDark": "#09040F", "text": "#FFF7ED", "textMuted": "#F4C2A1", "border": "#7C3AED", "shadow": "rgba(249,115,22,.30)"},
        "decorations": ["🎃", "👻", "🕸️"],
    },
    "noel": {
        "label": "Noël élégant",
        "palette": {"primary": "#B91C1C", "secondary": "#166534", "accent": "#F6D365", "background": "#F7F3E8", "backgroundAlt": "#E4EFE5", "surface": "#FFFDF8", "surfaceDark": "#102A1B", "text": "#20130F", "textMuted": "#725E55", "border": "#D7C49A", "shadow": "rgba(22,101,52,.24)"},
        "decorations": ["🎄", "✨", "🎁"],
    },
    "rentree": {
        "label": "Rentrée dynamique",
        "palette": {"primary": "#0F5CC0", "secondary": "#F59E0B", "accent": "#FDE68A", "background": "#F5F8FF", "backgroundAlt": "#DDEAFF", "surface": "#FFFFFF", "surfaceDark": "#0B2346", "text": "#0B1D38", "textMuted": "#4D6585", "border": "#9CBCE8", "shadow": "rgba(15,92,192,.22)"},
        "decorations": ["🎓", "📚", "✏️"],
    },
    "or-premium": {
        "label": "OR premium Intégrale",
        "palette": {"primary": "#B87900", "secondary": "#F5B82E", "accent": "#F9E6A6", "background": "#FBF6EA", "backgroundAlt": "#EBDDAD", "surface": "#FFFDF8", "surfaceDark": "#18140C", "text": "#17130D", "textMuted": "#6F6248", "border": "#DDC58B", "shadow": "rgba(184,121,0,.24)"},
        "decorations": ["✨", "✦"],
    },
    "estival": {
        "label": "Été lumineux",
        "palette": {"primary": "#0284C7", "secondary": "#F59E0B", "accent": "#FDE68A", "background": "#F0F9FF", "backgroundAlt": "#CFFAFE", "surface": "#FFFFFF", "surfaceDark": "#083344", "text": "#082F49", "textMuted": "#39728A", "border": "#7DD3FC", "shadow": "rgba(2,132,199,.22)"},
        "decorations": ["☀️", "🌊", "✨"],
    },
    "futuriste": {
        "label": "Futuriste néon",
        "palette": {"primary": "#7C3AED", "secondary": "#06B6D4", "accent": "#C4B5FD", "background": "#080B1C", "backgroundAlt": "#111638", "surface": "#171B3C", "surfaceDark": "#030511", "text": "#F5F3FF", "textMuted": "#B4B8D8", "border": "#4F46E5", "shadow": "rgba(6,182,212,.28)"},
        "decorations": ["⚡", "✦", "🚀"],
    },
}


def _normalized(value):
    return "".join(
        char for char in unicodedata.normalize("NFD", value or "")
        if unicodedata.category(char) != "Mn"
    ).lower()


def transform_design_from_prompt(prompt, formation=None, template_id=None):
    """Return a safe, deterministic art direction from a natural-language prompt."""
    raw = str(prompt or "").strip()[:500]
    normalized = _normalized(raw)
    words = set(re.findall(r"[a-z0-9]+", normalized))
    if any(word in normalized for word in ("halloween", "citrouille", "fantome")):
        preset_id = "halloween"
    elif any(word in normalized for word in ("noel", "sapin", "fetes")):
        preset_id = "noel"
    elif any(word in normalized for word in ("rentree", "ecole", "septembre")):
        preset_id = "rentree"
    elif "or" in words or any(word in normalized for word in ("dore", "gold", "luxe", "premium")):
        preset_id = "or-premium"
    elif any(word in normalized for word in ("ete", "estival", "soleil", "vacances")):
        preset_id = "estival"
    elif any(word in normalized for word in ("futur", "neon", "tech", "cyber")):
        preset_id = "futuriste"
    else:
        preset_id = "or-premium" if str(formation or "").upper() == "OR" else "futuriste"
    design = DESIGN_PRESETS[preset_id]
    return {
        "id": preset_id,
        "label": design["label"],
        "prompt": raw,
        "palette": dict(design["palette"]),
        "decorations": list(design["decorations"]),
        "templateId": str(template_id or "")[:80],
        "message": f"Direction artistique « {design['label']} » appliquée.",
    }


__all__ = ["generate_content_from_topic", "transform_design_from_prompt"]
