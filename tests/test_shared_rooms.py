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


def test_legacy_updates_use_same_guard_and_hold_lock_until_commit(linked,monkeypatch,tmp_path):
    conn=sqlite3.connect(tmp_path/'formations.db');conn.row_factory=sqlite3.Row
    conn.execute('CREATE TABLE formations(id INTEGER PRIMARY KEY,nom TEXT,type TEXT,date_debut TEXT,date_fin TEXT,salle TEXT,nombre_stagiaires INT,commentaire TEXT,created_at TEXT,shared_room_id TEXT)')
    calls=[]
    def call(action,data):
        calls.append((action,conn.in_transaction));return dict(token='hold')
    monkeypatch.setattr(rooms,'call',call)
    fid=rooms.save_formation(conn,dict(nom='APS',type='APS',date_debut='2027-01-04',date_fin='2027-01-05',salle='Salle 1',nombre_stagiaires=4,commentaire='',created_at='now'))
    assert calls==[('prepare',True),('finish',False)]
    current=dict(conn.execute('SELECT * FROM formations WHERE id=?',(fid,)).fetchone())
    with pytest.raises(rooms.RoomError):rooms.save_formation(conn,dict(current,salle='Salle 2'),fid,expected=dict(current,nom='stale'))
    conn.rollback()
    assert conn.execute('SELECT salle FROM formations').fetchone()[0]=='Salle 1'
