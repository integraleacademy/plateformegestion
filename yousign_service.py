"""Service d'intégration Yousign API v3.

Ce module ne dépend pas de Flask afin de rester testable isolément. Les secrets
sont lus depuis l'environnement et ne doivent jamais être exposés au frontend.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("yousign")

DEFAULT_YOUSIGN_API_BASE_URL = "https://api.yousign.app/v3"
YOUSIGN_STATUSES = {"draft", "approval", "ongoing", "done", "declined", "expired", "canceled", "rejected", "error"}
YOUSIGN_EXTERNAL_ID_MAX_LENGTH = 180
YOUSIGN_EXTERNAL_ID_FALLBACK = "aps-trainer-contract"


def sanitize_yousign_external_id(value: str, fallback: str = YOUSIGN_EXTERNAL_ID_FALLBACK) -> str:
    """Nettoie un external_id pour respecter les contraintes Yousign.

    Yousign autorise uniquement les lettres, chiffres, espaces et caractères
    `_ - @ . % +`. Les autres caractères sont remplacés avant l'envoi afin
    d'éviter un rejet du POST /signature_requests.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_\-@.%+ ]+", "-", value or "")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    cleaned = cleaned.strip(" -")
    return cleaned[:YOUSIGN_EXTERNAL_ID_MAX_LENGTH] or fallback


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
    workspace_id: str = ""


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def get_yousign_config() -> YousignConfig:
    # YOUSIGN_BASE_URL is the canonical variable used by the deployment runbook.
    # Keep YOUSIGN_API_BASE_URL as a backward-compatible alias only.
    base_url = (_env("YOUSIGN_BASE_URL") or _env("YOUSIGN_API_BASE_URL", DEFAULT_YOUSIGN_API_BASE_URL)).rstrip("/")
    return YousignConfig(
        api_key=_env("YOUSIGN_API_KEY"),
        base_url=base_url,
        webhook_secret=_env("YOUSIGN_WEBHOOK_SECRET"),
        contract_template_id=_env("YOUSIGN_CONTRACT_TEMPLATE_ID"),
        signature_level=_env("YOUSIGN_SIGNATURE_LEVEL", "electronic_signature"),
        authentication_mode=_env("YOUSIGN_AUTHENTICATION_MODE", "no_otp"),
        delivery_mode=_env("YOUSIGN_DELIVERY_MODE", "email"),
        workspace_id=_env("YOUSIGN_WORKSPACE_ID"),
    )



def detect_yousign_environment(base_url: str) -> str:
    url = (base_url or "").lower()
    if "api-sandbox.yousign.app" in url:
        return "sandbox"
    if "api.yousign.app" in url:
        return "production"
    return "custom"


def mask_yousign_api_key(api_key: str) -> str:
    if not api_key:
        return "absent"
    prefix = api_key[:6]
    return f"present:{prefix}..." if prefix else "present"


def yousign_config_diagnostics(config: Optional[YousignConfig] = None) -> Dict[str, Any]:
    config = config or get_yousign_config()
    return {
        "environment": detect_yousign_environment(config.base_url),
        "base_url": config.base_url,
        "api_key": mask_yousign_api_key(config.api_key),
        "api_key_present": bool(config.api_key),
        "workspace_id_present": bool(config.workspace_id),
    }


def normalizeFrenchPhoneNumber(phone: str) -> str:
    """Normalise un numéro mobile français au format international E.164."""
    cleaned = re.sub(r"[\s.\-()]+", "", phone or "")
    if cleaned.startswith("0033"):
        cleaned = "+33" + cleaned[4:]
    if cleaned.startswith("06") or cleaned.startswith("07"):
        cleaned = "+33" + cleaned[1:]
    if cleaned.startswith("+33") and re.fullmatch(r"\+33[67]\d{8}", cleaned):
        return cleaned
    raise YousignError("Numéro de téléphone formateur absent ou invalide pour l’OTP SMS Yousign.")


def mask_phone_number(phone: str) -> str:
    if not phone:
        return "absent"
    return f"{phone[:3]}******{phone[-2:]}" if len(phone) >= 5 else "***"


