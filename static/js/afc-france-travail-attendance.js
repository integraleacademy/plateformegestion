(() => {
  const card = document.getElementById('afc-france-travail-section');
  if (!card) return;
  const byId = id => document.getElementById(id);
  const api = '/api/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/afc-france-travail/';
  const config = byId('afcFranceTravailConfig');
  const box = byId('afcFranceTravailPreview');
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

  async function read(action, data) {
    const options = data ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)} : {};
    const response = await fetch(api + action, {...options, cache: 'no-store'});
    if (response.redirected) throw new Error('Reconnectez-vous à la plateforme pour accéder aux feuilles.');
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Données France Travail indisponibles.');
    return result;
  }

  function sourceLink(source) {
    const link = element('a', source.name || 'Ouvrir la session source');
    link.href = 'https://gestionstagiaires-r5no.onrender.com/admin/sessions/' + encodeURIComponent(source.id) + '/trainees';
    link.target = '_blank';
    link.rel = 'noopener';
    return link;
  }

  async function loadRoster() {
    const body = byId('ftRosterRows');
    if (!body) return;
    const status = byId('ftRosterStatus');
    body.replaceChildren();
    status.textContent = 'Chargement des inscrits…';
    try {
      const {students, source} = await read('roster');
      status.replaceChildren();
      if (source) status.append(sourceLink(source));
      status.append(element('span', ' · ' + students.length + ' stagiaire(s) inscrit(s)'));
      for (const student of students) {
        const row = document.createElement('tr');
        for (const value of [student.displayName, student.france_travail_id || 'À renseigner',
          dateFr(student.entryDate), dateFr(student.exitDate), student.ranHours == null ? '—' : student.ranHours + ' h']) {
          row.append(element('td', value));
        }
        body.append(row);
      }
    } catch (error) {
      status.textContent = error.message;
    }
  }

  function openConfig() {
    config.style.display = 'block';
    loadRoster();
  }
  byId('configureAfcFranceTravail').addEventListener('click', () => {
    if (config.style.display === 'none') openConfig();
    else config.style.display = 'none';
  });
  byId('saveAfcFranceTravailSettings').addEventListener('click', async () => {
    const settings = Object.fromEntries(Object.entries(fields).map(([key, [id]]) => [key, byId(id).value]));
    if (byId('ftSourceSessionId')) settings.sourceSessionId = byId('ftSourceSessionId').value;
    try {
      await read('settings', settings);
      box.style.display = 'none';
      showPlanningToast('Informations France Travail enregistrées.');
      await loadRoster();
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
  preview.addEventListener('click', async () => {
    preview.disabled = true;
    box.style.display = 'block';
    box.className = 'flash';
    box.textContent = 'Préparation des feuilles…';
    try {
      const {preview: p, source} = await read('preview');
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
      box.className = 'flash error';
      box.textContent = e.message;
    } finally { preview.disabled = false; }
  });
})();
