from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

import app
from services.aps_pdf_presentation import (
    APS_CONTRACT_PRESENTATION_VERSION, contract_interventions_for_pdf, contract_module_labels,
)


def intervention(start, end, hours, module="UV3 Analyse et résolution des conflits - Apports théoriques en présentiel", **extra):
    return {"date": "2026-11-18", "dateLabel": "18/11/2026", "start": start, "end": end,
            "hours": hours, "module": module, "modality": "Présentiel", "room": "Salle 1", **extra}


def contract_data():
    return {"id": "simple-contract", "trainerName": "Rachid EL MEHERZI", "pdfFilename": "existing.pdf",
            "calculatedHours": 7, "calculatedDays": 1, "billedDays": 1, "dailyRate": 250,
            "totalHT": 250, "totalTTC": 250, "yousign": {"status": "draft"},
            "interventions": [
                intervention("08:30", "09:30", 1, "UV2 Mise en œuvre du livre VI - Apports théoriques en présentiel"),
                intervention("09:30", "11:30", 2),
                intervention("13:30", "15:30", 2),
                intervention("15:30", "16:30", 1, "UV3 Gestion des conflits - Mise en situation pratique"),
                intervention("16:30", "17:30", 1, "UV3 Gestion des conflits - Mise en situation pratique"),
            ]}


def session_data():
    return {"id": "simple-aps", "formation": "APS", "display_name": "APS NOVEMBRE 2026",
            "date_debut": "2026-11-03", "date_fin": "2026-12-08", "date_exam": "2026-12-09"}


def test_saved_sequences_become_the_same_simple_blocks_as_the_planning_without_changing_hours():
    source = contract_data()["interventions"]
    before = deepcopy(source)
    rows = contract_interventions_for_pdf(source)
    assert len(rows) == 3
    assert rows[-1]["module"] == "UV 3 - Module Gestion des conflits"
    assert (rows[-1]["start"], rows[-1]["end"], rows[-1]["hours"]) == ("13:30", "17:30", 4)
    assert sum(row["hours"] for row in rows) == sum(row["hours"] for row in source) == 7
    assert source == before
    assert contract_interventions_for_pdf(rows) == rows


@pytest.mark.parametrize("change", [
    {"date": "2026-11-19"}, {"start": "15:45"}, {"room": "Salle 2"},
    {"modality": "E-learning"}, {"trainer": "Autre"}, {"part": "Autre période"},
    {"module": "UV4 Stratégique"}, {"module": "UV30 Module spécifique"},
])
def test_blocks_do_not_cross_dates_breaks_rooms_modalities_or_modules(change):
    rows = [intervention("13:30", "15:30", 2), intervention("15:30", "16:30", 1)]
    rows[1].update(change)
    assert len(contract_interventions_for_pdf(rows)) == 2


def test_module_list_has_one_simple_label_per_uv_in_numeric_order():
    rows = [intervention("08:30", "09:30", 1, label) for label in
            ["UV10 Ancien titre", "UV 2 - Autre titre", "UV1", "UV2 Pratique", "UV14 Industriel", "Accueil spécifique"]]
    labels = contract_module_labels(contract_interventions_for_pdf(rows))
    assert labels == ["UV 1 - Module Secourisme", "UV 2 - Module Environnement juridique",
                      "UV 10 - Module Surveillance par moyens électroniques de sécurité",
                      "UV 14 - Module Industriel spécifique", "Accueil spécifique"]


def test_pdf_simplifies_both_the_mission_and_the_annex_and_preserves_the_contract(tmp_path):
    contract = contract_data()
    before = deepcopy(contract)
    path = tmp_path / "contract.pdf"
    app.generate_aps_trainer_contract_pdf(session_data(), contract, str(path))
    text = "\n".join(page.extract_text() for page in PdfReader(path).pages)
    mission = text.split("Modules / UV confiés", 1)[1].split("Volume horaire formation", 1)[0]
    assert mission.count("UV 3 - Module Gestion des conflits") == 1
    assert mission.index("UV 2") < mission.index("UV 3")
    assert "13:30 - 17:30" in text
    assert "15:30 - 16:30" not in text
    assert "Apports théoriques" not in text
    assert "Mise en situation pratique" not in text
    assert "250,00 €" in text
    assert "Fait à Puget-sur-Argens, le 27/10/2026." in text
    assert contract == before


