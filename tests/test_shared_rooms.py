"""Projection safety and durable reservation guards for every session writer."""
from copy import deepcopy
import json
import sqlite3

import pytest
from services import shared_rooms as rooms
from services.session_storage import load_session_store, save_session_store, SessionStorageConflict


def source():
    return dict(id='aps', formation='APS', date_debut='2027-01-04', date_fin='2027-01-05',
                salle='Centre de formation, adresse', sharedRoom=dict(room_id='r1'),
                apsPlanningData=[dict(date='2027-01-04', slots=[dict(start='09:00', end='12:00', modality='presentiel'),
                    dict(start='13:00',end='15:00',modality='elearning')])])


def test_only_actual_in_person_timetable_not_drafts_or_personal_data():
    s = source(); s['stagiaires']=[dict(nom='PRIVATE',email='secret@example.test')]
    s['a3pPlanningEditorDraft']=[dict(date='2027-09-01',slots=[])]
    p=rooms.projection(s)
    assert p['slots']==[dict(date='2027-01-04',start='09:00',end='12:00',room_id='r1')]
    assert 'PRIVATE' not in json.dumps(p) and 'email' not in json.dumps(p)
    s['stagiaires'].append(dict(nom='Other'))
    assert rooms.projection(s)['revision']==p['revision']
    s['apsPlanningData'][0]['slots'][0]['end']='13:00'
    assert rooms.projection(s)['revision']!=p['revision']


def test_address_is_unassigned_and_existing_named_room_uses_conservative_all_days():
    s=source(); s.pop('sharedRoom'); s.pop('apsPlanningData')
    assert rooms.projection(s)['slots']==[]
    s['salle']='Salle 1'
    p=rooms.projection(s)
    assert len(p['slots'])==2
    assert all(slot['start']=='00:00' and slot['end']=='24:00' for slot in p['slots'])


def test_explicit_fallback_weekdays_and_times():
    s=source(); s.pop('apsPlanningData');s['sharedRoom']=dict(room_id='r2',start='08:30',end='16:00',weekdays=[1])
    assert rooms.projection(s)['slots']==[dict(date='2027-01-05',start='08:30',end='16:00',room_id='r2')]


@pytest.fixture
def linked(monkeypatch):
    monkeypatch.setenv('SHARED_ROOMS_TOKEN','test');monkeypatch.setenv('BTS_ROOMS_URL','https://bts.test')


def store(tmp_path):
    path=tmp_path/'sessions.json';save_session_store(path,dict(sessions=[source()],jurys=[]));return path


def test_prepare_before_durable_save_finish_after_and_unchanged_personal_edit_offline(linked, monkeypatch, tmp_path):
    path=store(tmp_path);calls=[]
    def call(action,data):
        persisted=json.loads(path.read_text())['sessions'][0]['sharedRoom']['room_id']
        calls.append((action,persisted,data));return dict(token='hold')
    monkeypatch.setattr(rooms,'call',call)
    data=load_session_store(path);data['sessions'][0]['sharedRoom']['room_id']='r2'
    save_session_store(path,data,reservation_guard=rooms.session_guard)
    assert [(a,r) for a,r,_ in calls]==[('prepare','r1'),('finish','r2')]
    assert calls[-1][2]['commit'] is True
    calls.clear();data=load_session_store(path);data['sessions'][0]['notes']='Sans changement d’horaires'
    save_session_store(path,data,reservation_guard=rooms.session_guard)
    assert not calls


def test_conflict_prevents_any_source_write(linked,monkeypatch,tmp_path):
    path=store(tmp_path);original=path.read_bytes()
    def deny(*args):raise rooms.RoomError('Salle déjà prise')
    monkeypatch.setattr(rooms,'call',deny)
    data=load_session_store(path);data['sessions'][0]['sharedRoom']['room_id']='r2'
    with pytest.raises(rooms.RoomError):save_session_store(path,data,reservation_guard=rooms.session_guard)
    assert path.read_bytes()==original


def test_failed_finish_preserves_durable_save_and_does_not_abort(linked,monkeypatch,tmp_path):
    path=store(tmp_path);calls=[]
    def call(action,data):
        calls.append((action,data))
        if action=='finish':raise rooms.RoomError('Network')
        return dict(token='pending')
    monkeypatch.setattr(rooms,'call',call)
    data=load_session_store(path);data['sessions'][0]['sharedRoom']['room_id']='r2'
    save_session_store(path,data,reservation_guard=rooms.session_guard)
    assert load_session_store(path)['sessions'][0]['sharedRoom']['room_id']=='r2'
    assert all(d.get('commit') is not False for _,d in calls)


