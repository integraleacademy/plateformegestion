"""Parcours administrateur des conventions de dotation et signatures Yousign."""
import fcntl
import hashlib
import hmac
import os
import secrets
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from functools import wraps
from io import BytesIO

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for

from services.dotation_contracts import contract_values, fingerprint, generate_pdf, read_contract_form, SIGNATURE_FIELDS
from yousign_service import YousignClient, YousignError, get_yousign_config, normalizeFrenchPhoneNumber

LABELS = {"draft": "PDF prêt", "creating": "Préparation Yousign", "ongoing": "En attente de signature",
          "approval": "En préparation", "partially_signed": "Une signature sur deux", "done": "Signé par les deux parties",
          "declined": "Refusé", "expired": "Expiré", "canceled": "Annulé", "rejected": "Refusé", "error": "Envoi à vérifier"}
TERMINAL = {"done", "declined", "expired", "canceled", "rejected"}


def now():
    return datetime.now().isoformat(timespec="seconds")


class DotationWorkflow:
    def __init__(self, app, load, save, lock_path, directory):
        self.app, self.load, self.save = app, load, save
        self.lock_path, self.directory = lock_path, directory
        self.logo = os.path.join(app.root_path, "static", "img", "logo-integrale.png")
        app.jinja_env.globals["dotation_csrf"] = self.csrf
        app.jinja_env.globals["dotation_signature_label"] = lambda status: LABELS.get(status, "À vérifier")
        bp = Blueprint("dotation_contracts", __name__)
        bp.add_url_rule("/dotations/<id>/contrat", "detail", self.locked(self.detail), methods=["GET", "POST"])
        bp.add_url_rule("/dotations/<id>/contrat/pdf", "pdf", self.pdf)
        for action in ("send", "sync", "cancel", "signed"):
            bp.add_url_rule(f"/dotations/<id>/contrat/{action}", action, self.locked(getattr(self, action)), methods=["POST"])
        app.register_blueprint(bp)

    @staticmethod
    def csrf():
        if not session.get("dotation_csrf"):
            session["dotation_csrf"] = secrets.token_urlsafe(32)
        return session["dotation_csrf"]

    @contextmanager
    def transaction(self):
        # Covers both Gunicorn workers, including the entire send workflow.
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        with open(self.lock_path, "a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def locked(self, fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if request.method == "GET":
                return fn(*args, **kwargs)
            supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
            expected = session.get("dotation_csrf") or ""
            if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
                abort(400, "La page a expiré. Rechargez-la avant de réessayer.")
            try:
                with self.transaction():
                    return fn(*args, **kwargs)
            except BlockingIOError:
                if request.headers.get("Accept") == "application/json":
                    return jsonify(ok=False, error="Une opération est déjà en cours."), 409
                flash("Une opération sur les dotations est déjà en cours. Patientez quelques instants puis réessayez.", "error")
                return redirect(url_for("dotations_home"))
        return wrapped

    def find(self, id):
        data = self.load()
        dotation = next((d for d in data if d.get("id") == id), None)
        if dotation is None:
            abort(404)
        return data, dotation

    @staticmethod
    def records(dotation):
        return ([dotation["contract"]] if dotation.get("contract") else []) + dotation.get("contract_history", [])

    @staticmethod
    def blocked(contract):
        state = contract.get("yousign") or {}
        return bool(state.get("creationUncertain") or (state.get("signatureRequestId") and state.get("status") not in TERMINAL))

    def path(self, contract, signed=False):
        filename = contract.get("signedFilename" if signed else "filename") or ""
        if not filename or os.path.basename(filename) != filename:
            abort(404)
        return os.path.join(self.directory, filename)

    def selected_contract(self, dotation, require_current=False):
        version = request.form.get("version") or request.args.get("version")
        contracts = [dotation.get("contract") or {}] if require_current else self.records(dotation)
        record = next((c for c in contracts if c.get("id") == version), None)
        if record is None:
            abort(409, "Cette version du contrat n'est plus celle affichée. Rechargez la page.")
        return record

    def back(self, id):
        return redirect(url_for("dotation_contracts.detail", id=id))

    def detail(self, id):
        data, dotation = self.find(id)
        contract = dotation.get("contract") or {}
        if request.method == "POST":
            if self.blocked(contract):
                flash("La demande Yousign doit être terminée ou annulée avant de créer une nouvelle version.", "error")
                return self.back(id)
            path = None
            try:
                values = read_contract_form(request.form)
                version = uuid.uuid4().hex
                os.makedirs(self.directory, exist_ok=True)
                filename = f"convention_dotation_{id}_{version}.pdf"
                path = os.path.join(self.directory, filename)
                generate_pdf(values, path, self.logo)
                with open(path, "rb") as pdf_file:
                    checksum = hashlib.sha256(pdf_file.read()).hexdigest()
                if contract:
                    dotation.setdefault("contract_history", []).insert(0, contract)
                dotation.update(values)
                dotation["contract"] = {"id": version, "filename": filename, "generatedAt": now(), "snapshot": values,
                                        "fingerprint": fingerprint(values), "sha256": checksum, "yousign": {"status": "draft"}}
                self.save(data)
                flash("Convention générée. Vérifiez le PDF avant de l'envoyer en signature.", "ok")
                return self.back(id)
            except ValueError as exc:
                if path and os.path.isfile(path):
                    os.remove(path)
                flash(str(exc), "error")
                # Preserve every entered field after a validation error.
                values = contract_values(dotation)
                values.update({k: request.form.get(k, values.get(k)) for k in values})
                values["chargeur"] = request.form.get("chargeur") == "1"
        else:
            values = contract_values(dotation)
        state = contract.get("yousign") or {}
        return render_template("dotation_contract.html", d=dotation, values=values, contract=contract, state=state,
                               blocked=self.blocked(contract), stale=bool(contract and fingerprint(contract_values(dotation)) != contract.get("fingerprint")),
                               configured=bool(get_yousign_config().api_key), sms=get_yousign_config().authentication_mode == "otp_sms",
                               sandbox="sandbox" in get_yousign_config().base_url, history=dotation.get("contract_history", []))

    def pdf(self, id):
        _, dotation = self.find(id)
        contract = self.selected_contract(dotation)
        return send_file(self.path(contract), mimetype="application/pdf", as_attachment=request.args.get("download") == "1",
                         download_name="Convention_mise_a_disposition.pdf", max_age=0)

    def client(self):
        # This page explicitly promises an e-mail invitation, even if another
        # integration uses delivery_mode=none for embedded signatures.
        config = replace(get_yousign_config(), delivery_mode="email")
        if not config.api_key:
            raise ValueError("La connexion Yousign n'est pas configurée sur cette application.")
        return YousignClient(config=config, timeout=10)

    def send(self, id):
        data, dotation = self.find(id)
        contract = self.selected_contract(dotation, require_current=True)
        state = contract.setdefault("yousign", {})
        if state.get("signatureRequestId") or state.get("creationUncertain"):
            flash("Une demande existe déjà. Actualisez son statut ; annulez-la avant de préparer une nouvelle version.", "error")
            return self.back(id)
        try:
            if contract.get("fingerprint") != fingerprint(contract_values(dotation)):
                raise ValueError("Les données de la dotation ont changé. Générez une nouvelle version avant l'envoi.")
            values = contract["snapshot"]
            client = self.client()
            use_sms = client.config.authentication_mode == "otp_sms"
            phones = [None, None]
            if use_sms:
                try:
                    phones = [normalizeFrenchPhoneNumber(values.get(key) or "") for key in ("telephone", "centre_telephone")]
                except YousignError:
                    raise ValueError("La signature par SMS nécessite un mobile français valide pour le stagiaire et le centre.")
            with open(self.path(contract), "rb") as pdf_file:
                content = pdf_file.read()
            if hashlib.sha256(content).hexdigest() != contract.get("sha256"):
                raise ValueError("Le PDF a changé depuis sa génération. Générez une nouvelle version.")
            # Save the intent before the network call: an uncertain timeout must
            # never cause a blind retry creating a second request.
            state.update(status="creating", externalId=f"dotation-{id}-{contract['id']}", creationUncertain=True, error=None)
            self.save(data)
            result = client.create_signature_request(f"Mise à disposition de matériel - {values['prenom']} {values['nom']}", state["externalId"])
            if not result.get("id"):
                raise YousignError("Yousign n'a pas retourné l'identifiant de la demande.")
            state.update(signatureRequestId=result["id"], creationUncertain=False)
            self.save(data)
            srid = state["signatureRequestId"]
            document = client.upload_file(srid, content, "Convention_mise_a_disposition.pdf", parse_anchors=False)
            if not document.get("id"):
                raise YousignError("Le document n'a pas été identifié par Yousign.")
            state["documentId"] = document["id"]
            self.save(data)
            for first, last, email, phone, role in (
                (values["prenom"], values["nom"], values["email"], phones[0], "stagiaire"),
                ("Clément", "VAILLANT", values["centre_email"], phones[1], "centre"),
            ):
                signer = client.add_signer(srid, first, last, email, use_text_tags=True, phone_number=phone, force_sms_otp=use_sms)
                if not signer.get("id"):
                    raise YousignError("Un signataire n'a pas été identifié par Yousign.")
                state[role + "SignerId"] = signer["id"]
                self.save(data)
                field = client.add_signature_field(srid, document["id"], signer["id"], **SIGNATURE_FIELDS[role])
                if not field.get("id"):
                    raise YousignError("Le champ de signature n'a pas été créé.")
                state[role + "FieldId"] = field["id"]
                self.save(data)
            result = client.activate_signature_request(srid)
            state.update(status=result.get("status") or "ongoing", sentAt=now(), error=None)
            self.save(data)
            flash("Convention envoyée par Yousign au stagiaire et à Clément VAILLANT.", "ok")
        except (ValueError, YousignError, OSError) as exc:
            if isinstance(exc, YousignError) and exc.status_code and 400 <= exc.status_code < 500 and not state.get("signatureRequestId"):
                state["creationUncertain"] = False
            state.update(status="error", error=str(exc), lastAttemptAt=now())
            self.save(data)
            flash(f"Envoi non confirmé : {exc}", "error")
        return self.back(id)

    def sync_record(self, contract):
        state = contract.setdefault("yousign", {})
        if not state.get("signatureRequestId"):
            raise ValueError("Aucune demande Yousign identifiable à actualiser.")
        client = self.client()
        result = client.get_signature_request(state["signatureRequestId"])
        status = result.get("status")
        if status not in LABELS:
            raise ValueError("Yousign n'a pas renvoyé de statut reconnu.")
        if status == "ongoing":
            signers = client.get_signature_request_signers(state["signatureRequestId"])
            signers = signers.get("data", signers.get("signers", [])) if isinstance(signers, dict) else signers
            if any(s.get("status") in {"signed", "done"} for s in (signers or [])):
                status = "partially_signed"
        # Only the authenticated signature request status can mark both parties
        # as done. A single signer.done webhook is insufficient.
        state.update(status=status, lastSyncedAt=now(), error=None)
        if status == "done":
            state.setdefault("signedAt", now())
        return state

    def sync(self, id):
        data, dotation = self.find(id)
        contract = self.selected_contract(dotation)
        try:
            state = self.sync_record(contract)
            self.save(data)
            if state["status"] == "done":
                try:
                    self.cache_signed(contract)
                    self.save(data)
                except (ValueError, YousignError, OSError, zipfile.BadZipFile):
                    pass  # Keep the proven signature status; download can retry.
            if request.headers.get("Accept") == "application/json":
                return jsonify(ok=True, status=state["status"], label=LABELS[state["status"]])
            flash("Statut de signature actualisé.", "ok")
        except (ValueError, YousignError, OSError) as exc:
            contract.setdefault("yousign", {})["error"] = str(exc)
            self.save(data)
            if request.headers.get("Accept") == "application/json":
                return jsonify(ok=False, error=str(exc)), 502
            flash(f"Actualisation impossible : {exc}", "error")
        return self.back(id)

    def cancel(self, id):
        data, dotation = self.find(id)
        contract = self.selected_contract(dotation, require_current=True)
        try:
            state = self.sync_record(contract)
            if state["status"] == "done":
                raise ValueError("Cette convention est déjà signée par les deux parties.")
            client = self.client()
            if state["status"] == "draft":
                client.request("DELETE", f"signature_requests/{state['signatureRequestId']}")
            elif state["status"] not in TERMINAL:
                client.cancel_signature_request(state["signatureRequestId"], "Convention annulée depuis la gestion des dotations.")
            state.update(status="canceled", canceledAt=now(), error=None)
            self.save(data)
            flash("Demande annulée. Vous pouvez générer une nouvelle version.", "ok")
        except (ValueError, YousignError, OSError) as exc:
            self.save(data)
            flash(f"Annulation non confirmée : {exc}", "error")
        return self.back(id)

    def cache_signed(self, contract):
        if contract.get("signedFilename") and os.path.isfile(self.path(contract, signed=True)):
            return
        state = contract.get("yousign") or {}
        if state.get("status") != "done":
            raise ValueError("Le document n'est pas encore signé par les deux parties.")
        content = self.client().download_signed_documents(state["signatureRequestId"])
        if zipfile.is_zipfile(BytesIO(content)):
            with zipfile.ZipFile(BytesIO(content)) as archive:
                files = [i for i in archive.infolist() if i.filename.lower().endswith(".pdf") and not i.is_dir()]
                if len(files) != 1 or files[0].file_size > 30 * 1024 * 1024:
                    raise ValueError("L'archive Yousign ne contient pas un contrat PDF unique.")
                content = archive.read(files[0])
        if not content.startswith(b"%PDF-"):
            raise ValueError("Yousign n'a pas retourné un PDF signé valide.")
        from pypdf import PdfReader
        try:
            if len(PdfReader(BytesIO(content)).pages) < 3:
                raise ValueError("PDF signé incomplet.")
        except Exception as exc:
            raise ValueError("Le PDF signé reçu est illisible ou incomplet.") from exc
        os.makedirs(self.directory, exist_ok=True)
        filename = f"convention_{contract['id']}_signee.pdf"
        with tempfile.NamedTemporaryFile(dir=self.directory, delete=False) as output:
            output.write(content)
            temp_name = output.name
        os.replace(temp_name, os.path.join(self.directory, filename))
        contract["signedFilename"] = filename

    def signed(self, id):
        data, dotation = self.find(id)
        contract = self.selected_contract(dotation)
        try:
            if not contract.get("signedFilename"):
                self.sync_record(contract)
            self.cache_signed(contract)
            self.save(data)
            return send_file(self.path(contract, signed=True), mimetype="application/pdf", as_attachment=True,
                             download_name="Convention_mise_a_disposition_signee.pdf", max_age=0)
        except (ValueError, YousignError, OSError, zipfile.BadZipFile) as exc:
            flash(f"Téléchargement impossible : {exc}", "error")
            return self.back(id)

    def webhook(self, payload):
        data_payload = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        sr = data_payload.get("signature_request") if isinstance(data_payload.get("signature_request"), dict) else {}
        srid = sr.get("id") or data_payload.get("signature_request_id") or payload.get("signature_request_id")
        signer = data_payload.get("signer") if isinstance(data_payload.get("signer"), dict) else {}
        signer_request = signer.get("signature_request") if isinstance(signer.get("signature_request"), dict) else {}
        srid = srid or signer_request.get("id")
        if not srid:
            return None
        # Most webhooks concern other modules. Avoid locking them unnecessarily.
        if not any((c.get("yousign") or {}).get("signatureRequestId") == srid for d in self.load() for c in self.records(d)):
            return None
        try:
            with self.transaction():
                data = self.load()
                for dotation in data:
                    for contract in self.records(dotation):
                        if (contract.get("yousign") or {}).get("signatureRequestId") != srid:
                            continue
                        self.sync_record(contract)
                        contract["yousign"]["lastWebhookAt"] = now()
                        self.save(data)
                        return {"ok": True, "target": "dotation"}
        except (BlockingIOError, ValueError, YousignError, OSError):
            # A non-2xx response asks Yousign to retry, rather than lose an event.
            return {"ok": False, "retry": True}, 503
        return None
