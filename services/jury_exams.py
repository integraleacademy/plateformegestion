"""Keep each jury attached to one examination of an AFC training session."""

AFC_EXAMS = {'aps': ('APS', 'EXAM_APS'), 'ssiap1': ('SSIAP 1', 'EXAM_SSIAP1')}


def exam_dates(services, training):
    categories = {category: key for key, (_, category) in AFC_EXAMS.items()}
    dates = {key: set() for key in AFC_EXAMS}
    for day in training.get('apsPlanningData') or []:
        for slot in day.get('slots') or []:
            category = slot.get('afcCategory') or slot.get('category') or slot.get('uv')
            key = categories.get(category)
            if key:
                date = services.session_input_date(day.get('date'))
                if date:
                    dates[key].add(date)
    return {key: next(iter(days)) if len(days) == 1 else '' for key, days in dates.items()}


def rosters(services, training, dates):
    groups = training.setdefault('afc_exam_jurys', {})
    for key in (*AFC_EXAMS, 'unassigned'):
        groups.setdefault(key, [])
    # Old invitations displayed the single date_exam. Keep links and replies
    # with that examination when the saved timetable identifies it uniquely.
    # Move the original record with its token, receipts and answer, once.
    legacy = training.get('jurys') or []
    if legacy:
        old_date = services.session_input_date(training.get('date_exam'))
        matches = [key for key, date in dates.items() if old_date and date == old_date]
        for member in legacy:
            invited = member.get('notified_at') or member.get('status') in ('present', 'absent')
            key = matches[0] if invited and len(matches) == 1 else 'unassigned'
            if any(str(other.get('id')) == str(member.get('id')) for other in groups[key]):
                key = 'unassigned'
            if key == 'unassigned' and invited and old_date:
                member.setdefault('jury_invitation_date', old_date)
            groups[key].append(member)
        legacy.clear()
    return groups


def views(services, training, include_unassigned=False):
    if not services.is_afc_aps_ssiap_session(training):
        return [training]
    dates = exam_dates(services, training)
    groups = rosters(services, training, dates)
    labels = {key: label for key, (label, _) in AFC_EXAMS.items()}
    if include_unassigned and groups['unassigned']:
        labels['unassigned'] = 'Examen à préciser'
    return [
        {**training, 'jury_exam_key': key, 'jury_exam_label': label, 'date_exam': dates.get(key, ''),
         'jurys': groups[key], 'jury_notification_status': 'notified' if any(
             m.get('notified_at') or m.get('status') in ('present', 'absent') for m in groups[key]) else 'to_notify'}
        for key, label in labels.items()
    ]


def select(services, training, key, include_unassigned=False):
    return next((v for v in views(services, training, include_unassigned)
                 if v.get('jury_exam_key', '') == (key or '')), None)
