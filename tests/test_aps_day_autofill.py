"""Exercise the browser allocator against the real APS validator and save API."""
from copy import deepcopy
from datetime import date
import json
import subprocess

import pytest
import app


@pytest.mark.parametrize('mode', ['full_presentiel', 'elearning_presentiel'])
def test_recreated_day_restores_a_complete_plan_and_survives_save_and_reload(monkeypatch, mode):
    original, _, _ = app.build_aps_planning_data(date(2026, 9, 1), 'Formateur', 'Salle', mode)
    original = app.normalize_aps_slot_durations(original)
    target = next(day for day in original[3:] if day['slots'][0].get('modality', 'presentiel') == 'presentiel')
    incomplete = deepcopy(original)
    incomplete.remove(next(day for day in incomplete if day['date'] == target['date']))
    morning = [slot for slot in target['slots'] if slot['start'] < '12:30']
    afternoon = [slot for slot in target['slots'] if slot['start'] >= '13:30']
    fields = {'date': target['date'], 'modality': 'presentiel', 'room': 'Salle',
              'morning': {'start': morning[0]['start'], 'end': morning[-1]['end']} if morning else None,
              'afternoon': {'start': afternoon[0]['start'], 'end': afternoon[-1]['end']} if afternoon else None}
    process = subprocess.run(['node', '-e', '''
      const planner = require('./static/js/aps-day-planner.js');
      const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
      process.stdout.write(JSON.stringify(planner.fill(planner.createDay(input.plan, input.fields), input.contents)));
    '''], input=json.dumps({'plan': incomplete, 'fields': fields, 'contents': app.aps_expected_content(mode)}),
        text=True, capture_output=True, check=True)
    result = json.loads(process.stdout)
    assert result['remainingMinutes'] == 0
    assert result['addedMinutes'] == sum(slot['durationMinutes'] for slot in target['slots'])
    record = {'id': 'day-autofill', 'formation': 'APS', 'apsPlanningMode': mode, 'apsPlanningData': incomplete}
    data = {'sessions': [record], 'jurys': []}
    saves = []
    monkeypatch.setattr(app, 'load_sessions', lambda: data)
    monkeypatch.setattr(app, 'save_sessions', lambda value: saves.append(deepcopy(value)))
    app.app.config.update(TESTING=True, SECRET_KEY='test')
    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session['admin_logged'] = True
            session['admin_session_version'] = app.ADMIN_SESSION_VERSION
        response = client.put('/api/sessions/day-autofill/aps-planning', json={'planningData': result['planning']})
        assert response.status_code == 200, response.get_json()
        refreshed = client.get('/api/sessions/day-autofill/aps-planning').get_json()
    assert refreshed['curriculum']['remainingMinutes'] == 0
    assert refreshed['compliance']['ok'] is True, refreshed['compliance']['errors']
    assert len(saves) == 1
    for unchanged in incomplete:
        restored = next(day for day in refreshed['apsPlanningData'] if day['date'] == unchanged['date'])
        assert restored == unchanged
