/* Shared planner: civil dates (Europe/Paris), no browser-local persistence. */
(() => {
  'use strict';
  const $ = (q, root = document) => root.querySelector(q);
  const $$ = (q, root = document) => [...root.querySelectorAll(q)];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icon = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const date = value => new Date(`${value}T12:00:00`);
  const add = (value, days) => { const d = date(value); d.setDate(d.getDate() + days); return iso(d); };
  const today = new Intl.DateTimeFormat('sv-SE', {timeZone:'Europe/Paris'}).format(new Date());
  const fmt = (value, options = {}) => value ? date(value).toLocaleDateString('fr-FR', {day:'numeric',month:'short',...options}) : '';
  const span = (start, end, year = false) => start === end || !end ? fmt(start, year ? {year:'numeric'} : {}) : `${fmt(start)} → ${fmt(end, year ? {year:'numeric'} : {})}`;
  const ownerName = owner => ({both:'Clément & Elsa',clement:'Clément',elsa:'Elsa'}[owner] || 'Clément & Elsa');
  const TYPES = {
    louise:{label:'Louise',icon:'heart',color:'#c66e99'}, boarding:{label:'Pension chien',icon:'paw',color:'#c78244'},
    transport:{label:'Transports',icon:'plane',color:'#4b9b9e'},personal:{label:'Personnel',icon:'calendar',color:'#8674b9'},
    professional:{label:'Rendez-vous pro',icon:'work',color:'#647a9a'},task:{label:'À faire',icon:'task',color:'#82914c'},
    training_start:{label:'Début de formation',icon:'work',color:'#4b929e'},training_onsite:{label:'Début de présentiel',icon:'work',color:'#6575bd'},
    training_end:{label:'Fin de formation',icon:'work',color:'#6b9a71'},training_exam:{label:'Examen',icon:'work',color:'#bc8f37'},
    location:{label:'Lieu / séjour',icon:'pin',color:'#7c65bc'},shopping:{label:'Liste de courses',icon:'bag',color:'#78a489'},note:{label:'Note',icon:'note',color:'#b39b6e'}
  };
  const PLACES = {paris:{label:'Paris',color:'#7c65bc'},puget:{label:'Puget',color:'#c09240'},cantal:{label:'Cantal',color:'#4e987c'},away:{label:'Déplacement',color:'#5b8fb3'}};
  const TABS = [ ['calendar','Calendrier','calendar'],['louise','Louise','heart'],['location','Déplacements','pin'],['boarding','Pension chien','paw'],['transport','Transports','plane'],['shopping','Courses','bag'],['task','À faire','task'],['note','Notes','note'],['training','Formations','work'],['alerts','Anomalies','alert'] ];
  const s = {data:null,today,cursor:date(today),tab:'calendar',view:'month',owner:'all',hidden:new Set(),editing:null,listScope:'year',search:'',selectedDay:today,loading:false,lastLoaded:0,request:0};
  const color = r => (r.kind === 'location' ? PLACES[r.place]?.color : TYPES[r.kind]?.color) || '#8674b9';
  const owns = r => s.owner === 'all' || r.owner === 'both' || r.owner === s.owner;
  const inYear = r => r.start <= `${s.cursor.getFullYear()}-12-31` && r.end >= `${s.cursor.getFullYear()}-01-01`;
  const api = async (url, options = {}) => {
    const response = await fetch(`/gestion-clement-elsa${url}`, {credentials:'same-origin',cache:'no-store',...options,
      headers:{'Content-Type':'application/json','X-Planner-CSRF':$('meta[name=planner-csrf]').content,...options.headers}});
    if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Votre session a expiré. Rechargez la page pour vous reconnecter.');
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'L’enregistrement a échoué. Réessayez.');
    return result;
  };
  function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(s.toastTimer); s.toastTimer = setTimeout(() => $('#toast').hidden = true, 5000); }
  function errorAt(id, message) { $(id).textContent = message; $(id).hidden = !message; }
  async function load() {
    const id = ++s.request;
    s.loading = true; $('#refresh').disabled = true; $('#save-state').textContent = 'Actualisation en cours…';
    try {
      const data = await api(`/data?year=${s.cursor.getFullYear()}`);
      if (id !== s.request) return false;
      s.data = data; s.today = data.today; s.lastLoaded = Date.now();
      errorAt('#load-error', ''); errorAt('#training-error', data.training_error || '');
      render(); $('#save-state').textContent = `Planning partagé · Actualisé à ${new Date().toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'})}`;
      return true;
    } catch (e) {
      if (id !== s.request) return false;
      errorAt('#load-error', `${e.message} Cliquez sur Actualiser pour réessayer.`);
      $('#save-state').textContent = 'Actualisation impossible · les informations affichées peuvent être anciennes.';
      return false;
    } finally {
      if (id === s.request) { s.loading = false; $('#refresh').disabled = false; $('#add-main').disabled = !s.data; }
    }
  }
  function calendarEvents() {
    if (!s.data) return [];
    return [...s.data.records.filter(r => !['location','boarding','transport','shopping','note','task'].includes(r.kind)),
      ...s.data.reservations, ...s.data.training,
      ...s.data.records.filter(r => r.kind === 'task' && r.due && !r.done).map(r => ({...r,start:r.due,end:r.due}))]
      .filter(r => owns(r) && !s.hidden.has(r.kind)).sort((a,b) => a.start.localeCompare(b.start) || (a.start_time || '').localeCompare(b.start_time || '') || a.title.localeCompare(b.title));
  }
  function dayCoverage(value) {
    const known = s.data.coverage.days.find(d => d.date === value);
    if (known) return known;
    const row = {date:value,clement:null,elsa:null};
    s.data.records.filter(r => r.kind === 'location' && r.start <= value && r.end >= value).forEach(r => {
      (r.owner === 'both' ? ['clement','elsa'] : [r.owner]).forEach(p => row[p] = r);
    });
    return row;
  }
  const missingDay = row => s.owner === 'all' ? !row.clement || !row.elsa : !row[s.owner];
  function placesForDay(value) {
    const row = dayCoverage(value), persons = s.owner === 'all' ? ['clement','elsa'] : [s.owner];
    const titles = [...new Set(persons.map(p => row[p]?.title).filter(Boolean))];
    return {row,persons,title:titles.join(' / ')};
  }
  function setTab(tab) { s.tab = tab; s.search = ''; render(); }
  function render() {
    if (!s.data) return;
    const futureAlerts = s.data.alerts.filter(r => r.end >= s.today);
    const nextLouise = s.data.records.filter(r => r.kind === 'louise' && r.end >= s.today).sort((a,b) => a.start.localeCompare(b.start))[0];
    const courses = s.data.records.filter(r => r.kind === 'shopping' && !r.done).length;
    $('#metrics').innerHTML = [
      ['pin',s.data.coverage.missing_days,`jours à compléter en ${s.data.year}`,'alerts'],
      ['plane',new Set(futureAlerts.map(a => a.record_id)).size,'séjours / réservations à préparer','transport'],
      ['heart',nextLouise ? (nextLouise.start <= s.today ? 'Avec nous' : fmt(nextLouise.start)) : 'À prévoir','prochaine période avec Louise','louise'],
      ['bag',courses,`article${courses > 1 ? 's' : ''} sur la liste de courses`,'shopping']
    ].map(([i,v,l,t]) => `<button class="metric" data-tab="${t}"><span class="metric-icon">${icon(i)}</span><span><strong>${esc(v)}</strong><span class="metric-label">${esc(l)}</span></span></button>`).join('');
    $('#tabs').innerHTML = TABS.map(([id,label,i]) => `<button class="tab ${id === s.tab ? 'active' : ''}" data-tab="${id}" aria-current="${id === s.tab ? 'page' : 'false'}">${icon(i)}${label}${id === 'alerts' && s.data.coverage.missing_days ? `<span class="tab-count">${s.data.coverage.missing_days}</span>` : ''}</button>`).join('');
    $('#today-label').textContent = fmt(s.today);
    const td = dayCoverage(s.today);
    $('#today-places').innerHTML = ['clement','elsa'].map(p => `<button class="today-person" data-day="${s.today}"><span class="avatar ${p}">${p === 'clement' ? 'C' : 'E'}</span><span><strong>${ownerName(p)}</strong><small>${esc(td[p]?.title || 'Lieu à renseigner')}</small></span>${icon('pin')}</button>`).join('');
    $('#upcoming').innerHTML = futureAlerts.slice(0,3).map(a => `<button class="prepare-item" data-edit="${esc(a.record_id)}"><span class="prepare-icon">${icon(a.kind === 'boarding' ? 'paw' : 'plane')}</span><span><strong>${esc(a.title)}</strong><small>${span(a.start,a.end)}</small></span></button>`).join('') || '<p class="side-empty">Aucune réservation en attente. Vous pouvez préparer votre prochain séjour.</p>';
    renderLegend(); renderView();
  }
  function renderLegend() {
    $('#legend').innerHTML = '<p class="legend-group">Vos lieux</p>' + Object.entries(PLACES).map(([key,v]) => `<div class="legend-label"><span class="legend-dot" style="--event-color:${v.color}"></span>${v.label}</div>`).join('') +
      '<p class="legend-group">Vie personnelle</p>' + Object.entries(TYPES).filter(([k]) => ['louise','boarding','transport','personal','task'].includes(k)).map(legendCheck).join('') +
      '<p class="legend-group">Vie professionnelle</p>' + Object.entries(TYPES).filter(([k]) => k.startsWith('training_') || k === 'professional').map(legendCheck).join('');
  }
  function legendCheck([key,v]) { return `<label class="legend-label"><input type="checkbox" data-filter="${key}" ${s.hidden.has(key) ? '' : 'checked'}><span class="legend-dot" style="--event-color:${v.color}"></span>${v.label}</label>`; }
  function renderView() {
    const calendar = s.tab === 'calendar', undated = ['shopping','task','note'].includes(s.tab);
    $('#view-switch').hidden = !calendar; $('#calendar-footer').hidden = !calendar; $('#today-button').hidden = !calendar;
    $('#prev').hidden = undated; $('#next').hidden = undated; $('#view-intro').hidden = calendar;
    $$('#view-switch button').forEach(b => { b.classList.toggle('active',b.dataset.view === s.view); b.setAttribute('aria-pressed',b.dataset.view === s.view); });
    $('#period-label').textContent = undated ? TABS.find(t => t[0] === s.tab)[1] : calendar && s.view !== 'year' ? s.cursor.toLocaleDateString('fr-FR',{month:'long',year:'numeric'}) : String(s.cursor.getFullYear());
    if (calendar) { if (s.view === 'year') renderYear(); else renderCalendar(); }
    else renderList();
  }
  function chip(r,value) { return `<button class="event-chip ${r.status === 'pending' ? 'pending' : ''} ${r.start < value ? 'continued' : ''}" style="--event-color:${color(r)}" data-event="${esc(r.id)}" title="${esc(r.title + (r.status === 'pending' ? ' · À réserver' : '') + ' · ' + span(r.start,r.end))}">${r.start_time ? esc(r.start_time) + ' ' : ''}${r.status === 'booked' ? '✓ ' : ''}${esc(r.title)}</button>`; }
  function renderCalendar() {
    const week = s.view === 'week', d = new Date(s.cursor);
    if (!week) d.setDate(1);
    d.setDate(d.getDate() - (d.getDay() + 6) % 7);
    const first = iso(d), days = week ? 7 : Math.ceil(((new Date(s.cursor.getFullYear(),s.cursor.getMonth(),1).getDay() + 6) % 7 + new Date(s.cursor.getFullYear(),s.cursor.getMonth() + 1,0).getDate()) / 7) * 7;
    const events = calendarEvents();
    if (week) $('#period-label').textContent = span(first,add(first,6));
    let html = '<div class="weekday-row">' + ['LUN.','MAR.','MER.','JEU.','VEN.','SAM.','DIM.'].map(x => `<span>${x}</span>`).join('') + `</div><div class="month-grid ${week ? 'week-grid' : ''}">`;
    for (let i = 0; i < days; i++) {
      const value = add(first,i), day = date(value), {row,persons,title} = placesForDay(value);
      const ev = events.filter(r => r.start <= value && r.end >= value), limit = week ? 30 : 3;
      html += `<div class="calendar-day ${day.getMonth() !== s.cursor.getMonth() && !week ? 'outside' : ''} ${value === s.today ? 'today' : ''}" data-day="${value}" tabindex="0" role="group" aria-label="${esc(fmt(value,{weekday:'long',month:'long',year:'numeric'}))}${missingDay(row) ? ' — lieu à compléter' : ''}"><div class="day-top"><span class="day-number">${day.getDate()}</span>${missingDay(row) ? '<span class="coverage-dot" title="Lieu à compléter"></span>' : '<span class="day-add-hint">+</span>'}</div><div class="location-lines">${persons.map(p => `<span class="location-line ${row[p] ? '' : 'missing'}" style="--event-color:${PLACES[row[p]?.place]?.color || '#edcfc9'}" title="${ownerName(p)} : ${esc(row[p]?.title || 'lieu manquant')}"></span>`).join('')}</div><span class="place-name">${esc(title || 'Lieu à compléter')}</span>${ev.slice(0,limit).map(r => chip(r,value)).join('')}${ev.length > limit ? `<button class="more-events" data-day="${value}">+ ${ev.length - limit} autre${ev.length - limit > 1 ? 's' : ''}</button>` : ''}</div>`;
    }
    $('#view').innerHTML = html + '</div>';
  }
  function renderYear() {
    const year = s.cursor.getFullYear(), events = calendarEvents();
    let html = '<div class="year-grid">';
    for (let m = 0; m < 12; m++) {
      const first = new Date(year,m,1), count = new Date(year,m + 1,0).getDate();
      html += `<section class="mini-month"><h3>${first.toLocaleDateString('fr-FR',{month:'long'})}</h3><div class="mini-grid">${['L','M','M','J','V','S','D'].map(x => `<span>${x}</span>`).join('')}${'<span></span>'.repeat((first.getDay() + 6) % 7)}`;
      for (let n = 1; n <= count; n++) {
        const value = iso(new Date(year,m,n)), missing = missingDay(dayCoverage(value));
        html += `<button class="mini-day ${missing ? 'missing' : 'covered'} ${value === s.today ? 'today' : ''}" data-day="${value}" title="${esc(fmt(value,{month:'long'}))} · ${missing ? 'Lieu à compléter' : 'Lieux renseignés'}">${n}${events.some(r => r.start <= value && r.end >= value) ? '<span class="mini-event-dot"></span>' : ''}</button>`;
      }
      html += '</div></section>';
    }
    $('#view').innerHTML = html + '</div><p class="year-key">Vert : lieux renseignés · Rose : lieu manquant · Point violet : événement prévu. Les 365 jours de l’année sont contrôlés (366 les années bissextiles).</p>';
  }
  const empty = (title,text,type = 'calendar') => `<div class="empty-state"><div class="empty-icon">${icon(TYPES[type]?.icon || 'calendar')}</div><h3>${esc(title)}</h3><p>${esc(text)}</p><button class="button primary" data-new="${type}">${icon('plus')} Ajouter</button></div>`;
  function listRecords() {
    let records;
    if (s.tab === 'training') records = s.data.training;
    else if (s.tab === 'boarding' || s.tab === 'transport') records = s.data.reservations.filter(r => r.kind === s.tab);
    else records = s.data.records.filter(r => r.kind === s.tab);
    return records.filter(owns).filter(r => !r.start || s.listScope === 'all' || (s.listScope === 'future' ? r.end >= s.today : inYear(r)))
      .filter(r => `${r.title} ${r.notes || ''} ${r.destination || ''} ${r.origin || ''}`.toLocaleLowerCase('fr').includes(s.search.toLocaleLowerCase('fr')))
      .sort((a,b) => Number(!!a.done) - Number(!!b.done) || (a.start || a.due || '9999').localeCompare(b.start || b.due || '9999') || a.title.localeCompare(b.title));
  }
  const descriptions = {
    louise:'Les jours avec Louise, les week-ends et les vacances. Ajoutez aussi des périodes une semaine sur deux.',
    location:'Vos lieux de vie, jour par jour. Les dates de début et de fin sont incluses dans chaque période.',
    boarding:'Les périodes de pension, avec leur statut et leurs dates de réservation réelles.',
    transport:'Vos billets et trajets, y compris les retours à Puget. Les allers et retours des séjours sont affichés séparément.',
    shopping:'Une liste partagée. Cochez les achats au fur et à mesure, depuis votre téléphone ou votre ordinateur.',
    task:'Les choses à ne pas oublier. Une tâche avec une échéance apparaît aussi dans le calendrier.',
    note:'Vos idées, informations pratiques et notes à retrouver facilement.',
    training:'Dates récupérées automatiquement depuis les sessions. Les modifications se font dans la fiche de formation.',
    alerts:'Repérez les jours sans lieu et les réservations qui restent à préparer.'
  };
  function renderList() {
    const dated = !['shopping','task','note','alerts'].includes(s.tab);
    $('#view-intro').innerHTML = `<p>${descriptions[s.tab]}</p><div class="list-tools">${dated ? `<select id="list-scope" aria-label="Période de la liste"><option value="year" ${s.listScope === 'year' ? 'selected' : ''}>Année ${s.cursor.getFullYear()}</option><option value="future" ${s.listScope === 'future' ? 'selected' : ''}>Toutes les dates à venir</option><option value="all" ${s.listScope === 'all' ? 'selected' : ''}>Toutes les dates</option></select>` : ''}${s.tab !== 'alerts' ? `<input type="search" id="list-search" placeholder="Rechercher…" aria-label="Rechercher dans la liste" value="${esc(s.search)}">` : ''}</div>`;
    if (s.tab === 'alerts') { renderAlerts(); return; }
    const records = listRecords(), type = s.tab === 'training' ? 'professional' : s.tab;
    if (s.tab === 'note') {
      $('#view').innerHTML = records.length ? `<div class="list-content"><button class="button small" data-new="note">${icon('plus')} Nouvelle note</button></div><div class="notes-grid">${records.map(r => `<button class="note-card" data-edit="${r.id}"><strong>${esc(r.title)}</strong><p>${esc(r.notes || 'Cliquer pour compléter…')}</p><small>${ownerName(r.owner)}</small></button>`).join('')}</div>` : empty('Les idées ont leur place ici.','Gardez une adresse, un code de réservation ou une idée pour plus tard.','note');
      return;
    }
    if (s.tab === 'shopping' || s.tab === 'task') {
      $('#view').innerHTML = `<form class="quick-add" id="quick-add"><input name="title" required maxlength="200" placeholder="${s.tab === 'shopping' ? 'Ajouter un article à acheter…' : 'Ajouter une chose à faire…'}" aria-label="Nouvel élément"><button class="button primary" type="submit">${icon('plus')} Ajouter</button></form><div class="list-content">${records.map(r => `<div class="check-item ${r.done ? 'done' : ''}"><input type="checkbox" data-toggle="${r.id}" aria-label="${esc(r.title)} : terminé" ${r.done ? 'checked' : ''}><button class="list-main row-open" data-edit="${r.id}"><strong>${esc(r.title)} ${r.quantity ? `<span class="badge">${esc(r.quantity)}</span>` : ''}</strong><small>${r.due ? fmt(r.due,{year:'numeric'}) + ' · ' : ''}${ownerName(r.owner)}${r.notes ? ' · ' + esc(r.notes.slice(0,120)) : ''}</small></button><button class="icon-button" data-edit="${r.id}" aria-label="Modifier ${esc(r.title)}">${icon('right')}</button></div>`).join('') || '<div class="empty-state"><h3>Une chose de moins à garder en tête.</h3><p>Ajoutez votre premier élément juste au-dessus.</p></div>'}</div>`;
      return;
    }
    if (!records.length) {
      $('#view').innerHTML = s.tab === 'training' ? '<div class="empty-state"><div class="empty-icon">' + icon('work') + '</div><h3>Aucune date pour cette sélection</h3><p>Les dates enregistrées dans les sessions apparaîtront automatiquement ici.</p><a class="button" href="/sessions">Voir les sessions</a></div>' : empty('Votre planning prend forme.','Aucun élément pour cette sélection. Ajoutez une première date ou affichez toutes les dates.',type);
      return;
    }
    let month = '';
    $('#view').innerHTML = '<div class="list-content">' + (s.tab !== 'training' ? `<button class="button small" data-new="${type}">${icon('plus')} Ajouter ${s.tab === 'louise' ? 'une période' : 'un élément'}</button>` : '') + records.map(r => {
      const nextMonth = r.start.slice(0,7), heading = nextMonth !== month ? `<h3 class="list-group-label">${fmt(r.start,{day:undefined,month:'long',year:'numeric'})}</h3>` : ''; month = nextMonth;
      const details = [ownerName(r.owner),r.origin && r.destination ? `${r.origin} → ${r.destination}` : '',r.mode || '',r.reference || '',r.linked ? 'Lié au séjour · modifier le séjour' : '',r.series_id ? 'Période récurrente' : ''].filter(Boolean).join(' · ');
      return heading + `<div class="list-row"><span class="list-color" style="--event-color:${color(r)}"></span><div class="list-date">${span(r.start,r.end)}</div><div class="list-main">${r.readonly ? `<a class="row-open" href="${esc(r.url)}"><strong>${esc(r.title)}</strong></a>` : `<button class="row-open" data-edit="${esc(r.record_id || r.id)}"><strong>${esc(r.title)}</strong></button>`}<small>${esc(details)}</small>${r.notes ? `<small class="notes-preview">${esc(r.notes)}</small>` : ''}</div>${r.readonly ? '<span class="badge automatic">Automatique</span>' : r.status ? `<span class="badge ${r.status}">${r.status === 'booked' ? '✓ Réservé' : 'À réserver'}</span>` : ''}<button class="icon-button" ${r.readonly ? `data-url="${esc(r.url)}"` : `data-edit="${esc(r.record_id || r.id)}"`} aria-label="Ouvrir ${esc(r.title)}">${icon('right')}</button></div>`;
    }).join('') + '</div>';
  }
  function renderAlerts() {
    const cov = s.data.coverage, missing = cov.missing.filter(r => owns(r)), alerts = s.data.alerts.filter(inYear);
    $('#view').innerHTML = `<div class="list-content"><div class="anomaly-intro"><strong>${cov.covered_days} / ${cov.total_days} jours entièrement renseignés</strong><p>Chaque jour doit avoir un lieu pour Clément et pour Elsa, y compris les jours passés. Aucun lieu n’est supposé automatiquement.</p><div class="coverage-bar"><span style="width:${cov.covered_days / cov.total_days * 100}%"></span></div><button class="button small" id="fill-year-inline" style="margin-top:14px">${icon('pin')} Compléter les jours sans lieu</button></div><h3 class="list-group-label">Lieux à compléter · ${missing.reduce((n,r) => n + r.count,0)} jours</h3>${missing.map(r => `<div class="list-row"><span class="list-color" style="--event-color:#d4928a"></span><div class="list-date">${span(r.start,r.end)}</div><div class="list-main"><strong>${ownerName(r.owner)}</strong><small>${r.count} jour${r.count > 1 ? 's' : ''} sans lieu</small></div><button class="button small" data-fill-start="${r.start}" data-fill-end="${r.end}" data-fill-owner="${r.owner}">Compléter</button></div>`).join('') || '<p class="side-empty">Tous les jours de cette année ont un lieu renseigné.</p>'}<h3 class="list-group-label">Réservations à vérifier · ${alerts.length}</h3>${alerts.map(r => `<div class="list-row"><span class="list-color" style="--event-color:#bd985f"></span><div class="list-date">${span(r.start,r.end)}</div><button class="list-main row-open" data-edit="${esc(r.record_id)}"><strong>${esc(r.title)}</strong><small>Ouvrir pour compléter le statut, les dates et les notes.</small></button>${icon('right')}</div>`).join('') || '<p class="side-empty">Aucune réservation en attente pour cette année.</p>'}</div>`;
  }
  function openDay(value) {
    s.selectedDay = value; const row = dayCoverage(value);
    $('#day-title').textContent = fmt(value,{weekday:'long',month:'long',year:'numeric'});
    const events = calendarEvents().filter(r => r.start <= value && r.end >= value);
    $('#day-content').innerHTML = '<div class="day-places">' + ['clement','elsa'].map(p => `<button class="day-place ${row[p] ? '' : 'missing'}" ${row[p] ? `data-edit="${row[p].id}"` : `data-fill-start="${value}" data-fill-end="${value}" data-fill-owner="${p}"`}><small>${ownerName(p)}</small><strong>${esc(row[p]?.title || '＋ Renseigner le lieu')}</strong></button>`).join('') + '</div>' +
      events.map(r => `<button class="day-event" data-event="${esc(r.id)}"><span class="legend-dot" style="--event-color:${color(r)}"></span><span><strong>${esc(r.title)}</strong><small>${span(r.start,r.end,true)}${r.start_time ? ' · ' + esc(r.start_time) : ''}${r.end_time ? ' → ' + esc(r.end_time) : ''} · ${ownerName(r.owner)}${r.notes ? '\n' + esc(r.notes) : ''}</small></span>${r.status ? `<span class="badge ${r.status}">${r.status === 'booked' ? 'Réservé' : 'À réserver'}</span>` : r.readonly ? '<span class="badge automatic">Session ↗</span>' : ''}</button>`).join('') + (!events.length ? '<p class="side-empty">Aucun autre événement affiché pour cette journée.</p>' : '');
    if (!$('#day-dialog').open) $('#day-dialog').showModal();
  }
  function openEvent(id) {
    const event = calendarEvents().find(r => r.id === id);
    if (!event) return;
    if (event.readonly) { window.location.href = event.url; return; }
    openEditor(null,event.record_id || event.id);
  }
  const input = (name,label,value='',type='text',extra='') => `<label class="field">${label}<input type="${type}" name="${name}" value="${esc(value)}" ${extra}></label>`;
  const textarea = (name,label,value='',extra='') => `<label class="field">${label}<textarea name="${name}" maxlength="20000" ${extra}>${esc(value)}</textarea></label>`;
  const select = (name,label,options,value) => `<label class="field">${label}<select name="${name}">${options.map(([k,v]) => `<option value="${k}" ${k === value ? 'selected' : ''}>${v}</option>`).join('')}</select></label>`;
  const statuses = [['pending','À réserver'],['booked','Réservé'],['not_needed','Pas nécessaire']];
  function openEditor(kind='personal',id=null,defaults={}) {
    if (!s.data) return;
    $('#day-dialog').close();
    s.editing = id ? s.data.records.find(r => r.id === id) : null;
    if (id && !s.editing) { toast('Cet élément n’est plus disponible. Actualisez le planning.'); return; }
    const r = s.editing || {kind:kind || 'personal',owner:s.owner === 'all' ? 'both' : s.owner,start:s.today,end:s.today,...defaults};
    errorAt('#form-error','');
    $('#editor-title').textContent = s.editing ? 'Modifier ' + (r.kind === 'location' ? 'le séjour' : 'cet élément') : (r.kind === 'location' ? 'Où serez-vous ?' : 'Ajouter à votre quotidien');
    $('#delete-record').hidden = !s.editing; $('#duplicate-record').hidden = !s.editing;
    renderForm(r);
    if (!$('#editor').open) $('#editor').showModal();
    setTimeout(() => $('#editor-fields input:not([type=hidden]), #editor-fields select')?.focus(),30);
  }
  function renderForm(r) {
    const kind = r.kind, item = ['shopping','task','note'].includes(kind);
    let html = s.editing ? `<input type="hidden" name="kind" value="${kind}">` : select('kind','Qu’est-ce qu’on ajoute ?',Object.keys(TYPES).filter(k => !k.startsWith('training_')).map(k => [k,TYPES[k].label]),kind);
    html += select('owner','Pour qui ?',[['both','Clément & Elsa'],['clement','Clément'],['elsa','Elsa']],r.owner || 'both');
    if (kind === 'location') html += `<div class="field-row">${select('place','Lieu',Object.entries(PLACES).map(([k,v]) => [k,v.label]),r.place || 'cantal')}${input('destination','Destination du déplacement',r.destination || '', 'text','maxlength="300" placeholder="Ex. Londres, Lyon…"')}</div>`;
    else html += input('title',kind === 'louise' ? 'Intitulé (facultatif)' : 'Intitulé',r.title || (kind === 'louise' ? 'Avec Louise' : kind === 'boarding' ? 'Pension chien' : ''),'text',`maxlength="200" ${['louise','boarding','transport'].includes(kind) ? '' : 'required'}`);
    if (!item) {
      html += `<div class="field-row">${input('start',kind === 'location' || kind === 'louise' ? 'Premier jour inclus' : 'Date de début',r.start,'date','required')}${input('end',kind === 'location' || kind === 'louise' ? 'Dernier jour inclus' : 'Date de fin',r.end || r.start,'date','required')}</div>`;
      if (!['location','louise','boarding'].includes(kind)) html += `<div class="field-row">${input('start_time','Heure de début (facultatif)',r.start_time || '','time')}${input('end_time','Heure de fin (facultatif)',r.end_time || '','time')}</div>`;
    }
    if (kind === 'louise') {
      if (r.series_id && s.editing) html += '<p class="linked-note">Cette date appartient à une série. La modification concerne cette période uniquement. Vous pouvez supprimer toute la série avec le bouton Supprimer.</p>';
      if (!s.editing) html += `<div class="form-section"><h3>${icon('heart')} Gagner du temps sur les dates de garde</h3>${select('repeat','Répétition',[['none','Une seule période'],['weekly','Chaque semaine'],['fortnightly','Une semaine sur deux']],r.repeat || 'none')}<div id="repeat-dates">${input('repeat_until','Répéter jusqu’au (inclus)',r.repeat_until || `${s.cursor.getFullYear()}-12-31`,'date')}</div><p class="form-hint">La même période est répétée tous les 7 ou 14 jours. Chaque date reste modifiable individuellement.</p></div>`;
    }
    if (kind === 'location') {
      if (!s.editing) html += `<label class="check-label"><input name="fill_gaps" type="checkbox" ${r.fill_gaps ? 'checked' : ''}> Remplir seulement les jours sans lieu <span class="sr-only">Les séjours existants sont conservés</span></label><p class="form-hint">Un lieu par jour et par personne. Les séjours existants sont conservés en mode remplissage.</p>`;
      html += '<label class="check-label"><input name="replace_conflicts" type="checkbox"> Remplacer le lieu habituel sur ces dates</label><p class="form-hint">Utile si votre année est déjà remplie. Les dates autour de ce séjour restent inchangées. Un séjour avec des réservations doit être modifié directement.</p>';
      for (const prefix of ['boarding','transport']) {
        const stat = r[prefix + '_status'] || (['paris','away'].includes(r.place) ? 'pending' : 'not_needed');
        html += `<section class="form-section"><h3>${icon(prefix === 'boarding' ? 'paw' : 'plane')} ${prefix === 'boarding' ? 'La pension du chien' : 'Les billets et trajets'}</h3>${select(prefix + '_status','Réservation',statuses,stat)}<div id="${prefix}-dates"><div class="field-row">${input(prefix + '_start',prefix === 'boarding' ? 'Début de pension' : 'Date de l’aller',r[prefix + '_start'] || r.start,'date')}${input(prefix + '_end',prefix === 'boarding' ? 'Fin de pension' : 'Date du retour (facultatif)',r[prefix + '_end'] || (prefix === 'boarding' ? r.end : ''),'date')}</div>${prefix === 'transport' ? `<div class="field-row">${select('transport_mode','Transport',[['Avion','Avion'],['Train','Train'],['Voiture','Voiture'],['Autre','Autre']],r.transport_mode || 'Avion')}${input('transport_origin','Ville de départ / de retour',r.transport_origin || '','text','maxlength="300" placeholder="Ex. Nice"')}</div>` : ''}<p class="form-hint">${prefix === 'boarding' ? 'Ces dates apparaîtront sur le calendrier comme pension réservée.' : 'Les trajets aller et retour seront visibles sur le calendrier. Ajoutez un trajet séparé si le retour se fait dans une autre ville.'}</p></div>${textarea(prefix + '_notes',prefix === 'boarding' ? 'Notes pension (contact, horaires, consignes…)' : 'Notes transport (référence, horaires, bagages…)',r[prefix + '_notes'] || '', 'maxlength="10000"')}</section>`;
      }
    }
    if (kind === 'boarding' || kind === 'transport') {
      html += select('status','Statut',statuses.slice(0,2),r.status || 'pending');
      if (kind === 'transport') html += `<div class="field-row">${input('origin','Départ',r.origin || '', 'text','required maxlength="300" placeholder="Ex. Paris Orly"')}${input('destination','Arrivée',r.destination || '', 'text','required maxlength="300" placeholder="Ex. Nice / Puget"')}</div>${select('mode','Moyen de transport',[['Avion','Avion'],['Train','Train'],['Voiture','Voiture'],['Autre','Autre']],r.mode || 'Avion')}`;
      html += input('reference','Référence de réservation (facultatif)',r.reference || '', 'text','maxlength="300"');
      html += '<p class="form-hint">Réservation indépendante. Pour mettre à jour une réservation déjà liée à un séjour, ouvrez le séjour dans Déplacements.</p>';
    }
    if (item && kind !== 'note') {
      if (kind === 'shopping') html += input('quantity','Quantité (facultatif)',r.quantity || '', 'text','maxlength="80" placeholder="Ex. 2 paquets"');
      if (kind === 'task') html += input('due','Échéance (facultatif)',r.due || '', 'date');
      html += `<label class="check-label"><input type="checkbox" name="done" ${r.done ? 'checked' : ''}> ${kind === 'shopping' ? 'Déjà acheté' : 'Terminé'}</label>`;
    }
    html += textarea('notes',kind === 'note' ? 'Votre note' : 'Notes et informations utiles',r.notes || '');
    $('#editor-fields').innerHTML = html;
    updateConditionalFields();
  }
  function updateConditionalFields() {
    const form = $('#event-form');
    for (const prefix of ['boarding','transport']) {
      const status = form.elements[prefix + '_status'];
      if (!status) continue;
      const visible = status.value === 'booked', area = $(`#${prefix}-dates`);
      area.hidden = !visible;
      $$('input,select',area).forEach(el => { el.disabled = !visible; el.required = visible && (el.name === prefix + '_start' || prefix === 'boarding' && el.name === 'boarding_end'); });
    }
    if ($('#repeat-dates')) { const repeating = form.elements.repeat.value !== 'none'; $('#repeat-dates').hidden = !repeating; form.elements.repeat_until.disabled = !repeating; form.elements.repeat_until.required = repeating; }
    if (form.elements.kind.value === 'location') {
      const dest = form.elements.destination, away = form.elements.place.value === 'away';
      dest.closest('.field').hidden = !away; dest.required = away;
    }
  }
  function formValue() {
    const form = $('#event-form'), data = Object.fromEntries(new FormData(form));
    data.done = form.elements.done?.checked || false;
    data.fill_gaps = form.elements.fill_gaps?.checked || false;
    data.replace_conflicts = form.elements.replace_conflicts?.checked || false;
    if (s.editing) data.revision = s.editing.revision;
    return data;
  }
  async function save(e) {
    e.preventDefault(); const button = $('#save-record'); if (button.disabled) return;
    button.disabled = true; button.textContent = 'Enregistrement…'; errorAt('#form-error','');
    try {
      const payload = formValue();
      const result = await api(s.editing ? `/records/${s.editing.id}` : '/records',{method:s.editing ? 'PUT' : 'POST',body:JSON.stringify(payload)});
      if (payload.start && (s.tab === 'calendar' || s.listScope === 'year')) s.cursor = date(payload.start);
      $('#editor').close();
      toast(result.count === 0 ? 'Tous ces jours ont déjà un lieu. Aucun séjour n’a été modifié.' : result.count > 1 ? `${result.count} périodes enregistrées.` : 'Enregistré dans votre planning partagé.');
      await load();
    } catch (e) { errorAt('#form-error',e.message); $('#form-error').scrollIntoView({block:'nearest'}); }
    finally { button.disabled = false; button.textContent = 'Enregistrer'; }
  }
  function fillYear() { const y = s.cursor.getFullYear(); openEditor('location',null,{start:`${y}-01-01`,end:`${y}-12-31`,fill_gaps:true,place:'cantal',boarding_status:'not_needed',transport_status:'not_needed'}); }
  async function navigate(delta) {
    if (!s.data || s.loading) return;
    const before = new Date(s.cursor), old = s.cursor.getFullYear();
    if (s.tab !== 'calendar' || s.view === 'year') s.cursor.setFullYear(old + delta);
    else if (s.view === 'week') s.cursor.setDate(s.cursor.getDate() + 7 * delta);
    else { s.cursor.setDate(1); s.cursor.setMonth(s.cursor.getMonth() + delta); }
    if (s.cursor.getFullYear() < 2000 || s.cursor.getFullYear() > 2100) { s.cursor.setFullYear(old); return; }
    if (old !== s.cursor.getFullYear()) { if (!await load()) s.cursor = before; } else renderView();
  }
  document.addEventListener('click', async e => {
    const target = e.target.closest('button,a,[data-day]'); if (!target) return;
    if (target.dataset.close) { $('#' + target.dataset.close).close(); return; }
    if (!s.data) return;
    if (target.dataset.tab) { setTab(target.dataset.tab); return; }
    if (target.dataset.new) { openEditor(target.dataset.new); return; }
    if (target.dataset.edit) { openEditor(null,target.dataset.edit); return; }
    if (target.dataset.event) { openEvent(target.dataset.event); return; }
    if (target.dataset.url) { window.location.href = target.dataset.url; return; }
    if (target.dataset.fillStart) { openEditor('location',null,{start:target.dataset.fillStart,end:target.dataset.fillEnd,owner:target.dataset.fillOwner,fill_gaps:true,place:'cantal'}); return; }
    if (target.dataset.day) { openDay(target.dataset.day); return; }
    if (target.dataset.view) { s.view = target.dataset.view; renderView(); return; }
    if (target.id === 'fill-year-inline') fillYear();
  });
  document.addEventListener('keydown', e => { if (['Enter',' '].includes(e.key) && e.target.matches('.calendar-day')) { e.preventDefault(); openDay(e.target.dataset.day); } });
  document.addEventListener('change', async e => {
    const el = e.target;
    if (el.dataset.filter) { if (el.checked) s.hidden.delete(el.dataset.filter); else s.hidden.add(el.dataset.filter); renderView(); }
    if (el.id === 'owner-filter') { s.owner = el.value; renderView(); }
    if (el.id === 'list-scope') { s.listScope = el.value; renderList(); }
    if (el.dataset.toggle) {
      const r = s.data.records.find(r => r.id === el.dataset.toggle); if (!r) return; el.disabled = true;
      try { await api(`/records/${r.id}`,{method:'PUT',body:JSON.stringify({...r,done:el.checked})}); await load(); }
      catch (e) { el.checked = !el.checked; el.disabled = false; errorAt('#load-error',e.message); }
    }
    if (el.closest('#event-form')) {
      if (el.name === 'fill_gaps' && el.checked) $('#event-form').elements.replace_conflicts.checked = false;
      if (el.name === 'replace_conflicts' && el.checked && $('#event-form').elements.fill_gaps) $('#event-form').elements.fill_gaps.checked = false;
      if (el.name === 'kind' && !s.editing) { const previous = formValue(); renderForm({kind:el.value,owner:previous.owner,start:previous.start || s.today,end:previous.end || s.today}); }
      if (el.name === 'place') {
        const form = $('#event-form');
        if (!s.editing) for (const prefix of ['boarding','transport']) if (form.elements[prefix + '_status'].value !== 'booked') form.elements[prefix + '_status'].value = ['paris','away'].includes(el.value) ? 'pending' : 'not_needed';
      }
      if (el.name === 'start') {
        const form = $('#event-form'); if (form.elements.end.value < el.value) form.elements.end.value = el.value;
      }
      if (/^(boarding|transport)_(start|end)$/.test(el.name)) el.dataset.manual = 'true';
      if (!s.editing && ['start','end','boarding_status','transport_status'].includes(el.name)) {
        const form = $('#event-form');
        for (const prefix of ['boarding','transport']) {
          const first = form.elements[prefix + '_start'], last = form.elements[prefix + '_end'];
          if (first && !first.dataset.manual) first.value = form.elements.start.value;
          if (last && !last.dataset.manual && prefix === 'boarding') last.value = form.elements.end.value;
        }
      }
      updateConditionalFields();
    }
  });
  document.addEventListener('input', e => {
    if (e.target.id === 'list-search') {
      s.search = e.target.value; const pos = e.target.selectionStart; renderList(); $('#list-search').focus(); try { $('#list-search').setSelectionRange(pos,pos); } catch (_) { /* search selection varies across browsers */ }
    }
  });
  document.addEventListener('submit', async e => {
    if (e.target.id !== 'quick-add') return;
    e.preventDefault(); const form = e.target, btn = $('button',form); btn.disabled = true;
    try { await api('/records',{method:'POST',body:JSON.stringify({kind:s.tab,title:form.elements.title.value,owner:s.owner === 'all' ? 'both' : s.owner})}); await load(); $('#quick-add input')?.focus(); }
    catch (e) { btn.disabled = false; errorAt('#load-error',e.message); }
  });
  $('#event-form').addEventListener('submit',save);
  $('#refresh').addEventListener('click',load);
  $('#add-main').addEventListener('click',() => openEditor(['calendar','training','alerts'].includes(s.tab) ? 'personal' : s.tab));
  $('#add-main').disabled = true;
  $('#prev').addEventListener('click',() => navigate(-1)); $('#next').addEventListener('click',() => navigate(1));
  $('#today-button').addEventListener('click',async () => { const before = new Date(s.cursor); s.cursor = date(s.today); if (s.cursor.getFullYear() !== before.getFullYear()) { if (!await load()) s.cursor = before; } else renderView(); });
  $('#day-add').addEventListener('click',() => openEditor('personal',null,{start:s.selectedDay,end:s.selectedDay}));
  $('#fill-year').addEventListener('click',fillYear);
  $('#reset-filters').addEventListener('click',() => { s.hidden.clear(); renderLegend(); renderView(); });
  $('#duplicate-record').addEventListener('click',() => { const copy = {...formValue()}; delete copy.revision; delete copy.series_id; openEditor(copy.kind,null,copy); });
  $('#delete-record').addEventListener('click',() => { $('#confirm-dialog .dialog-body > p').textContent = s.editing?.kind === 'location' ? 'Le séjour et ses réservations liées (pension et trajets) seront supprimés du planning partagé.' : 'Cet élément sera supprimé du planning partagé.'; $('#delete-series-label').hidden = !s.editing?.series_id; $('#delete-series').checked = false; errorAt('#delete-error',''); $('#confirm-dialog').showModal(); });
  $('#confirm-delete').addEventListener('click',async () => {
    if (!s.editing) return; const btn = $('#confirm-delete'); btn.disabled = true;
    try { const result = await api(`/records/${s.editing.id}`,{method:'DELETE',body:JSON.stringify({revision:s.editing.revision,delete_series:$('#delete-series').checked})}); $('#confirm-dialog').close(); $('#editor').close(); toast(result.count > 1 ? `${result.count} périodes supprimées.` : 'Élément supprimé.'); await load(); }
    catch (e) { errorAt('#delete-error',e.message); }
    finally { btn.disabled = false; }
  });
  document.addEventListener('visibilitychange',() => { if (!document.hidden && !s.loading && !$$('dialog[open]').length && Date.now() - s.lastLoaded > 60000) load(); });
  load();
})();