def test_failed_disk_keeps_holds_for_reconciliation(linked,monkeypatch,tmp_path):
    path=store(tmp_path);calls=[]
    monkeypatch.setattr(rooms,'call',lambda action,data:calls.append((action,data)) or dict(token='pending'))
    from services import session_storage
    monkeypatch.setattr(session_storage,'_atomic_write',lambda *a:(_ for _ in ()).throw(OSError('disk')))
    data=load_session_store(path);data['sessions'][0]['sharedRoom']['room_id']='r2'
    with pytest.raises(OSError):save_session_store(path,data,reservation_guard=rooms.session_guard)
    assert [a for a,_ in calls]==['prepare']


def test_stale_writer_cannot_even_prepare(linked,monkeypatch,tmp_path):
    path=store(tmp_path);first=load_session_store(path);stale=load_session_store(path)
    first['sessions'][0]['notes']='New';save_session_store(path,first)
    monkeypatch.setattr(rooms,'call',lambda *a:pytest.fail('A stale writer must not call the ledger'))
    stale['sessions'][0]['sharedRoom']['room_id']='r2'
    with pytest.raises(SessionStorageConflict):save_session_store(path,stale,reservation_guard=rooms.session_guard)


def test_old_planner_is_isolated_from_the_shared_registry(linked,monkeypatch,tmp_path):
    conn=sqlite3.connect(tmp_path/'formations.db');conn.row_factory=sqlite3.Row
    conn.execute('CREATE TABLE formations(id INTEGER PRIMARY KEY,nom TEXT,type TEXT,date_debut TEXT,date_fin TEXT,salle TEXT,nombre_stagiaires INT,commentaire TEXT,created_at TEXT,shared_room_id TEXT)')
    calls=[]
    def call(action,data):
        calls.append((action,conn.in_transaction));return dict(token='hold')
    monkeypatch.setattr(rooms,'call',call)
    from services.legacy_planning_storage import save_formation
    fid=save_formation(conn,dict(nom='APS',type='APS',date_debut='2027-01-04',date_fin='2027-01-05',salle='Salle 1',nombre_stagiaires=4,commentaire='',created_at='now'))
    assert calls==[]
    current=dict(conn.execute('SELECT * FROM formations WHERE id=?',(fid,)).fetchone())
    with pytest.raises(SessionStorageConflict):save_formation(conn,dict(current,salle='Salle 2'),fid,expected=dict(current,nom='stale'))
    conn.rollback()
    assert conn.execute('SELECT salle FROM formations').fetchone()[0]=='Salle 1'


@pytest.fixture
def api(linked,monkeypatch,tmp_path):
    from flask import Flask
    path=store(tmp_path)
    legacy=tmp_path/'formations.db'
    with sqlite3.connect(legacy) as conn:
        conn.execute('CREATE TABLE formations(id INTEGER,nom TEXT,salle TEXT)')
        conn.execute("INSERT INTO formations VALUES(3,'BTS MOS - ancien planning','Salle 1B')")
    calls=[]
    def ledger(action,data):
        calls.append((action,deepcopy(data)))
        return dict(ok=True,token='hold',count=len(data.get('owners',[])),scope='sessions',excluded_owners=0)
    monkeypatch.setattr(rooms,'call',ledger)
    app=Flask('shared-room-tests');app.config['TESTING']=True
    rooms.register(app,lambda:load_session_store(path),
                   lambda data:save_session_store(path,data,reservation_guard=rooms.session_guard),str(path))
    return app.test_client(),path,legacy,calls


def test_api_lists_and_reconciles_only_actual_sessions(api):
    client,path,legacy,calls=api;before=legacy.read_bytes()
    data=load_session_store(path)
    revision=rooms.projection(data['sessions'][0])['revision']
    data['sessions'][0]['display_name']='APS JANVIER 2027'
    save_session_store(path,data)
    result=client.get('/api/shared-rooms/sessions',headers={'Authorization':'Bearer test'})
    assert result.status_code==200,result.json
    assert result.json['source']=='sessions'
    assert [s['owner'] for s in result.json['sessions']]==['session:aps']
    assert result.json['sessions'][0]['name']=='APS JANVIER 2027'
    assert result.json['sessions'][0]['revision']!=revision
    assert result.json['sessions'][0]['title']=='APS JANVIER 2027'
    assert calls[0][1]['owners'][0]['legacy_revision']==rooms.projection_v1(source())['revision']
    assert 'legacy' not in result.json['sessions'][0]
    assert len(calls)==1 and calls[0][0]=='reconcile'
    assert [s['owner'] for s in calls[0][1]['owners']]==['session:aps']
    assert legacy.read_bytes()==before


def test_bootstrap_ignores_old_planner_and_its_room_catalogue(api):
    client,path,legacy,calls=api
    result=client.post('/api/shared-rooms/bootstrap',headers={'Authorization':'Bearer test'})
    assert result.status_code==200 and result.json['count']==1
    assert [s['owner'] for s in calls[0][1]['owners']]==['session:aps']
    assert 'room_names' not in calls[0][1]


