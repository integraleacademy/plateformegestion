"""Storage for the isolated /planning module; not a source of shared rooms."""
from services.session_storage import SessionStorageConflict


def save_formation(conn, data, formation_id=None, delete=False, expected=None):
    """Standalone old planner: never contacts the shared room registry."""
    conn.execute('BEGIN IMMEDIATE')
    current = conn.execute('SELECT * FROM formations WHERE id=?', (formation_id,)).fetchone() if formation_id else None
    if formation_id and not current:
        raise SessionStorageConflict('Formation introuvable.')
    if expected is not None and dict(current or {}) != expected:
        raise SessionStorageConflict('La formation a changé. Rechargez la page.')
    if formation_id is None:
        formation_id = conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM formations').fetchone()[0]
    new = dict(current or {}); new.update(data); new['id'] = formation_id
    if delete:
        conn.execute('DELETE FROM formations WHERE id=?', (formation_id,))
    elif current:
        fields = [k for k in data if k in ('nom','type','date_debut','date_fin','salle','nombre_stagiaires','commentaire')]
        conn.execute('UPDATE formations SET ' + ','.join(k+'=?' for k in fields) + ' WHERE id=?', [data[k] for k in fields]+[formation_id])
    else:
        fields = ['id','nom','type','date_debut','date_fin','salle','nombre_stagiaires','commentaire','created_at']
        conn.execute('INSERT INTO formations('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')', [new.get(k) for k in fields])
    conn.commit()
    return formation_id
