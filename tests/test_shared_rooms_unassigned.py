"""Roomless actual sessions are projected without creating artificial schedules."""
from copy import deepcopy
import json

import pytest
from services import shared_rooms as rooms
from services.session_storage import load_session_store, save_session_store
from test_shared_rooms import source, linked, api


def unassigned():
    row=source();row.pop('sharedRoom');row['display_name']='APS JANVIER 2027'
    return row


def test_real_roomless_presence_and_exam_are_published_remote_and_drafts_excluded():
    s=unassigned();s.update(date_exam='2027-01-09',stagiaires=[{'nom':'PRIVATE'}],a3pPlanningEditorDraft=[{'date':'2027-02-01'}])
    s['apsPlanningData'].insert(0,dict(date='2026-12-01',modality='remote',slots=[dict(start='08:00',end='12:00')]))
    p=rooms.projection(s)
    assert p['slots']==[dict(date='2027-01-04',start='09:00',end='12:00',room_id=None),dict(date='2027-01-09',start='00:00',end='24:00',room_id=None)]
    assert p['metadata']['start']=='2027-01-04' and not p['metadata']['needs_schedule']
    assert p['metadata']['exam_full_day']==['2027-01-09']
    assert 'PRIVATE' not in json.dumps(p) and '2027-02-01' not in json.dumps(p)
    assert rooms.projection_v2(s)['slots']==[]


def test_partial_room_mapping_keeps_assigned_slots_and_single_embedded_exam():
    s=unassigned();s['apsPlanningData'][0]['slots'][0]['room']='Salle 1'
    s['apsPlanningData'].append(dict(date='2027-01-05',slots=[dict(start='09:00',end='12:00',category='EXAM_APS')]))
    s['date_exam']='2027-01-05'
    p=rooms.projection(s)
    assert p['slots']==[dict(date='2027-01-04',start='09:00',end='12:00',room_name='Salle 1'),dict(date='2027-01-05',start='09:00',end='12:00',room_id=None)]
    assert p['metadata']['exam_dates']==['2027-01-05'] and not p['metadata']['exam_full_day']


def test_unknown_schedule_appears_as_needs_schedule_without_fake_presence():
    s=unassigned();s.pop('apsPlanningData');s['date_exam']='2027-01-09'
    p=rooms.projection(s)
    assert p['metadata']['start'] is None and p['metadata']['needs_schedule']
    assert p['slots']==[dict(date='2027-01-09',start='00:00',end='24:00',room_id=None)]
    s.update(formation='DIRIGEANT',despPresentielStart='2027-01-04',date_fin='2027-01-08')
    p=rooms.projection(s)
    assert p['metadata']['start']=='2027-01-04' and p['metadata']['needs_schedule']
    assert len(p['slots'])==1  # Knowing dates alone does not invent daily hours.
    s['sharedRoom']=dict(presence_start='2027-01-04',presence_end='2027-01-08',start='08:30',end='16:00',weekdays=[0,2])
    p=rooms.projection(s)
    assert not p['metadata']['needs_schedule']
    assert {r['date'] for r in p['slots']}=={'2027-01-04','2027-01-06','2027-01-09'}
    assert all(r['room_id'] is None for r in p['slots'])


def test_incomplete_unassigned_hours_do_not_hide_other_sessions_or_invent_slots():
    s=unassigned();s['apsPlanningData'][0]['slots'][0].pop('end')
    p=rooms.projection(s)
    assert p['slots']==[] and p['metadata']['needs_schedule']
    s['apsPlanningData']=[dict(date='2027-01-04',slots=[])]
    assert rooms.projection(s)['metadata']['needs_schedule']
    s['apsPlanningData'][0]['slots']=[dict(start='09:00',end='12:00',modality='remote')]
    assert not rooms.projection(s)['metadata']['needs_schedule'] and not rooms.projection(s)['slots']


def test_exact_v2_hash_remains_compatible():
    assert rooms.projection(source())['compat_revision']=='71cc8ae3dd1b6f599335323697f2adb5bdce9dda40080a8cad1dc18471f4bc93'


@pytest.mark.parametrize('remaining,assigned',[(1,False),(0,True)])
def test_sessions_api_uses_effective_central_room_overrides(api,monkeypatch,remaining,assigned):
    client,path,legacy,calls=api
    data=load_session_store(path);data['sessions']=[unassigned()];save_session_store(path,data)
    monkeypatch.setattr(rooms,'call',lambda *a:dict(assignments={'session:aps':dict(total=2,unassigned=remaining)}))
    response=client.get('/api/shared-rooms/sessions',headers={'Authorization':'Bearer test'})
    assert response.status_code==200,response.json
    row=response.json['sessions'][0]
    assert row['assigned'] is assigned and row['unassigned_count']==remaining and row['assigned_count']==2-remaining
    assert not row['needs_schedule']


def test_missing_presence_can_be_completed_and_assigned_from_shared_page(api):
    client,path,legacy,calls=api
    data=load_session_store(path);s=unassigned();s.pop('apsPlanningData');data['sessions']=[s];save_session_store(path,data)
    before=rooms.projection(s)
    result=client.post('/api/shared-rooms/sessions',headers={'Authorization':'Bearer test'},json=dict(owner=before['owner'],revision=before['revision'],room_id='r2',presence_start='2027-01-04',presence_end='2027-01-05',start='08:30',end='16:00',weekdays=[0,1]))
    assert result.status_code==200,result.json
    p=rooms.projection(load_session_store(path)['sessions'][0])
    assert not p['metadata']['needs_schedule'] and len(p['slots'])==2
    assert all(r['room_id']=='r2' and r['start']=='08:30' for r in p['slots'])
    assert [c[0] for c in calls]==['prepare','finish']


def test_deleted_incomplete_session_cannot_reappear_in_needs_schedule():
    s=unassigned();s.pop('apsPlanningData')
    removed=rooms.empty_projection(rooms.projection(s))
    assert not removed['slots'] and removed['metadata']['deleted']
