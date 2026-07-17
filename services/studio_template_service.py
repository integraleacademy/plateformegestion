import json
from pathlib import Path


def _read_json(root_path, name):
    path = Path(root_path) / "static" / "studio_visuals" / "data" / name
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_studio_config(root_path):
    templates_data = _read_json(root_path, "templates.json")
    themes = _read_json(root_path, "themes.json")
    recipes = _read_json(root_path, "carousel-recipes.json")
    icons = _read_json(root_path, "icons.json")
    return {
        "themes": themes,
        "templates": templates_data["templates"],
        "families": templates_data["families"],
        "recipes": recipes["recipes"],
        "icons": icons["icons"],
    }