def test_api_rejects_old_formation_reassignment_without_any_write(api):
    client,path,legacy,calls=api;before=path.read_bytes();old=legacy.read_bytes()
    result=client.post('/api/shared-rooms/sessions',json=dict(owner='formation:3',room_id='r2',revision='0'*64),headers={'Authorization':'Bearer test'})
    assert result.status_code==400
    assert path.read_bytes()==before and legacy.read_bytes()==old and not calls


def test_actual_session_assignment_still_uses_atomic_guard(api):
    client,path,legacy,calls=api;revision=rooms.projection(source())['revision']
    result=client.post('/api/shared-rooms/sessions',json=dict(owner='session:aps',room_id='r2',revision=revision),headers={'Authorization':'Bearer test'})
    assert result.status_code==200,result.json
    assert [c[0] for c in calls]==['prepare','finish']
    assert calls[0][1]['owner']=='session:aps'
    assert load_session_store(path)['sessions'][0]['sharedRoom']['room_id']=='r2'


def test_machine_routes_remain_private(api):
    client,_,_,calls=api
    assert client.get('/api/shared-rooms/sessions').status_code==403
    assert client.post('/api/shared-rooms/bootstrap').status_code==403
    assert not calls


def test_actual_presence_excludes_initial_remote_days_and_declared_exam_is_reserved():
    s=source();s['display_name']='APS JANVIER 2027';s['date_debut']='2026-12-01';s['date_exam']='2027-01-09'
    s['apsPlanningData'].insert(0,dict(date='2026-12-01',modality='elearning',slots=[dict(start='08:00',end='12:00')]))
    p=rooms.projection(s)
    assert p['metadata']['start']=='2027-01-04' and p['metadata']['formation_start']=='2026-12-01'
    assert p['metadata']['exam_full_day']==['2027-01-09']
    assert p['title']=='APS JANVIER 2027'
    assert {r['date'] for r in p['slots']}=={'2027-01-04','2027-01-09'}
    assert next(r for r in p['slots'] if r['date']=='2027-01-09')==dict(room_id='r1',date='2027-01-09',start='00:00',end='24:00')
    assert p['schema']==2 and p['legacy_revision']==rooms.projection_v1(s)['revision']


def test_exam_known_times_and_embedded_exam_are_not_full_day_or_duplicated():
    s=source();s.update(date_exam='2027-01-09',exam_date='2027-01-10',exam_start_time='08:30',exam_end_time='16:00')
    p=rooms.projection(s)
    assert p['metadata']['exam_dates']==['2027-01-09'] and p['metadata']['exam_full_day']==[]
    exam=next(r for r in p['slots'] if r['date']=='2027-01-09');assert exam['start']=='08:30' and exam['end']=='16:00'
    s['apsPlanningData'].append(dict(date='2027-01-09',slots=[dict(start='09:00',end='12:00',modality='presentiel',uv='UV1',category='EXAM_APS')]))
    p=rooms.projection(s)
    exams=[r for r in p['slots'] if r['date']=='2027-01-09']
    assert len(exams)==1 and exams[0]['start']=='09:00'
    assert p['metadata']['end']=='2027-01-04'


def test_declared_exam_not_suppressed_by_training_on_same_day():
    s=source();s['date_exam']='2027-01-04';p=rooms.projection(s)
    assert any(r['start']=='00:00' and r['end']=='24:00' for r in p['slots'])


def test_desp_presence_fallback_and_weekend_exam_outside_range():
    s=source();s.pop('apsPlanningData');s.update(formation='DIRIGEANT',date_debut='2026-12-01',date_fin='2027-01-08',despPresentielStart='2027-01-04',date_exam='2027-01-09')
    p=rooms.projection(s)
    assert p['metadata']['formation']=='DESP' and p['metadata']['start']=='2027-01-04'
    assert min(r['date'] for r in p['slots'])=='2027-01-04'
    assert max(r['date'] for r in p['slots'])=='2027-01-09'


def test_unknown_mixed_presence_is_not_reported_as_formation_start():
    s=source();s.pop('apsPlanningData');s['apsPlanningMode']='elearning_presentiel'
    assert rooms.projection(s)['metadata']['start'] is None
    s['apsPlanningMode']='full_presentiel';assert rooms.projection(s)['metadata']['start']==s['date_debut']


def test_global_assignment_has_reset_marker_and_previous_projection(api):
    client,path,legacy,calls=api;before=rooms.projection(source())
    response=client.post('/api/shared-rooms/sessions',json=dict(owner=before['owner'],revision=before['revision'],room_id='r2'),headers={'Authorization':'Bearer test'})
    assert response.status_code==200,response.json
    prepared=calls[0][1]
    assert prepared['previous_projection']==before and prepared['metadata']['assignment']
    assert prepared['metadata']['assignment']==load_session_store(path)['sessions'][0]['sharedRoom']['assignment']
