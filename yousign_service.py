"""Service d'intégration Yousign API v3.

Ce module ne dépend pas de Flask afin de rester testable isolément. Les secrets
sont lus depuis l'environnement et ne doivent jamais être exposés au frontend.
"""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("yousign")

DEFAULT_YOUSIGN_API_BASE_URL = "https://api.yousign.app/v3"
YOUSIGN_STATUSES = {"draft", "approval", "ongoing", "done", "declined", "expired", "canceled", "rejected", "error"}


class YousignError(RuntimeError):
    """Erreur lisible levée lorsque l'appel Yousign échoue."""

    def __init__(self, message: str, status_code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class YousignConfig:
    api_key: str
    base_url: str
    webhook_secret: str = ""
    contract_template_id: str = ""
    signature_level: str = "electronic_signature"
    authentication_mode: str = "no_otp"
    delivery_mode: str = "email"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def get_yousign_config() -> YousignConfig:
    # Render may contain either the historical project variable or the shorter
    # name used in Yousign runbooks. Prefer the explicit API variable when both
    # are present.
    base_url = (_env("YOUSIGN_API_BASE_URL") or _env("YOUSIGN_BASE_URL", DEFAULT_YOUSIGN_API_BASE_URL)).rstrip("/")
    return YousignConfig(
        api_key=_env("YOUSIGN_API_KEY"),
        base_url=base_url,
        webhook_secret=_env("YOUSIGN_WEBHOOK_SECRET"),
        contract_template_id=_env("YOUSIGN_CONTRACT_TEMPLATE_ID"),
        signature_level=_env("YOUSIGN_SIGNATURE_LEVEL", "electronic_signature"),
        authentication_mode=_env("YOUSIGN_AUTHENTICATION_MODE", "no_otp"),
        delivery_mode=_env("YOUSIGN_DELIVERY_MODE", "email"),
    )


def is_yousign_configured() -> bool:
    return bool(get_yousign_config().api_key)


class YousignClient:
    def __init__(self, config: Optional[YousignConfig] = None, timeout: int = 20):
        self.config = config or get_yousign_config()
        self.timeout = timeout

    def _headers(self, content_type: Optional[str] = "application/json") -> Dict[str, str]:
        if not self.config.api_key:
            raise YousignError("Configuration Yousign incomplète: YOUSIGN_API_KEY est manquante.")
        headers = {"Authorization": f"Bearer {self.config.api_key}", "Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}/{path.lstrip('/')}"

    def request(self, method: str, path: str, payload: Any = None, headers: Optional[Dict[str, str]] = None) -> Any:
        body = None
        request_headers = self._headers()
        if headers:
            request_headers.update(headers)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self._url(path), data=body, headers=request_headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = response.read()
                if not data:
                    return {}
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(data.decode(charset))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                error_payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                error_payload = {"raw": raw[:500]}
            logger.warning("Yousign API error status=%s path=%s", exc.code, path)
            message = error_payload.get("message") if isinstance(error_payload, dict) else None
            raise YousignError(message or f"Erreur API Yousign ({exc.code})", exc.code, error_payload) from exc
        except urllib.error.URLError as exc:
            logger.warning("Yousign network error path=%s reason=%s", path, exc.reason)
            raise YousignError("Impossible de joindre l'API Yousign.") from exc

    def upload_file(self, signature_request_id: str, pdf_bytes: bytes, filename: str) -> Any:
        boundary = "----plateformegestion-yousign-boundary"
        safe_filename = filename.replace('"', "") or "contrat.pdf"
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{safe_filename}\"\r\nContent-Type: application/pdf\r\n\r\n".encode(),
            pdf_bytes,
            f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"nature\"\r\n\r\nsignable_document\r\n--{boundary}--\r\n".encode(),
        ]
        req = urllib.request.Request(
            self._url(f"signature_requests/{urllib.parse.quote(signature_request_id)}/documents"),
            data=b"".join(parts),
            headers=self._headers(f"multipart/form-data; boundary={boundary}"),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode(response.headers.get_content_charset() or "utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            logger.warning("Yousign document upload failed status=%s", exc.code)
            raise YousignError("Échec de l'envoi du PDF à Yousign.", exc.code, raw[:500]) from exc

    def create_signature_request(self, name: str, external_id: str = "") -> Any:
        payload = {"name": name[:128], "delivery_mode": self.config.delivery_mode}
        if external_id:
            payload["external_id"] = external_id[:255]
        return self.request("POST", "signature_requests", payload)

    def add_signer(self, signature_request_id: str, first_name: str, last_name: str, email: str, document_id: Optional[str] = None) -> Any:
        payload: Dict[str, Any] = {
            "info": {"first_name": first_name or last_name or "Formateur", "last_name": last_name or first_name or "Intégrale", "email": email, "locale": "fr"},
            "signature_level": self.config.signature_level,
            "signature_authentication_mode": self.config.authentication_mode,
        }
        if document_id:
            # Champ attendu par l'API v3 pour positionner une signature visible simple.
            payload["fields"] = [{"document_id": document_id, "type": "signature", "page": 1, "x": 420, "y": 700}]
        return self.request("POST", f"signature_requests/{urllib.parse.quote(signature_request_id)}/signers", payload)

    def activate_signature_request(self, signature_request_id: str) -> Any:
        return self.request("POST", f"signature_requests/{urllib.parse.quote(signature_request_id)}/activate")

    def get_signature_request(self, signature_request_id: str) -> Any:
        return self.request("GET", f"signature_requests/{urllib.parse.quote(signature_request_id)}")

    def download_signed_documents(self, signature_request_id: str) -> bytes:
        req = urllib.request.Request(
            self._url(f"signature_requests/{urllib.parse.quote(signature_request_id)}/documents/download"),
            headers=self._headers(None),
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return response.read()


def test_yousign_connection() -> Dict[str, Any]:
    client = YousignClient(timeout=10)
    client.request("GET", "signature_requests?limit=1")
    return {"ok": True, "base_url": client.config.base_url}
