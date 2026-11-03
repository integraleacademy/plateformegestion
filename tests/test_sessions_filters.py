"""Dashboard links, counts and cards must describe the same subset."""
from datetime import date, timedelta
from html import unescape
import re

import pytest

import app


@pytest.fixture
def dashboard(monkeypatch):
    today = date.today()

    def session(sid, code, start, end, **extra):
        return dict(id=sid, formation=code, date_debut=start, date_fin=end,
                    date_exam="", jurys=[], steps=[], **extra)

    future = (today + timedelta(days=1)).strftime("%d/%m/%Y")
    yesterday = (today - timedelta(days=1)).isoformat()
    rows = [
        session("starts-ends-today", "A3P", today.isoformat(), today.isoformat()),
        session("future", "A3P", future, future),
        session("past", "A3P", yesterday, yesterday),
        session("manual-archive", "A3P", future, future, archived=True),
        session("other-course", "APS", future, future),
        session("incomplete", "A3P", "", ""),
    ]
    monkeypatch.setattr(app, "load_sessions", lambda: {"sessions": rows})
    client = app.app.test_client()
    with client.session_transaction() as auth:
        auth.update(admin_logged=True, admin_session_version=app.ADMIN_SESSION_VERSION)
    return client


@pytest.mark.parametrize("status,expected", [
    ("toutes", {"starts-ends-today", "future", "past", "manual-archive", "incomplete"}),
    ("en-cours", {"starts-ends-today"}), ("a-venir", {"future"}),
    ("terminees", {"past", "manual-archive"}),
])
def test_combined_filters_match_cards_and_selected_total(dashboard, status, expected):
    response = dashboard.get("/sessions", query_string={"formation": "A3P", "statut": status})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert set(re.findall(r'data-session-id="([^"]+)"', html)) == expected
    selected = re.search(r'<a class="metric[^"]*" data-state="[^"]+"[^>]* aria-current="true">(.*?)</a>', html, re.S)
    assert f'<strong class="metric-value">{len(expected)}</strong>' in selected[1]
    assert 'href="/sessions?formation=A3P&amp;statut=a-venir#selection-sessions"' in html


def test_status_then_course_link_preserves_status_and_shows_empty_result(dashboard):
    html = dashboard.get("/sessions?statut=en-cours").get_data(as_text=True)
    link = re.search(r'<a class="chip" data-code="APS" href="([^"]+)"', html)
    empty = dashboard.get(unescape(link[1])).get_data(as_text=True)
    assert 'Aucune session pour cette sélection' in empty
    assert 'data-session-id="' not in empty
    assert 'Effacer les filtres' in empty


def test_unfiltered_dashboard_includes_sessions_with_incomplete_dates(dashboard):
    html = dashboard.get("/sessions").get_data(as_text=True)
    assert len(re.findall(r'data-session-id="', html)) == 6
    assert 'Dates à compléter' in html
