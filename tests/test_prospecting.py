import io

import pytest

import prospecting
from app import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    app.config.update(TESTING=True, SECRET_KEY="test")
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["admin_logged"] = True
        yield client


def test_scoring_rewards_ape_recency_qualiopi_and_contact():
    score, signal = prospecting.score_prospect({
        "name": "Centre de formation sécurité SSIAP",
        "signal": "Formation agent de sécurité et APS",
        "ape_code": "85.59A",
        "company_created_at": prospecting.date.today().isoformat(),
        "qualiopi": True,
        "email": "contact@example.fr",
        "phone": "0102030405",
        "website": "https://example.fr",
    })
    assert score == 100
    assert "APE 8559A" in signal
    assert "Qualiopi" in signal


def test_admin_crud_mail_and_excel_export(client):
    with app.app_context():
        prospecting.init_prospect_db()
        prospecting._upsert(prospecting._candidate({
            "nom": "Sécurité Formation Test",
            "siret": "12345678900012",
            "ville": "Paris",
            "code_postal": "75001",
            "ape": "85.59A",
            "email": "contact@example.fr",
            "qualiopi": "oui",
        }, "Test"))

    response = client.get("/cron-prospects-scan")
    assert response.status_code == 401

    response = client.get("/admin")
    assert response.status_code == 200
    assert "Sécurité Formation Test" in response.get_data(as_text=True)

    response = client.get("/admin/prospects/1/mail")
    assert response.status_code == 200
    assert "Intégrale Academy" in response.get_data(as_text=True)

    response = client.post("/admin/prospects/1/contacted", follow_redirects=True)
    assert "Contacté" in response.get_data(as_text=True)

    response = client.get("/admin/export.xlsx")
    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(io.BytesIO(response.data).getvalue()) > 1000
