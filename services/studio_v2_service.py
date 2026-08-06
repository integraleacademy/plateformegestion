"""Persistent, isolated storage for Studio Visuel V2.

Project JSON and uploaded media deliberately never touch the application's main
``data.json``.  Every write is validated and atomically replaced while holding a
Studio-only lock.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

SCHEMA_VERSION = 2
MAX_ASSET_BYTES = 15 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
_LOCK = threading.RLock()


class StudioError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class StudioStorage:
    def __init__(self, root):
        self.root = Path(root).resolve()
        for name in ("projects", "assets", "thumbnails", "templates", "metadata", "backups"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _id(value):
        try:
            return uuid.UUID(str(value)).hex
        except (ValueError, TypeError, AttributeError):
            raise StudioError("Identifiant Studio invalide.")

    def _json_path(self, section, item_id):
        return self.root / section / f"{self._id(item_id)}.json"

    def _write_json(self, path, payload):
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        if b"data:image/" in encoded or b";base64," in encoded:
            raise StudioError("Les images encodées en base64 ne sont pas autorisées dans un projet.")
        tmp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        with _LOCK:
            if path.exists():
                shutil.copy2(path, self.root / "backups" / f"{path.stem}.json.bak")
            with tmp.open("wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def list_projects(self):
        with _LOCK:
            rows = [self._read(path) for path in (self.root / "projects").glob("*.json")]
        return sorted(rows, key=lambda row: row.get("updated_at", ""), reverse=True)

    @staticmethod
    def _read(path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StudioError("Données Studio illisibles.", 500) from exc

    def get_project(self, item_id):
        path = self._json_path("projects", item_id)
        if not path.exists():
            raise StudioError("Projet introuvable.", 404)
        return self._read(path)

    def create_project(self, payload, author):
        payload = self._validate_project(payload)
        now, item_id = self._now(), uuid.uuid4().hex
        project = {**payload, "id": item_id, "schema_version": SCHEMA_VERSION,
                   "author": author or "admin", "created_at": now, "updated_at": now}
        self._write_json(self._json_path("projects", item_id), project)
        return project

    def update_project(self, item_id, patch):
        current = self.get_project(item_id)
        allowed = {"name", "format", "width", "height", "formation", "template_id", "pages", "caption", "hashtags", "thumbnail"}
        merged = {**current, **{key: value for key, value in patch.items() if key in allowed}}
        merged = {**current, **self._validate_project(merged), "updated_at": self._now()}
        self._write_json(self._json_path("projects", item_id), merged)
        return merged

    def delete_project(self, item_id):
        path = self._json_path("projects", item_id)
        if not path.exists():
            raise StudioError("Projet introuvable.", 404)
        with _LOCK:
            path.unlink()

    def duplicate_project(self, item_id, author):
        source = self.get_project(item_id)
        source.pop("id", None); source.pop("created_at", None); source.pop("updated_at", None)
        source["name"] = f"{source.get('name', 'Sans titre')} — copie"
        return self.create_project(source, author)

    @staticmethod
    def _validate_project(payload):
        if not isinstance(payload, dict):
            raise StudioError("Le projet doit être un objet JSON.")
        width, height = payload.get("width", 1080), payload.get("height", 1350)
        if not isinstance(width, int) or not isinstance(height, int) or not (100 <= width <= 10000 and 100 <= height <= 10000):
            raise StudioError("Dimensions de document invalides.")
        pages = payload.get("pages") or []
        if not isinstance(pages, list) or not pages or len(pages) > 100:
            raise StudioError("Le projet doit contenir entre 1 et 100 pages.")
        for page in pages:
            if not isinstance(page, dict) or not isinstance(page.get("fabric"), dict):
                raise StudioError("État Fabric.js de page invalide.")
        return {"name": str(payload.get("name") or "Sans titre")[:160], "format": str(payload.get("format") or "custom")[:40],
                "width": width, "height": height, "formation": str(payload.get("formation") or "A3P")[:40],
                "template_id": payload.get("template_id"), "pages": pages,
                "caption": str(payload.get("caption") or "")[:10000], "hashtags": list(payload.get("hashtags") or [])[:100],
                "thumbnail": payload.get("thumbnail")}

    def list_assets(self):
        with _LOCK:
            rows = [self._read(path) for path in (self.root / "metadata").glob("*.json")]
        return sorted(rows, key=lambda row: row.get("created_at", ""), reverse=True)

    def get_asset(self, item_id):
        path = self._json_path("metadata", item_id)
        if not path.exists():
            raise StudioError("Média introuvable.", 404)
        return self._read(path)

    def save_asset(self, stream, original_name, public_url):
        stream.seek(0, os.SEEK_END); size = stream.tell(); stream.seek(0)
        if size > MAX_ASSET_BYTES:
            raise StudioError("Le fichier dépasse la limite de 15 Mo.", 413)
        try:
            image = Image.open(stream); image.verify(); stream.seek(0); image = Image.open(stream)
            fmt = image.format
            if fmt not in ALLOWED_IMAGE_FORMATS:
                raise StudioError("Format refusé. Utilisez JPEG, PNG ou WebP.")
            image = ImageOps.exif_transpose(image)
        except (UnidentifiedImageError, OSError) as exc:
            raise StudioError("Ce fichier n'est pas une image valide.") from exc
        ext, mime = ALLOWED_IMAGE_FORMATS[fmt]; item_id = uuid.uuid4().hex
        destination = self.root / "assets" / f"{item_id}.{ext}"
        save_image = image.convert("RGB") if fmt == "JPEG" else image.copy()
        save_image.save(destination, format=fmt, optimize=True, quality=92)
        thumb = image.copy(); thumb.thumbnail((480, 480)); thumb_path = self.root / "thumbnails" / f"{item_id}.webp"
        (thumb.convert("RGB") if thumb.mode not in ("RGB", "RGBA") else thumb).save(thumb_path, "WEBP", quality=82, method=6)
        meta = {"id": item_id, "name": Path(original_name or "image").name[:200], "mime": mime, "width": image.width,
                "height": image.height, "size": destination.stat().st_size, "url": public_url(item_id, "file"),
                "thumbnail_url": public_url(item_id, "thumbnail"), "created_at": self._now()}
        self._write_json(self._json_path("metadata", item_id), meta)
        return meta

    def asset_file(self, item_id, thumbnail=False):
        meta = self.get_asset(item_id)
        if thumbnail:
            return self.root / "thumbnails" / f"{self._id(item_id)}.webp"
        return self.root / "assets" / f"{self._id(item_id)}.{ALLOWED_IMAGE_FORMATS_INV[meta['mime']]}"

    def delete_asset(self, item_id):
        meta = self.get_asset(item_id)
        ext = ALLOWED_IMAGE_FORMATS_INV[meta["mime"]]
        with _LOCK:
            for path in (self.root / "assets" / f"{self._id(item_id)}.{ext}", self.root / "thumbnails" / f"{self._id(item_id)}.webp", self._json_path("metadata", item_id)):
                path.unlink(missing_ok=True)


ALLOWED_IMAGE_FORMATS_INV = {mime: ext for ext, mime in ALLOWED_IMAGE_FORMATS.values()}
