import pytest

import app


@pytest.mark.parametrize(('start', 'end', 'expected'), [
    ('2027-01-04', '2027-01-13', '4 – 13 janv. 2027'),
    ('14/01/2027', '08/02/2027', '14 janv. – 8 févr. 2027'),
    ('2026-12-28', '2027-01-05', '28 déc. 2026 – 5 janv. 2027'),
    ('2027-02-09', None, '9 févr. 2027'),
    (None, None, '—'),
])
def test_calendar_spans_keep_exact_dates(start, end, expected):
    assert app.session_calendar_span(start, end) == expected


@pytest.mark.parametrize(('formation', 'sections', 'absent'), [
    ('APS', ('steps-section', 'aps-attendance-section', 'aps-contracts-section'), ('afc-dsf-section',)),
    ('A3P', ('a3p-contracts-section',), ('aps-contracts-section',)),
    ('AFC_APS_SSIAP', ('afc-dsf-section', 'aps-attendance-section'), ('steps-section',)),
    ('GENERAL', ('steps-section', 'jury-section'), ('aps-attendance-section', 'aps-contracts-section')),
])
def test_detail_links_match_available_panels(monkeypatch, formation, sections, absent):
    row = dict(id='sheet', formation=formation, date_debut='2027-01-04',
               date_fin='2027-02-08', date_exam='2027-02-09', steps=[], jurys=[])
    monkeypatch.setattr(app, 'load_sessions', lambda: dict(sessions=[row], jurys=[]))
    monkeypatch.setattr(app, 'save_sessions', lambda data: None)
    with app.app.test_client() as client:
        with client.session_transaction() as auth:
            auth.update(admin_logged=True, admin_session_version=app.ADMIN_SESSION_VERSION)
        response = client.get('/sessions/sheet')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for panel in ('session-overview', 'planning-section', *sections):
        assert f'href="#{panel}" data-sheet-link="{panel}"' in html
        assert f'id="{panel}" data-sheet-panel="{panel}"' in html
    for panel in absent:
        assert f'data-sheet-link="{panel}"' not in html


@pytest.mark.parametrize(('state', 'expected'), [
    ('missing', True), ('draft', True), ('expired', True),
    ('ongoing', False), ('signed', False),
])
def test_contract_alert_only_when_action_is_needed(state, expected):
    row = {'formation': 'APS'}
    if state != 'missing':
        row['apsTrainerContracts'] = [{'id':'c1', 'trainerName':'Test', 'yousign':{'status':state}}]
    assert app.session_trainer_contract_summary(row)['action_required'] is expected


def test_edit_inputs_use_saved_dates_in_both_formats():
    assert app.session_input_date('03/11/2026') == '2026-11-03'
    assert app.session_input_date('2026-12-09') == '2026-12-09'
    assert app.session_input_date('') == ''
