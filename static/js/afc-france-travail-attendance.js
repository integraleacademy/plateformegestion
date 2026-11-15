(() => {
  const card = document.getElementById('afc-france-travail-section');
  if (!card) return;
  const byId = id => document.getElementById(id);
  const api = '/api/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/afc-france-travail/';
  const config = byId('afcFranceTravailConfig');
  const box = byId('afcFranceTravailPreview');
  let editor = null;
  let rosterRequest = 0;
  let previewRequest = 0;
  const fields = {
    marche_afc: ['ftMarcheAfc', 'Marché AFC'], brs: ['ftBrs', 'BRS'],
    convention: ['ftConvention', 'Convention'], bon_commande: ['ftBonCommande', 'Bon de commande'],
    type_session: ['ftTypeSession', 'Type de session'], intitule: ['ftIntitule', 'Intitulé']
  };
  const dateFr = value => value ? value.split('-').reverse().join('/') : 'À renseigner';
  const element = (tag, text) => {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  };

  async function read(action, data, method = 'POST') {
    const options = data ? {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)} : {};
    const response = await fetch(api + action, {...options, cache: 'no-store'});
    if (response.redirected) throw new Error('Reconnectez-vous à la plateforme pour accéder aux feuilles.');
    const result = await response.json();
    if (!response.ok || !result.ok) {
      const error = new Error(result.error || 'Données France Travail indisponibles.');
      error.status = response.status;
      throw error;
    }
    return result;
  }

  function sourceLink(source) {
    const link = element('a', source.name || 'Ouvrir la session source');
    link.href = 'https://gestionstagiaires-r5no.onrender.com/admin/sessions/' + encodeURIComponent(source.id) + '/trainees';
    link.target = '_blank';
    link.rel = 'noopener';
    return link;
  }

  function button(label, action, primary = false) {
    const node = element('button', label);
    node.type = 'button';
    node.className = primary ? 'btn small gold' : 'btn small';
    node.addEventListener('click', action);
    return node;
  }

  function canLeaveRow() {
    if (!editor) return true;
    if (editor.saving || editor.hasChanges()) {
      showPlanningToast(editor.saving ? 'Enregistrement en cours…' : 'Enregistrez ou annulez la modification du stagiaire.', 'warning');
      return false;
    }
    editor.close();
    return true;
  }

  function displayRow(row, student, source) {
    const values = [student.displayName, student.france_travail_id || 'À renseigner',
      dateFr(student.entryDate), dateFr(student.exitDate), student.ranHours == null ? '—' : student.ranHours + ' h'];
    row.replaceChildren(...values.map(value => element('td', value)));
    const actions = row.insertCell();
    if (source) {
      const missing = !student.france_travail_id;
      actions.append(button(missing ? 'Renseigner' : 'Modifier', () => {
        if (canLeaveRow()) editRow(row, student, source);
      }, missing));
    }
  }

  function editRow(row, student, source) {
    function control(column, tag, label) {
      const node = document.createElement(tag);
      node.setAttribute('aria-label', label + ' · ' + student.displayName);
      row.cells[column].replaceChildren(node);
      return node;
    }
    const id = control(1, 'input', 'Identifiant France Travail');
    id.value = student.france_travail_id;
    id.placeholder = 'Identifiant France Travail';
    id.maxLength = 64;
    id.autocomplete = 'off';
    const entry = control(2, 'input', 'Entrée en formation');
    entry.type = 'date';
    entry.required = true;
    entry.max = student.exitDate;
    entry.value = student.entryDate;
    const ran = control(4, 'select', 'Remise à niveau');
    ran.add(new Option('Non renseignée', ''));
    for (const hours of [0, 40, 54]) ran.add(new Option(hours + ' h', String(hours)));
    ran.value = student.ranHours ?? '';
    ran.addEventListener('change', () => {
      const profileDate = source.ranStartDates?.[ran.value];
      if (profileDate) entry.value = profileDate;
    });
    const message = element('small', '');
    message.className = 'ft-row-message';
    message.setAttribute('role', 'status');
    const actions = document.createElement('div');
    actions.className = 'ft-row-actions';
    const save = button('Enregistrer', submit, true);
    const cancel = button('Annuler', close);
    actions.append(save, cancel);
    row.cells[5].replaceChildren(actions, message);

    function changedValues() {
      const values = {france_travail_id: id.value.trim(), entryDate: entry.value,
        ranHours: ran.value === '' ? null : Number(ran.value)};
      return Object.fromEntries(Object.entries(values).filter(([key, value]) => value !== student[key]));
    }
    function close() {
      editor = null;
      displayRow(row, student, source);
      row.cells[5].querySelector('button')?.focus();
    }
    editor = {saving: false, hasChanges: () => Object.keys(changedValues()).length > 0, close};
    id.focus();

    async function submit() {
      if (!entry.reportValidity()) return;
      const changes = changedValues();
      if (!Object.keys(changes).length) return close();
      const previous = Object.fromEntries(Object.keys(changes).map(key => [key, student[key]]));
      editor.saving = true;
      const controls = [id, entry, ran, save, cancel];
      controls.forEach(node => { node.disabled = true; });
      save.textContent = 'Enregistrement…';
      message.replaceChildren();
      try {
        const result = await read('roster/' + encodeURIComponent(student.id), {sourceSessionId: source.id, changes, previous}, 'PATCH');
        for (const key of ['france_travail_id', 'entryDate', 'ranHours']) student[key] = result.student[key];
      } catch (error) {
        editor.saving = false;
        controls.forEach(node => { node.disabled = false; });
        save.textContent = 'Enregistrer';
        message.textContent = error.message;
        if (error.status === 409 || error.status === 404) {
          message.append(' ', button('Recharger la liste', () => { close(); loadRoster(); }));
        }
        return;
      }
      close();
      showPlanningToast('Modifications enregistrées dans Gestion des stagiaires.');
      if (box.style.display === 'block') showPreview();
    }
  }

  async function loadRoster() {
    const body = byId('ftRosterRows');
    if (!body) return;
    const revision = ++rosterRequest;
    const status = byId('ftRosterStatus');
    body.replaceChildren();
    status.textContent = 'Chargement des inscrits…';
    try {
      const {students, source} = await read('roster');
      if (revision !== rosterRequest) return;
      status.replaceChildren();
      if (source) status.append(sourceLink(source));
      status.append(element('span', ' · ' + students.length + ' stagiaire(s) inscrit(s)'));
      for (const student of students) displayRow(body.insertRow(), student, source);
    } catch (error) {
      if (revision === rosterRequest) status.textContent = error.message;
    }
  }

  function openConfig() {
    config.style.display = 'block';
    if (!editor) loadRoster();
  }
  byId('configureAfcFranceTravail').addEventListener('click', () => {
    if (config.style.display === 'none') openConfig();
    else if (canLeaveRow()) config.style.display = 'none';
  });
  byId('saveAfcFranceTravailSettings').addEventListener('click', async () => {
    if (!canLeaveRow()) return;
    const settings = Object.fromEntries(Object.entries(fields).map(([key, [id]]) => [key, byId(id).value]));
    if (byId('ftSourceSessionId')) settings.sourceSessionId = byId('ftSourceSessionId').value;
    try {
      await read('settings', settings);
      ++previewRequest;
      preview.disabled = false;
      box.style.display = 'none';
      showPlanningToast('Informations France Travail enregistrées.');
      if (!editor) await loadRoster();
    } catch (e) { showPlanningToast(e.message, 'error'); }
  });
  byId('saveAfcFranceTravailIds')?.addEventListener('click', async () => {
    const ids = {};
    for (const input of card.querySelectorAll('.ft-student-id')) ids[input.dataset.studentId] = input.value;
    try {
      await read('ids', {ids});
      showPlanningToast('Identifiants France Travail enregistrés.');
    } catch (e) { showPlanningToast(e.message, 'error'); }
  });

  async function download(button) {
    if (!canLeaveRow()) return;
    button.disabled = true;
    try {
      const response = await fetch(api + 'generate', {cache: 'no-store'});
      if (response.redirected) throw new Error('Reconnectez-vous à la plateforme pour télécharger les feuilles.');
      if (!response.ok) throw new Error((await response.json()).error || 'Téléchargement impossible.');
      const link = document.createElement('a');
      link.href = URL.createObjectURL(await response.blob());
      const name = /filename="?([^";]+)"?/.exec(response.headers.get('Content-Disposition') || '');
      link.download = name ? name[1] : 'feuilles_presence_france_travail.xlsx';
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 30000);
    } catch (e) { showPlanningToast(e.message, 'error'); }
    finally { button.disabled = false; }
  }

  const preview = byId('previewAfcFranceTravail');
  preview.addEventListener('click', () => { if (canLeaveRow()) showPreview(); });
  async function showPreview() {
    const revision = ++previewRequest;
    preview.disabled = true;
    box.style.display = 'block';
    box.className = 'flash';
    box.textContent = 'Préparation des feuilles…';
    try {
      const {preview: p, source} = await read('preview');
      if (revision !== previewRequest) return;
      box.className = p.missingIdCount || p.missingSettings.length || !p.studentCount ? 'flash warning' : 'flash success';
      box.replaceChildren(element('h3', p.sessionName || 'Feuilles France Travail'));
      if (source) {
        const label = element('p', 'Session dans Gestion des stagiaires · ');
        label.append(sourceLink(source));
        box.append(label);
      }
      box.append(element('p', 'Du ' + dateFr(p.dateStart) + ' au ' + dateFr(p.dateEnd) + ' · ' +
        p.weekCount + ' semaine(s) · ' + p.studentCount + ' stagiaire(s) · ' + p.trainerCount +
        ' formateur(s) · ' + p.totalPlannedHours + ' heures-stagiaires prévues.'));
      box.append(element('p', p.sheetNames.join(' · ')));
      box.append(element('p', Object.entries(fields).map(([key, [, label]]) => label + ' : ' + (p.settings[key] || '—')).join(' · ')));
      if (p.missingSettings.length) box.append(element('p', 'À renseigner : ' + p.missingSettings.map(key => fields[key][1]).join(', ')));
      if (p.missingIdCount) box.append(element('p', 'Identifiant France Travail manquant : ' + p.missingIds.join(', ')));
      if (source && !p.studentCount) box.append(element('p', 'Aucun stagiaire inscrit dans la session source.'));
      const actions = document.createElement('div');
      actions.className = 'planning-actions';
      const back = element('button', 'Configurer France Travail');
      back.type = 'button';
      back.className = 'btn';
      back.onclick = openConfig;
      const save = element('button', 'Télécharger le fichier Excel');
      save.type = 'button';
      save.className = 'btn gold';
      save.disabled = Boolean(source && !p.studentCount);
      save.onclick = () => download(save);
      actions.append(back, save);
      box.append(actions);
    } catch (e) {
      if (revision !== previewRequest) return;
      box.className = 'flash error';
      box.textContent = e.message;
    } finally { if (revision === previewRequest) preview.disabled = false; }
  }
})();