def yousign_service_access_message(status_code: Optional[int], payload: Any = None) -> str:
    message = payload.get("message") if isinstance(payload, dict) else ""
    if status_code == 401:
        return "Clé API Yousign invalide ou absente."
    if status_code == 403 and message == "You cannot consume this service":
        return "Yousign refuse l’accès au service de signature. Vérifiez la clé API, l’environnement sandbox/production, les droits de la clé et l’abonnement Yousign."
    if status_code == 403:
        return "Yousign refuse l’accès au service de signature. Vérifiez la clé API, l’environnement sandbox/production, les droits de la clé, le workspace et l’abonnement Yousign."
    return message or (f"Erreur API Yousign ({status_code})" if status_code else "Erreur Yousign")

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

    def request_with_http_status(self, method: str, path: str, payload: Any = None, headers: Optional[Dict[str, str]] = None) -> tuple[Any, int, str]:
        body = None
        request_headers = self._headers()
        if headers:
            request_headers.update(headers)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        url = self._url(path)
        req = urllib.request.Request(url, data=body, headers=request_headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = response.read()
                payload = {}
                if data:
                    charset = response.headers.get_content_charset() or "utf-8"
                    payload = json.loads(data.decode(charset))
                return payload, response.status, url
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                error_payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                error_payload = {"raw": raw[:500]}
            logger.warning("Yousign API error status=%s path=%s response=%r", exc.code, path, error_payload)
            message = error_payload.get("message") if isinstance(error_payload, dict) else None
            raise YousignError(message or f"Erreur API Yousign ({exc.code})", exc.code, error_payload) from exc
        except urllib.error.URLError as exc:
            logger.warning("Yousign network error path=%s reason=%s", path, exc.reason)
            raise YousignError("Impossible de joindre l'API Yousign.") from exc

    def request(self, method: str, path: str, payload: Any = None, headers: Optional[Dict[str, str]] = None) -> Any:
        response_payload, _status, _url = self.request_with_http_status(method, path, payload, headers)
        return response_payload

    def upload_file(self, signature_request_id: str, pdf_bytes: bytes, filename: str, parse_anchors: bool = True) -> Any:
        boundary = "----plateformegestion-yousign-boundary"
        safe_filename = filename.replace('"', "") or "contrat.pdf"
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{safe_filename}\"\r\nContent-Type: application/pdf\r\n\r\n".encode(),
            pdf_bytes,
            f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"nature\"\r\n\r\nsignable_document\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"parse_anchors\"\r\n\r\n{str(bool(parse_anchors)).lower()}\r\n--{boundary}--\r\n".encode(),
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
            logger.warning("Yousign document upload failed status=%s response=%s", exc.code, raw[:2000])
            raise YousignError("Échec de l'envoi du PDF à Yousign.", exc.code, raw[:2000]) from exc

    def create_signature_request(self, name: str, external_id: str = "") -> Any:
        payload = {"name": name[:128], "delivery_mode": self.config.delivery_mode}
        if self.config.workspace_id:
            payload["workspace_id"] = self.config.workspace_id
        if external_id:
            sanitized_external_id = sanitize_yousign_external_id(external_id)
            payload["external_id"] = sanitized_external_id
            logger.info("Yousign signature_request external_id=%s", sanitized_external_id)
        return self.request("POST", "signature_requests", payload)

    def add_signer(self, signature_request_id: str, first_name: str, last_name: str, email: str, document_id: Optional[str] = None, use_text_tags: bool = False, phone_number: Optional[str] = None, force_sms_otp: bool = False) -> Any:
        info = {"first_name": first_name or last_name or "Formateur", "last_name": last_name or first_name or "Intégrale", "email": email, "locale": "fr"}
        authentication_mode = self.config.authentication_mode
        if force_sms_otp:
            normalized_phone = normalizeFrenchPhoneNumber(phone_number or "")
            info["phone_number"] = normalized_phone
            authentication_mode = "otp_sms"
            logger.info("Yousign signer authentication_mode=%s phone_number=%s", authentication_mode, mask_phone_number(normalized_phone))
        payload: Dict[str, Any] = {
            "info": info,
            "signature_level": "electronic_signature" if force_sms_otp else self.config.signature_level,
            "signature_authentication_mode": authentication_mode,
            "delivery_mode": "email" if force_sms_otp else self.config.delivery_mode,
        }
        if document_id and not use_text_tags:
            # Champ attendu par l'API v3 pour positionner une signature visible simple.
            payload["fields"] = [{"document_id": document_id, "type": "signature", "page": 1, "x": 420, "y": 700}]
        return self.request("POST", f"signature_requests/{urllib.parse.quote(signature_request_id)}/signers", payload)

    def add_signature_field(
        self,
        signature_request_id: str,
        document_id: str,
        signer_id: str,
        page: int,
        x: int,
        y: int,
        width: int = 160,
        height: int = 60,
    ) -> Any:
        payload = {
            "type": "signature",
            "signer_id": signer_id,
            "document_id": document_id,
            "page": int(page or 1),
            "x": int(x),
            "y": int(y),
            "width": int(width),
            "height": int(height),
        }
        field = self.request(
            "POST",
            f"signature_requests/{urllib.parse.quote(signature_request_id)}/documents/{urllib.parse.quote(document_id)}/fields",
            payload,
        )
        logger.info(
            "Yousign signature field created field_id=%s signer_id=%s document_id=%s page=%s x=%s y=%s width=%s height=%s",
            field.get("id") if isinstance(field, dict) else "",
            signer_id,
            document_id,
            payload["page"],
            payload["x"],
            payload["y"],
            payload["width"],
            payload["height"],
        )
        return field

    def activate_signature_request(self, signature_request_id: str) -> Any:
        return self.request("POST", f"signature_requests/{urllib.parse.quote(signature_request_id)}/activate")

    def get_signature_request(self, signature_request_id: str) -> Any:
        return self.request("GET", f"signature_requests/{urllib.parse.quote(signature_request_id)}")

    def get_signature_request_with_http_status(self, signature_request_id: str) -> tuple[Any, int, str]:
        return self.request_with_http_status("GET", f"signature_requests/{urllib.parse.quote(signature_request_id)}")

    def get_signature_request_signers(self, signature_request_id: str) -> Any:
        return self.request("GET", f"signature_requests/{urllib.parse.quote(signature_request_id)}/signers")

    def get_signature_request_signers_with_http_status(self, signature_request_id: str) -> tuple[Any, int, str]:
        return self.request_with_http_status("GET", f"signature_requests/{urllib.parse.quote(signature_request_id)}/signers")

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
    diagnostic = yousign_config_diagnostics(client.config)
    try:
        client.request("GET", "signature_requests?limit=1")
        return {**diagnostic, "ok": True, "status": 200, "message": "Connexion Yousign OK."}
    except YousignError as exc:
        status = exc.status_code or 0
        return {
            **diagnostic,
            "ok": False,
            "status": status,
            "message": yousign_service_access_message(status, exc.payload),
            "yousign_message": exc.payload.get("message") if isinstance(exc.payload, dict) else str(exc.payload or ""),
        }
