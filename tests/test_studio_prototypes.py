from pathlib import Path

from PIL import Image

import app as application


EXPECTED_FILES = [
    "01-photo-plein-ecran.png",
    "02-editorial-photo-gauche.png",
    "03-typographique.png",
    "04-diagonale.png",
    "05-cartes-informations.png",
    "06-sombre-premium.png",
    "07-grand-chiffre.png",
    "08-photo-centrale.png",
]


def test_prototypes_page_requires_admin_session():
    client = application.app.test_client()
    response = client.get("/admin/studio-visuels/prototypes")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_prototypes_page_lists_eight_downloadable_visuals():
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["admin_logged"] = True
        session["admin_session_version"] = application.ADMIN_SESSION_VERSION

    response = client.get("/admin/studio-visuels/prototypes")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count("Télécharger le PNG") == 8
    for filename in EXPECTED_FILES:
        assert filename in html


def test_prototype_png_files_are_exactly_1080_square():
    # L'import matérialise les livrables sans stocker de blobs binaires dans Git.
    from services import studio_prototype_assets  # noqa: F401

    prototype_dir = Path(application.app.root_path) / "static/studio/prototypes/a3p"
    assert sorted(path.name for path in prototype_dir.glob("*.png")) == EXPECTED_FILES
    for filename in EXPECTED_FILES:
        with Image.open(prototype_dir / filename) as image:
            assert image.format == "PNG"
            assert image.size == (1080, 1080)
