import io

import pytest
from PIL import Image

from services.studio_v2_service import StudioError, StudioStorage


def project():
    return {"name": "Test", "format": "instagram_portrait", "width": 1080,
            "height": 1350, "formation": "A3P", "pages": [{"fabric": {"objects": []}}]}


def image_file(fmt):
    stream = io.BytesIO()
    Image.new("RGB", (32, 24), "red").save(stream, fmt)
    stream.seek(0)
    return stream


def test_project_lifecycle_and_persistence(tmp_path):
    storage = StudioStorage(tmp_path)
    created = storage.create_project(project(), "admin@example.test")
    updated = storage.update_project(created["id"], {"name": "Modifié"})
    assert updated["name"] == "Modifié"
    assert StudioStorage(tmp_path).get_project(created["id"])["name"] == "Modifié"
    duplicate = storage.duplicate_project(created["id"], "admin@example.test")
    assert duplicate["id"] != created["id"]
    storage.delete_project(created["id"])
    with pytest.raises(StudioError): storage.get_project(created["id"])


@pytest.mark.parametrize(("fmt", "name", "mime"), [("JPEG", "photo.jpg", "image/jpeg"), ("PNG", "photo.png", "image/png"), ("WEBP", "photo.webp", "image/webp")])
def test_valid_images_are_normalized_and_thumbnailed(tmp_path, fmt, name, mime):
    storage = StudioStorage(tmp_path)
    asset = storage.save_asset(image_file(fmt), name, lambda aid, kind: f"/{aid}/{kind}")
    assert asset["mime"] == mime
    assert asset["width"] == 32 and asset["height"] == 24
    assert storage.asset_file(asset["id"]).is_file()
    assert storage.asset_file(asset["id"], True).is_file()


def test_fake_image_and_base64_project_are_rejected(tmp_path):
    storage = StudioStorage(tmp_path)
    with pytest.raises(StudioError, match="pas une image valide"):
        storage.save_asset(io.BytesIO(b"not really a png"), "fake.png", lambda *_: "")
    bad = project(); bad["pages"][0]["fabric"]["objects"] = [{"src": "data:image/png;base64,AAAA"}]
    with pytest.raises(StudioError, match="base64"):
        storage.create_project(bad, "admin")


def test_path_traversal_identifier_is_rejected(tmp_path):
    with pytest.raises(StudioError, match="Identifiant"):
        StudioStorage(tmp_path).get_project("../../data.json")
