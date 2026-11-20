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
    assert 'Créer un visuel' not in html
    assert '/social-post/new' not in html
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


@pytest.mark.parametrize(('states', 'label', 'tone'), [
    ([], 'Jurys 0/2 présents', 'session-alert'),
    (['present', 'absent', 'pending'], 'Jurys 1/2 présents', 'session-alert'),
    (['present', 'present', 'absent'], 'Jurys 2/2 présents', 'jury-complete'),
    (['present'] * 3, 'Jurys 3 présents (2 attendus)', 'jury-complete'),
])
def test_jury_badge_on_cards_overview_and_jury_tab(monkeypatch, states, label, tone):
    row = dict(id='jury-check', formation='APS', date_debut='2099-01-04',
               date_fin='2099-02-08', date_exam='2099-02-09', steps=[],
               jury_notification_status='notified' if states else 'to_notify',
               jurys=[dict(id=str(i), status=st, notified_at='2026-11-20') for i, st in enumerate(states)])
    monkeypatch.setattr(app, 'load_sessions', lambda: dict(sessions=[row], jurys=[]))
    monkeypatch.setattr(app, 'save_sessions', lambda data: None)
    with app.app.test_client() as client:
        with client.session_transaction() as auth:
            auth.update(admin_logged=True, admin_session_version=app.ADMIN_SESSION_VERSION)
        for path, occurrences in [('/sessions?statut=a-venir', 1), ('/sessions/jury-check', 2)]:
            response = client.get(path)
            assert response.status_code == 200
            html = response.get_data(as_text=True)
            assert html.count(f'class="jury-presence {tone}"') == occurrences
            assert html.count(f'<span>{label}</span>') == occurrences
            assert f'Absents : {states.count("absent")}' in html
            assert f'En attente de réponse : {states.count("pending")}' in html


@pytest.mark.parametrize(('formation', 'name', 'statuses', 'label'), [
    ('SSIAP1', '', ['pending', 'absent'], '0/1 présent'),
    ('SSIAP', 'SSIAP 1 novembre', ['present', 'pending'], 'Jury complet · 1/1 présent'),
    ('SSIAP 1', '', ['present', 'present'], 'Jury complet · 2 présents (1 attendu)'),
    ('SSIAP', 'SSIAP 2 novembre', ['present'], 'Jurys 1/2 présents'),
    ('SSIAP3', '', ['present'], 'Jurys 1/2 présents'),
])
def test_ssiap_jury_threshold(formation, name, statuses, label):
    row = dict(formation=formation, display_name=name, jurys=[dict(status=s) for s in statuses])
    with app.app.test_request_context():
        badge = app.app.jinja_env.get_template('session_visuals.html').module.jury_presence(row)
    assert label in badge
    assert ('jury-complete' in badge) == label.startswith('Jury complet')
    assert ('Jury à notifier' in badge) != label.startswith('Jury complet')


def test_afc_ssiap_jury_is_complete_while_aps_still_needs_another_member(monkeypatch):
    member = dict(id='j', status='present')
    row = dict(id='afc', formation='AFC_APS_SSIAP', date_debut='2099-01-04', date_fin='2099-03-01',
               date_exam='2099-03-01', steps=[], jurys=[],
               afc_exam_jurys={'aps': [dict(member)], 'ssiap1': [dict(member)]})
    monkeypatch.setattr(app, 'load_sessions', lambda: dict(sessions=[row], jurys=[]))
    monkeypatch.setattr(app, 'save_sessions', lambda data: None)
    with app.app.test_client() as client:
        with client.session_transaction() as auth:
            auth.update(admin_logged=True, admin_session_version=app.ADMIN_SESSION_VERSION)
        for path, count in [('/sessions?statut=a-venir', 1), ('/sessions/afc', 2)]:
            response = client.get(path)
            assert response.status_code == 200
            html = response.get_data(as_text=True)
            assert html.count('Jury complet · 1/1 présent') == count
            assert html.count('Jurys 1/2 présents') == count
            assert html.count('class="jury-presence jury-complete"') == count