def test_opening_existing_unsigned_contract_refreshes_pdf_once_and_keeps_financial_snapshot(monkeypatch, tmp_path):
    contract = contract_data()
    before = deepcopy(contract)
    record = {**session_data(), "apsTrainerContracts": [contract]}
    data = {"sessions": [record], "jurys": []}
    path = tmp_path / contract["pdfFilename"]
    path.write_bytes(b"Old detailed PDF")
    monkeypatch.setattr(app, "APS_CONTRACT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "load_sessions", lambda: data)
    monkeypatch.setattr(app, "save_sessions", lambda value: None)
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    with app.app.test_client() as client:
        with client.session_transaction() as auth:
            auth["admin_logged"] = True
            auth["admin_session_version"] = app.ADMIN_SESSION_VERSION
        url = "/sessions/simple-aps/aps-trainer-contracts/simple-contract/view"
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert "UV 3 - Module Gestion des conflits" in "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.data)).pages)
        assert contract == {**before, "pdfPresentationVersion": APS_CONTRACT_PRESENTATION_VERSION}
        def fail_generate(*args):
            raise AssertionError("An up-to-date PDF must be reused")
        monkeypatch.setattr(app, "generate_session_trainer_contract_pdf", fail_generate)
        assert client.get(url).data == response.data


@pytest.mark.parametrize("signature", [
    {"yousign": {"signatureRequestId": "request-1", "status": "ongoing"}},
    {"yousign": {"status": "signed"}}, {"yousign": {"status": "done"}},
    {"yousign": {"signedDocumentFilename": "signed.pdf"}},
    {"yousign_signature_request_id": "legacy-request"}, {"yousign_status": "signed"},
])
def test_existing_signed_or_requested_contract_is_not_rewritten(monkeypatch, tmp_path, signature):
    contract = {**contract_data(), **signature}
    original = deepcopy(contract)
    path = tmp_path / contract["pdfFilename"]
    path.write_bytes(b"Original signature version")
    monkeypatch.setattr(app, "APS_CONTRACT_DIR", str(tmp_path))
    def fail_generate(*args):
        raise AssertionError("Signature version must be preserved")
    monkeypatch.setattr(app, "generate_session_trainer_contract_pdf", fail_generate)
    assert app.ensure_aps_trainer_contract_pdf(session_data(), contract) == str(path)
    assert path.read_bytes() == b"Original signature version"
    assert contract == original


def test_failed_refresh_preserves_original_pdf_and_does_not_mark_it_up_to_date(monkeypatch, tmp_path):
    contract = contract_data()
    original = deepcopy(contract)
    path = tmp_path / contract["pdfFilename"]
    path.write_bytes(b"Original PDF")
    monkeypatch.setattr(app, "APS_CONTRACT_DIR", str(tmp_path))
    def fail_generate(session, data, output_path):
        Path(output_path).write_bytes(b"Partial PDF")
        raise RuntimeError("Rendering failed")
    monkeypatch.setattr(app, "generate_aps_trainer_contract_pdf", fail_generate)
    with pytest.raises(RuntimeError, match="Rendering failed"):
        app.ensure_aps_trainer_contract_pdf(session_data(), contract)
    assert path.read_bytes() == b"Original PDF"
    assert list(tmp_path.iterdir()) == [path]
    assert contract == original


@pytest.mark.parametrize("formation", ["SSIAP1", "A3P", "DESP"])
def test_shared_renderer_does_not_apply_aps_module_names_to_other_trainings(tmp_path, formation):
    contract = contract_data()
    contract["interventions"] = [intervention("13:30", "16:30", 3, "UV1 Contenu spécifique autre formation")]
    path = tmp_path / f"{formation}.pdf"
    app.generate_aps_trainer_contract_pdf({**session_data(), "formation": formation}, contract, str(path))
    text = "\n".join(page.extract_text() for page in PdfReader(path).pages)
    assert "Contenu spécifique autre formation" in text
    assert "Module Secourisme" not in text
