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
    transport:{label:'Transports',icon:'plane',color:'#4b9b9e'},personal:{label:'Rendez-vous / événement',icon:'calendar',color:'#8674b9'},
    restaurant:{label:'Restaurant',icon:'restaurant',color:'#bd6c55'},
    professional:{label:'Rendez-vous pro',icon:'work',color:'#647a9a'},task:{label:'À faire',icon:'task',color:'#82914c'},
    training_start:{label:'Début de formation',icon:'work',color:'#4b929e'},training_onsite:{label:'Début de présentiel',icon:'work',color:'#6575bd'},
    training_end:{label:'Fin de formation',icon:'work',color:'#6b9a71'},training_exam:{label:'Examen',icon:'work',color:'#bc8f37'},
    location:{label:'Lieu / séjour',icon:'pin',color:'#7c65bc'},shopping:{label:'Liste de courses',icon:'bag',color:'#78a489'},note:{label:'Note',icon:'note',color:'#b39b6e'}
  };
  const PLACES = {paris:{label:'Paris',color:'#7c65bc',icon:'eiffel'},puget:{label:'Puget',color:'#c09240',icon:'coast'},cantal:{label:'Cantal',color:'#4e987c',icon:'mountain'},away:{label:'Déplacement',color:'#5b8fb3',icon:'pin'}};
  const placeLabel = (key,title) => `<span class="place-mark" style="--place-color:${PLACES[key]?.color || '#a198ac'}">${PLACES[key] ? icon(PLACES[key].icon) : ''}<span class="place-text">${esc(title)}</span></span>`;
  const TABS = [ ['dashboard','Tableau de bord','dashboard'],['calendar','Calendrier','calendar'],['louise','Louise','heart'],['location','Séjours','pin'],['boarding','Pension chien','paw'],['transport','Transports','plane'],['restaurant','Restaurants','restaurant'],['shopping','Courses','bag'],['task','À faire','task'],['note','Notes','note'],['training','Formations','work'],['alerts','Anomalies','alert'] ];
  const s = {data:null,today,cursor:date(today),tab:'dashboard',view:'month',owner:'all',hidden:new Set(),editing:null,listScope:'year',search:'',selectedDay:today,shoppingList:'autre',loading:false,lastLoaded:0,request:0,drag:null,moving:false};
  const BOARDING_PLACES = {itana:'Itana',lafeuillade:'Lafeuillade'};
  const mealLabel = r => ({lunch:'Midi',dinner:'Soir',other:'Autre moment'}[r.meal] || '');
  const displayTitle = r => `${r.important ? '★ ' : ''}${r.kind === 'restaurant' ? mealLabel(r) + ' · ' : ''}${r.title}${r.kind === 'boarding' && BOARDING_PLACES[r.boarding_location] && !r.title.includes(BOARDING_PLACES[r.boarding_location]) ? ' · ' + BOARDING_PLACES[r.boarding_location] : ''}`;
  const isSsiap = r => r.ssiap === true || /SSIAP/i.test(`${r.formation || ''} ${r.title || ''}`);
  const color = r => isSsiap(r) ? '#c62828' : (r.kind === 'location' ? PLACES[r.place]?.color : TYPES[r.kind]?.color) || '#8674b9';
  const STATUS_LABELS = {pending:'À réserver',booked:'Réservé',needs_change:'À modifier',not_needed:'Pas nécessaire'};
  const statusLabel = r => STATUS_LABELS[r.status] || '';
  const statusBadge = r => r.status ? `<span class="badge ${esc(r.status)}">${r.status === 'booked' ? '✓ ' : r.status === 'not_needed' ? '' : '! '}${statusLabel(r)}</span>` : '';
  const dayOrder = (a,b) => (a.kind === 'transport' ? 0 : a.kind === 'boarding' ? 1 : 2) - (b.kind === 'transport' ? 0 : b.kind === 'boarding' ? 1 : 2) || (a.start_time || '').localeCompare(b.start_time || '') || a.title.localeCompare(b.title);
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
      .filter(r => owns(r) && r.status !== 'not_needed' && !(r.milestones || [r.kind]).every(k => s.hidden.has(k)) && !(isSsiap(r) && s.hidden.has('ssiap'))).sort((a,b) => a.start.localeCompare(b.start) || dayOrder(a,b));
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
    $('#today-places').innerHTML = ['clement','elsa'].map(p => `<button class="today-person" data-day="${s.today}"><span class="avatar ${p}">${p === 'clement' ? 'C' : 'E'}</span><span><strong>${ownerName(p)}</strong><small>${esc(td[p]?.title || 'Lieu à renseigner')}</small></span>${icon(PLACES[td[p]?.place]?.icon || 'pin')}</button>`).join('');
    $('#upcoming').innerHTML = futureAlerts.slice(0,3).map(a => `<button class="prepare-item" data-edit="${esc(a.record_id)}"><span class="prepare-icon">${icon(a.kind === 'boarding' ? 'paw' : 'plane')}</span><span><strong>${esc(a.title)}</strong><small>${span(a.start,a.end)}</small></span></button>`).join('') || '<p class="side-empty">Aucune réservation en attente. Vous pouvez préparer votre prochain séjour.</p>';
    renderLegend(); renderView();
  }
  function renderLegend() {
    $('#legend').innerHTML = '<p class="legend-group">Vos lieux</p>' + Object.entries(PLACES).map(([key,v]) => `<div class="legend-label">${placeLabel(key,v.label)}</div>`).join('') +
      '<p class="legend-group">Vie personnelle</p>' + Object.entries(TYPES).filter(([k]) => ['louise','boarding','transport','restaurant','personal','task'].includes(k)).map(legendCheck).join('') +
      '<p class="legend-group">Vie professionnelle</p>' + legendCheck(['ssiap',{label:'Formations SSIAP',color:'#c62828'}]) + Object.entries(TYPES).filter(([k]) => k.startsWith('training_') || k === 'professional').map(legendCheck).join('');
  }
  function legendCheck([key,v]) { return `<label class="legend-label"><input type="checkbox" data-filter="${key}" ${s.hidden.has(key) ? '' : 'checked'}><span class="legend-dot" style="--event-color:${v.color}"></span>${v.label}</label>`; }
  function renderView() {
    const calendar = s.tab === 'calendar', dashboard = s.tab === 'dashboard', undated = ['shopping','task','note','dashboard'].includes(s.tab);
    document.body.classList.toggle('dashboard-active',dashboard);
    $('#view-switch').hidden = !calendar; $('#calendar-footer').hidden = !calendar; $('#today-button').hidden = !calendar;
    $('#calendar-actions').hidden = !calendar;
    $('#export-pdf').hidden = s.view === 'year';
    $('#export-pdf').title = `Imprimer le planning de ${s.cursor.toLocaleDateString('fr-FR',{month:'long',year:'numeric'})}`;
    $('#prev').hidden = undated; $('#next').hidden = undated; $('#view-intro').hidden = calendar || dashboard;
    $$('#view-switch button').forEach(b => { b.classList.toggle('active',b.dataset.view === s.view); b.setAttribute('aria-pressed',b.dataset.view === s.view); });
    $('#period-label').textContent = undated ? TABS.find(t => t[0] === s.tab)[1] : calendar && s.view !== 'year' ? s.cursor.toLocaleDateString('fr-FR',{month:'long',year:'numeric'}) : String(s.cursor.getFullYear());
    if (dashboard) renderDashboard();
    else if (calendar) { if (s.view === 'year') renderYear(); else renderCalendar(); }
    else renderList();
  }
  function chip(r,value) {
    const label = statusLabel(r), status = r.status || '', title = `${displayTitle(r)}${label ? ' · ' + label : ''} · ${span(r.start,r.end)}${r.estimated_date ? ' · Date prévue à confirmer' : ''}`;
    const movable = !r.readonly && s.data.records.some(record => record.id === (r.record_id || r.id));
    const hint = movable ? 'Glissez vers une autre date, ou cliquez pour modifier.' : 'Date synchronisée : modifiez-la dans la session de formation.';
    return `<button class="event-chip ${status} ${r.start < value ? 'continued' : ''} ${isSsiap(r) ? 'ssiap-event' : ''} ${r.important ? 'important-event' : ''}" style="--event-color:${color(r)}" data-event="${esc(r.id)}" draggable="${movable}" title="${esc(title + ' · ' + hint)}" aria-label="${esc(title)}"${movable ? ' aria-describedby="calendar-move-help"' : ''}>${label ? `<span class="event-status">${status === 'booked' ? '✓' : '!'} ${label}</span>` : ''}<span class="event-title">${r.start_time ? esc(r.start_time) + ' ' : ''}${esc(displayTitle(r))}</span></button>`;
  }
  function clearDrag() {
    clearTimeout(s.dragNavTimer); s.dragNav = null;
    s.drag = null;
    document.body.classList.remove('calendar-dragging');
    $$('.drag-source,.drop-target,.drag-nav-target').forEach(el => el.classList.remove('drag-source','drop-target','drag-nav-target'));
  }
  function movePayload(drag, targetDay) {
    // Compare civil dates in UTC so DST and the browser's timezone cannot add a day.
    const delta = (Date.parse(targetDay + 'T00:00:00Z') - Date.parse(drag.day + 'T00:00:00Z')) / 86400000;
    const record = {...drag.record}, event = drag.event;
    if (record.kind === 'task') record.due = add(record.due,delta);
    else if (event.linked && record.kind === 'location') {
      if (event.kind === 'boarding') {
        record.boarding_start = add(event.start,delta);
        record.boarding_end = add(event.end,delta);
      } else {
        // Each leg moves independently; do not move the stay or the other flight.
        const field = event.direction === 'return' ? 'transport_end' : 'transport_start';
        record[field] = add(event.start,delta);
        if (event.direction !== 'return' && record.transport_round_trip !== false && !record.transport_end && record.transport_start > record.end) {
          throw new Error('Le départ dépasserait la date de retour prévue. Déplacez d’abord le retour ou modifiez le séjour.');
        }
        // A projected return date must never turn into a confirmed booking by dragging it.
        if (event.estimated_date && record.transport_status === 'booked') record.transport_status = 'needs_change';
      }
    } else {
      record.start = add(record.start,delta);
      record.end = add(record.end,delta);
    }
    return record;
  }
  async function moveEvent(drag, targetDay) {
    if (s.moving || targetDay === drag.day) return;
    s.moving = true;
    document.body.classList.add('calendar-saving');
    $('#view').setAttribute('aria-busy','true');
    $('#save-state').textContent = 'Déplacement en cours…';
    errorAt('#load-error','');
    try {
      const payload = movePayload(drag,targetDay);
      await api(`/records/${payload.id}`,{method:'PUT',body:JSON.stringify(payload)});
      // The server is the source of truth: never leave a failed move on the screen.
      const refreshed = await load();
      toast(refreshed ? 'Date déplacée dans votre planning partagé.' : 'Déplacement enregistré. Cliquez sur Actualiser pour afficher les nouvelles dates.');
    } catch (e) {
      $('#save-state').textContent = 'Déplacement non confirmé · actualisez le planning avant de réessayer.';
      errorAt('#load-error',e.message);
      toast(e.message);
    } finally {
      s.moving = false;
      document.body.classList.remove('calendar-saving');
      $('#view').removeAttribute('aria-busy');
    }
  }
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
      const ev = events.filter(r => r.start <= value && r.end >= value).sort(dayOrder), limit = week ? ev.length : 4;
      html += `<div class="calendar-day ${day.getMonth() !== s.cursor.getMonth() && !week ? 'outside' : ''} ${value === s.today ? 'today' : ''}" data-day="${value}" tabindex="0" role="group" aria-label="${esc(fmt(value,{weekday:'long',month:'long',year:'numeric'}))}${missingDay(row) ? ' — lieu à compléter' : ''}"><div class="day-top"><span class="day-number">${day.getDate()}</span>${missingDay(row) ? '<span class="coverage-dot" title="Lieu à compléter"></span>' : ''}<button class="day-add-button" data-add-date="${value}" aria-label="Ajouter un rendez-vous le ${esc(fmt(value,{month:'long'}))}">+</button></div><div class="location-lines">${persons.map(p => `<span class="location-line ${row[p] ? '' : 'missing'}" style="--event-color:${PLACES[row[p]?.place]?.color || '#edcfc9'}" title="${ownerName(p)} : ${esc(row[p]?.title || 'lieu manquant')}"></span>`).join('')}</div><span class="place-name">${title ? [...new Map(persons.filter(p => row[p]).map(p => [row[p].title,row[p]])).values()].map(r => placeLabel(r.place,r.title)).join('<span aria-hidden="true"> / </span>') : 'Lieu à compléter'}</span>${ev.slice(0,limit).map(r => chip(r,value)).join('')}${ev.length > limit ? `<button class="more-events" data-day="${value}">+ ${ev.length - limit} autre${ev.length - limit > 1 ? 's' : ''}</button>` : ''}</div>`;
    }
    $('#view').innerHTML = html + '</div>';
    $('#view').style.setProperty('--calendar-weeks', String(days / 7));
  }
  function renderYear() {
    const year = s.cursor.getFullYear(), events = calendarEvents();
    let html = '<div class="year-grid">';
    for (let m = 0; m < 12; m++) {
      const first = new Date(year,m,1), count = new Date(year,m + 1,0).getDate();
      html += `<section class="mini-month"><h3>${first.toLocaleDateString('fr-FR',{month:'long'})}</h3><div class="mini-grid">${['L','M','M','J','V','S','D'].map(x => `<span>${x}</span>`).join('')}${'<span></span>'.repeat((first.getDay() + 6) % 7)}`;
      for (let n = 1; n <= count; n++) {
        const value = iso(new Date(year,m,n)), missing = missingDay(dayCoverage(value));
        const dayEvents = events.filter(r => r.start <= value && r.end >= value);
        html += `<button class="mini-day ${missing ? 'missing' : 'covered'} ${value === s.today ? 'today' : ''}" data-day="${value}" title="${esc(fmt(value,{month:'long'}))} · ${missing ? 'Lieu à compléter' : 'Lieux renseignés'}">${n}${dayEvents.length ? `<span class="mini-event-dot" style="background:${dayEvents.some(isSsiap) ? '#c62828' : '#7360b6'}"></span>` : ''}</button>`;
      }
      html += '</div></section>';
    }
    $('#view').innerHTML = html + '</div><p class="year-key">Vert : lieux renseignés · Rose : lieu manquant · Point : événement prévu (rouge pour SSIAP). Les 365 jours de l’année sont contrôlés (366 les années bissextiles).</p>';
  }
  function nextDateLabel(value) {
    const days = Math.round((date(value) - date(s.today)) / 86400000);
    return days <= 0 ? 'En cours' : days === 1 ? 'Demain' : `Dans ${days} jours`;
  }
  function renderDashboard() {
    const records = s.data.records.filter(owns), bookings = s.data.reservations.filter(owns);
    const next = items => items.filter(r => r.end >= s.today && r.status !== 'not_needed').sort((a,b) => a.start.localeCompare(b.start) || (a.start_time || '').localeCompare(b.start_time || ''))[0];
    const places = dayCoverage(s.today);
    const upcoming = [...records.filter(r => ['louise','personal','professional','restaurant'].includes(r.kind)),...bookings,...s.data.training.filter(owns)]
      .filter(r => r.end >= s.today && r.start <= add(s.today,7) && r.status !== 'not_needed')
      .sort((a,b) => a.start.localeCompare(b.start) || (a.start_time || '').localeCompare(b.start_time || ''));
    const alerts = s.data.alerts.filter(a => a.end >= s.today && owns(s.data.records.find(r => r.id === a.record_id) || {owner:'both'}));
    const pendingTasks = records.filter(r => r.kind === 'task' && !r.done).sort((a,b) => (a.due || '9999').localeCompare(b.due || '9999'));
    const missing = s.data.coverage.days.filter(r => r.date >= s.today && missingDay(r)).length;
    const card = (label,subtitle,entry,kind,extra='',placeKey='') => `<article class="dash-card" style="--card-color:${PLACES[placeKey]?.color || TYPES[kind]?.color || '#7360b6'}"><div class="dash-card-top"><span class="dash-icon ${placeKey ? 'dash-place-icon' : ''}">${icon(PLACES[placeKey]?.icon || TYPES[kind]?.icon || 'pin')}</span><span class="dash-overline">${esc(label)}</span>${entry ? `<span class="dash-countdown">${nextDateLabel(entry.start)}</span>` : ''}</div><h3>${entry ? fmt(entry.start < s.today ? s.today : entry.start,{month:'long'}) : 'À prévoir'}</h3><p>${esc(subtitle || (entry ? displayTitle(entry) : 'Aucune date renseignée'))}</p>${entry ? `<div class="dash-card-info">${span(entry.start,entry.end,true)} · ${ownerName(entry.owner)}</div>${entry.status ? statusBadge(entry) : ''}<button class="dash-card-link" data-edit="${esc(entry.record_id || entry.id)}">Voir le détail ${icon('right')}</button>` : `<button class="dash-card-link" data-new="${kind}" ${extra}>${icon('plus')} Ajouter une date</button>`}</article>`;
    const departures = Object.entries(PLACES).filter(([key]) => key !== 'away').map(([key,place]) => {
      const stays = records.filter(r => r.kind === 'location' && r.place === key && (r.transport_start || r.start) >= s.today)
        .map(r => ({...r,start:r.transport_status !== 'not_needed' && r.transport_start ? r.transport_start : r.start}));
      const journeys = bookings.filter(r => r.kind === 'transport' && r.start >= s.today && (r.destination || '').toLocaleLowerCase('fr').includes(key));
      const entry = next([...stays,...journeys]);
      return card(`Prochain départ · ${place.label}`,entry ? `Cap sur ${place.label}` : `Votre prochain séjour à ${place.label}`,entry,'location',`data-place="${key}"`,key);
    }).join('');
    const louise = next(records.filter(r => r.kind === 'louise'));
    const boarding = next(bookings.filter(r => r.kind === 'boarding'));
    const now = new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',hour:'2-digit',minute:'2-digit'}).format(new Date());
    const restaurant = next(records.filter(r => r.kind === 'restaurant' && (r.start > s.today || r.start === s.today && r.start_time >= now)));
    const dayEntry = r => `<button class="dash-agenda-row" style="--event-color:${color(r)}" ${r.readonly ? `data-url="${esc(r.url)}"` : `data-edit="${esc(r.record_id || r.id)}"`}><span class="dash-date"><strong>${fmt(r.start < s.today ? s.today : r.start,{month:undefined})}</strong><small>${fmt(r.start < s.today ? s.today : r.start,{day:undefined})}</small></span><span class="dash-agenda-copy"><strong ${isSsiap(r) ? 'style="color:#c62828"' : ''}>${esc(displayTitle(r))}</strong><small>${r.start_time ? esc(r.start_time) + ' · ' : ''}${r.start < s.today ? 'En cours · ' : ''}${ownerName(r.owner)}</small></span>${r.status ? statusBadge(r) : icon('right')}</button>`;
    $('#view').innerHTML = `<div class="dashboard"><section class="dash-hero"><div><p class="eyebrow">VOTRE QUOTIDIEN, EN UN REGARD</p><h2>${fmt(s.today,{weekday:'long',month:'long'})}</h2><p>Les prochaines dates, les réservations et ce qu’il reste à préparer.</p><div class="dash-today">${['clement','elsa'].map(p => `<button data-day="${s.today}"><span class="avatar ${p}">${p === 'clement' ? 'C' : 'E'}</span><span>${ownerName(p)}<strong>${placeLabel(places[p]?.place,places[p]?.title || 'Lieu à compléter')}</strong></span></button>`).join('')}</div></div><div class="dash-hero-action"><span class="dash-hero-number">${upcoming.length}</span><span>événement${upcoming.length > 1 ? 's' : ''} sur les 7 prochains jours</span><button class="button" data-tab="calendar">${icon('calendar')} Ouvrir le calendrier</button></div></section><div class="dash-section-heading"><h2>Vos prochaines étapes</h2><span>Mis à jour avec votre planning partagé</span></div><section class="dash-cards">${departures}${card('Prochaine fois avec Louise',louise ? displayTitle(louise) : 'Week-ends, vacances et moments ensemble',louise,'louise')}${card('Prochaine pension',boarding ? BOARDING_PLACES[boarding.boarding_location] || 'Lieu à préciser : Itana ou Lafeuillade' : 'Itana ou Lafeuillade',boarding,'boarding')}${card('Prochain restaurant',restaurant ? `${mealLabel(restaurant)} · ${restaurant.start_time} · ${restaurant.title}` : 'Une table à prévoir',restaurant,'restaurant')}</section><section class="dash-bottom"><article class="dash-panel"><div class="dash-panel-heading"><h2>Les 7 prochains jours</h2><button class="text-button" data-add-date="${s.today}">+ Ajouter</button></div>${upcoming.slice(0,9).map(dayEntry).join('') || '<p class="dash-empty">Votre agenda est libre pour le moment. Ajoutez un rendez-vous ou un restaurant.</p>'}${upcoming.length > 9 ? '<button class="text-button dash-see-all" data-tab="calendar">Voir toutes les dates</button>' : ''}</article><article class="dash-panel"><div class="dash-panel-heading"><h2>À préparer</h2><span class="badge">${alerts.length + pendingTasks.length}</span></div>${alerts.slice(0,4).map(a => `<button class="dash-attention" data-edit="${esc(a.record_id)}">${icon(a.kind === 'boarding' ? 'paw' : 'plane')}<span><strong>${esc(a.title)}</strong><small>${span(a.start,a.end,true)}</small></span>${icon('right')}</button>`).join('')}${pendingTasks.slice(0,3).map(r => `<button class="dash-attention" data-edit="${r.id}">${icon('task')}<span><strong>${esc(r.title)}</strong><small>${r.due ? fmt(r.due,{year:'numeric'}) : 'Sans échéance'}</small></span></button>`).join('')}${!alerts.length && !pendingTasks.length ? '<p class="dash-empty">Aucune réservation ni tâche en attente.</p>' : ''}<div class="dash-location-health"><strong>${missing ? `${missing} jour${missing > 1 ? 's' : ''} à compléter` : 'Lieux renseignés'}</strong><p>Sur la fin de l’année affichée (${s.data.year}).</p><button class="text-button" data-tab="alerts">Vérifier les lieux et réservations ${icon('right')}</button></div></article></section></div>`;
  }
  function transportGroups(records) {
    const groups = new Map();
    for (const r of records) {
      const key = r.linked ? r.record_id : r.id;
      if (!groups.has(key)) groups.set(key,{id:key,title:r.linked ? `Séjour à ${r.stay}` : r.title,linked:!!r.linked,legs:[]});
      groups.get(key).legs.push(r);
    }
    return [...groups.values()].sort((a,b) => a.legs[0].start.localeCompare(b.legs[0].start));
  }
  function renderTransportList(records) {
    const groups = transportGroups(records);
    $('#view').innerHTML = `<div class="list-content"><button class="button small" data-new="transport">${icon('plus')} Ajouter un trajet indépendant</button><div class="journeys">${groups.map(g => `<article class="journey-card"><header><span class="journey-icon">${icon('plane')}</span><div><h3>${esc(g.title)}</h3><p>${g.linked ? 'Un seul séjour · ' : ''}${g.legs.length > 1 ? 'Aller et retour' : 'Trajet'} · ${ownerName(g.legs[0].owner)}</p></div><button class="button small" data-edit="${g.id}">Modifier</button></header><div class="journey-legs">${g.legs.map(r => `<div class="journey-leg"><span class="journey-direction">${r.direction === 'return' ? 'Retour' : r.direction === 'outbound' ? 'Aller' : 'Trajet'}</span><strong>${fmt(r.start,{year:'numeric'})}${r.start_time ? ' · ' + esc(r.start_time) : ''}</strong><span>${esc(r.origin || 'Départ à préciser')} ${icon('arrow')} ${esc(r.destination || 'Arrivée à préciser')}</span>${statusBadge(r)}${r.estimated_date ? '<small>Date de retour prévue à confirmer</small>' : ''}</div>`).join('')}</div>${g.legs[0].notes ? `<p class="journey-notes">${esc(g.legs[0].notes)}</p>` : ''}</article>`).join('') || '<div class="empty-state"><h3>Aucun trajet pour cette sélection</h3><p>Ajoutez un séjour avec transport ou un trajet indépendant.</p></div>'}</div></div>`;
  }
  function shoppingLists() { return s.data.shopping_lists || [{id:'autre',name:'Autre',revision:1}]; }
  function shoppingNavigation() {
    const lists = shoppingLists();
    if (!lists.some(l => l.id === s.shoppingList)) s.shoppingList = lists[0].id;
    return `<div class="shopping-tabs" role="tablist" aria-label="Listes de courses">${lists.map(l => `<button role="tab" aria-selected="${l.id === s.shoppingList}" data-shopping-list="${l.id}" class="${l.id === s.shoppingList ? 'active' : ''}">${esc(l.name)}<span>${s.data.records.filter(r => r.kind === 'shopping' && (r.list_id || 'autre') === l.id && !r.done && owns(r)).length}</span></button>`).join('')}<button id="new-shopping-list">${icon('plus')} Nouvelle liste</button></div><div class="shopping-list-heading"><h3>${esc(lists.find(l => l.id === s.shoppingList).name)}</h3><button class="text-button" id="rename-shopping-list">Renommer cette liste</button></div>`;
  }
  function openShoppingList(rename=false) {
    const current = rename ? shoppingLists().find(l => l.id === s.shoppingList) : null;
    s.editingList = current;
    $('#shopping-list-title').textContent = rename ? 'Renommer la liste' : 'Nouvelle liste de courses';
    $('#shopping-list-name').value = current?.name || '';
    errorAt('#shopping-list-error',''); $('#shopping-list-dialog').showModal(); $('#shopping-list-name').focus();
  }
  const empty = (title,text,type = 'personal') => `<div class="empty-state"><div class="empty-icon">${icon(TYPES[type]?.icon || 'calendar')}</div><h3>${esc(title)}</h3><p>${esc(text)}</p><button class="button primary" data-new="${type}">${icon('plus')} Ajouter</button></div>`;
  function listRecords() {
    let records;
    if (s.tab === 'training') records = s.data.training;
    else if (s.tab === 'boarding' || s.tab === 'transport') records = s.data.reservations.filter(r => r.kind === s.tab);
    else records = s.data.records.filter(r => r.kind === s.tab);
    return records.filter(owns).filter(r => s.tab !== 'shopping' || (r.list_id || 'autre') === s.shoppingList).filter(r => !r.start || s.listScope === 'all' || (s.listScope === 'future' ? r.end >= s.today : inYear(r)))
      .filter(r => `${r.title} ${r.notes || ''} ${r.destination || ''} ${r.origin || ''}`.toLocaleLowerCase('fr').includes(s.search.toLocaleLowerCase('fr')))
      .sort((a,b) => Number(!!a.done) - Number(!!b.done) || (a.start || a.due || '9999').localeCompare(b.start || b.due || '9999') || a.title.localeCompare(b.title));
  }
  const descriptions = {
    louise:'Les jours avec Louise, les week-ends et les vacances. Ajoutez aussi des périodes une semaine sur deux.',
    location:'Vos lieux de vie, jour par jour. Les dates de début et de fin sont incluses dans chaque période.',
    boarding:'Les périodes de pension, avec leur statut et leurs dates de réservation réelles.',
    transport:'Un seul encadré par séjour, avec les dates et les statuts de l’aller et du retour.',
    restaurant:'Vos tables réservées, à midi ou le soir, avec l’heure, l’adresse et les notes.',
    shopping:'Vos courses par lieu. Créez vos listes, renommez-les et cochez les achats au fur et à mesure.',
    task:'Les choses à ne pas oublier. Une tâche avec une échéance apparaît aussi dans le calendrier.',
    note:'Vos idées, informations pratiques et notes à retrouver facilement.',
    training:'Dates récupérées automatiquement depuis les sessions. Les modifications se font dans la fiche de formation.',
    alerts:'Repérez les jours sans lieu et les réservations qui restent à préparer.'
  };
  function renderList() {
    const dated = !['shopping','task','note','alerts'].includes(s.tab);
    $('#view-intro').innerHTML = `<p>${descriptions[s.tab]}</p><div class="list-tools">${dated ? `<button class="button small" data-export-scope="${s.tab}">${icon('print')} Exporter un PDF</button>` : ''}${dated ? `<select id="list-scope" aria-label="Période de la liste"><option value="year" ${s.listScope === 'year' ? 'selected' : ''}>Année ${s.cursor.getFullYear()}</option><option value="future" ${s.listScope === 'future' ? 'selected' : ''}>Toutes les dates à venir</option><option value="all" ${s.listScope === 'all' ? 'selected' : ''}>Toutes les dates</option></select>` : ''}${s.tab !== 'alerts' ? `<input type="search" id="list-search" placeholder="Rechercher…" aria-label="Rechercher dans la liste" value="${esc(s.search)}">` : ''}</div>`;
    if (s.tab === 'alerts') { renderAlerts(); return; }
    const shoppingNav = s.tab === 'shopping' ? shoppingNavigation() : '';
    const records = listRecords(), type = s.tab === 'training' ? 'professional' : s.tab;
    if (s.tab === 'transport') { renderTransportList(records); return; }
    if (s.tab === 'note') {
      $('#view').innerHTML = records.length ? `<div class="list-content"><button class="button small" data-new="note">${icon('plus')} Nouvelle note</button></div><div class="notes-grid">${records.map(r => `<button class="note-card" data-edit="${r.id}"><strong>${esc(r.title)}</strong><p>${esc(r.notes || 'Cliquer pour compléter…')}</p><small>${ownerName(r.owner)}</small></button>`).join('')}</div>` : empty('Les idées ont leur place ici.','Gardez une adresse, un code de réservation ou une idée pour plus tard.','note');
      return;
    }
    if (s.tab === 'shopping' || s.tab === 'task') {
      $('#view').innerHTML = `${shoppingNav}<form class="quick-add" id="quick-add"><input name="title" required maxlength="200" placeholder="${s.tab === 'shopping' ? 'Ajouter un article à acheter…' : 'Ajouter une chose à faire…'}" aria-label="Nouvel élément"><button class="button primary" type="submit">${icon('plus')} Ajouter</button></form><div class="list-content">${records.map(r => `<div class="check-item ${r.done ? 'done' : ''}"><input type="checkbox" data-toggle="${r.id}" aria-label="${esc(r.title)} : terminé" ${r.done ? 'checked' : ''}><button class="list-main row-open" data-edit="${r.id}"><strong>${esc(r.title)} ${r.quantity ? `<span class="badge">${esc(r.quantity)}</span>` : ''}</strong><small>${r.due ? fmt(r.due,{year:'numeric'}) + ' · ' : ''}${ownerName(r.owner)}${r.notes ? ' · ' + esc(r.notes.slice(0,120)) : ''}</small></button><button class="icon-button" data-edit="${r.id}" aria-label="Modifier ${esc(r.title)}">${icon('right')}</button></div>`).join('') || '<div class="empty-state"><h3>Une chose de moins à garder en tête.</h3><p>Ajoutez votre premier élément juste au-dessus.</p></div>'}</div>`;
      return;
    }
    if (!records.length) {
      $('#view').innerHTML = s.tab === 'training' ? '<div class="empty-state"><div class="empty-icon">' + icon('work') + '</div><h3>Aucune date pour cette sélection</h3><p>Les dates enregistrées dans les sessions apparaîtront automatiquement ici.</p><a class="button" href="/sessions">Voir les sessions</a></div>' : empty('Votre planning prend forme.','Aucun élément pour cette sélection. Ajoutez une première date ou affichez toutes les dates.',type);
      return;
    }
    let month = '';
    $('#view').innerHTML = '<div class="list-content">' + (s.tab !== 'training' ? `<button class="button small" data-new="${type}">${icon('plus')} Ajouter ${s.tab === 'louise' ? 'une période' : 'un élément'}</button>` : '') + records.map(r => {
      const nextMonth = r.start.slice(0,7), heading = nextMonth !== month ? `<h3 class="list-group-label">${fmt(r.start,{day:undefined,month:'long',year:'numeric'})}</h3>` : ''; month = nextMonth;
      const details = [ownerName(r.owner),r.origin && r.destination ? `${r.origin} → ${r.destination}` : '',r.mode || '',r.reference || '',r.linked ? 'Lié au séjour · modifier le séjour' : '',r.series_id ? 'Période récurrente' : '',r.estimated_date ? 'Date de retour prévue à confirmer' : '',r.status ? statusLabel(r) : '',r.kind === 'boarding' ? BOARDING_PLACES[r.boarding_location] || 'Pension : lieu à préciser' : '',r.kind === 'restaurant' ? [mealLabel(r),r.start_time,r.guests ? r.guests + ' personnes' : '',r.address].filter(Boolean).join(' · ') : '',r.important ? 'Important' : ''].filter(Boolean).join(' · ');
      return heading + `<div class="list-row"><span class="list-color" style="--event-color:${color(r)}"></span><div class="list-date">${span(r.start,r.end)}</div><div class="list-main">${r.readonly ? `<a class="row-open" href="${esc(r.url)}"><strong>${esc(displayTitle(r))}</strong></a>` : `<button class="row-open" data-edit="${esc(r.record_id || r.id)}"><strong>${r.kind === 'location' ? placeLabel(r.place,r.title) : esc(r.title)}</strong></button>`}<small>${esc(details)}</small>${r.notes ? `<small class="notes-preview">${esc(r.notes)}</small>` : ''}</div>${r.readonly ? '<span class="badge automatic">Automatique</span>' : statusBadge(r)}<button class="icon-button" ${r.readonly ? `data-url="${esc(r.url)}"` : `data-edit="${esc(r.record_id || r.id)}"`} aria-label="Ouvrir ${esc(r.title)}">${icon('right')}</button></div>`;
    }).join('') + '</div>';
  }
  function renderAlerts() {
    const cov = s.data.coverage, missing = cov.missing.filter(r => owns(r)), alerts = s.data.alerts.filter(inYear);
    $('#view').innerHTML = `<div class="list-content"><div class="anomaly-intro"><strong>${cov.covered_days} / ${cov.total_days} jours entièrement renseignés</strong><p>Chaque jour doit avoir un lieu pour Clément et pour Elsa, y compris les jours passés. Aucun lieu n’est supposé automatiquement.</p><div class="coverage-bar"><span style="width:${cov.covered_days / cov.total_days * 100}%"></span></div><button class="button small" id="fill-year-inline" style="margin-top:14px">${icon('pin')} Compléter les jours sans lieu</button></div><h3 class="list-group-label">Lieux à compléter · ${missing.reduce((n,r) => n + r.count,0)} jours</h3>${missing.map(r => `<div class="list-row"><span class="list-color" style="--event-color:#d4928a"></span><div class="list-date">${span(r.start,r.end)}</div><div class="list-main"><strong>${ownerName(r.owner)}</strong><small>${r.count} jour${r.count > 1 ? 's' : ''} sans lieu</small></div><button class="button small" data-fill-start="${r.start}" data-fill-end="${r.end}" data-fill-owner="${r.owner}">Compléter</button></div>`).join('') || '<p class="side-empty">Tous les jours de cette année ont un lieu renseigné.</p>'}<h3 class="list-group-label">Réservations à vérifier · ${alerts.length}</h3>${alerts.map(r => `<div class="list-row"><span class="list-color" style="--event-color:#bd985f"></span><div class="list-date">${span(r.start,r.end)}</div><button class="list-main row-open" data-edit="${esc(r.record_id)}"><strong>${esc(r.title)}</strong><small>Ouvrir pour compléter le statut, les dates et les notes.</small></button>${icon('right')}</div>`).join('') || '<p class="side-empty">Aucune réservation en attente pour cette année.</p>'}</div>`;
  }
  function openDay(value) {
    s.selectedDay = value; const row = dayCoverage(value);
    $('#day-title').textContent = fmt(value,{weekday:'long',month:'long',year:'numeric'});
    const events = calendarEvents().filter(r => r.start <= value && r.end >= value).sort(dayOrder);
    $('#day-content').innerHTML = `<div class="day-quick-actions"><button class="button primary" data-day-new="personal">${icon('plus')} Rendez-vous</button><button class="button" data-day-new="personal" data-important="true">★ Important</button><button class="button" data-day-new="restaurant">${icon('restaurant')} Restaurant</button></div>` + '<div class="day-places">' + ['clement','elsa'].map(p => `<button class="day-place ${row[p] ? '' : 'missing'}" ${row[p] ? `data-edit="${row[p].id}"` : `data-fill-start="${value}" data-fill-end="${value}" data-fill-owner="${p}"`}><small>${ownerName(p)}</small><strong>${placeLabel(row[p]?.place,row[p]?.title || '＋ Renseigner le lieu')}</strong></button>`).join('') + '</div>' +
      events.map(r => `<button class="day-event" data-event="${esc(r.id)}"><span class="legend-dot" style="--event-color:${color(r)}"></span><span><strong>${esc(displayTitle(r))}</strong><small>${span(r.start,r.end,true)}${r.start_time ? ' · ' + esc(r.start_time) : ''}${r.end_time ? ' → ' + esc(r.end_time) : ''} · ${ownerName(r.owner)}${r.estimated_date ? '\nDate de retour prévue à confirmer' : ''}${r.kind === 'restaurant' ? '\n' + esc([r.address,r.guests ? r.guests + ' personnes' : ''].filter(Boolean).join(' · ')) : ''}${r.notes ? '\n' + esc(r.notes) : ''}</small></span>${r.status ? statusBadge(r) : r.readonly ? '<span class="badge automatic">Session ↗</span>' : ''}</button>`).join('') + (!events.length ? '<p class="side-empty">Aucun autre événement affiché pour cette journée.</p>' : '');
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
  const select = (name,label,options,value) => `<label class="field">${label}<select name="${name}">${options.map(([k,v]) => `<option value="${esc(k)}" ${k === value ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></label>`;
  const statuses = [['pending','À réserver'],['booked','Réservé'],['needs_change','À modifier'],['not_needed','Pas nécessaire']];
  function openEditor(kind='personal',id=null,defaults={}) {
    if (!s.data || s.moving) return;
    $('#day-dialog').close();
    s.editing = id ? s.data.records.find(r => r.id === id) : null;
    if (id && !s.editing) { toast('Cet élément n’est plus disponible. Actualisez le planning.'); return; }
    const r = s.editing || {kind:kind || 'personal',owner:s.owner === 'all' ? 'both' : s.owner,start:s.today,end:s.today,list_id:s.shoppingList,...defaults};
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
    else html += input('title',kind === 'louise' ? 'Intitulé (facultatif)' : kind === 'restaurant' ? 'Nom du restaurant' : 'Intitulé',r.title || (kind === 'louise' ? 'Avec Louise' : kind === 'boarding' ? 'Pension chien' : ''),'text',`maxlength="200" ${['louise','boarding','transport'].includes(kind) ? '' : 'required'}`);
    if (!item && kind !== 'restaurant') {
      html += `<div class="field-row">${input('start',kind === 'location' || kind === 'louise' ? 'Premier jour inclus' : 'Date de début',r.start,'date','required')}${input('end',kind === 'location' || kind === 'louise' ? 'Dernier jour inclus' : 'Date de fin',r.end || r.start,'date','required')}</div>`;
      if (!['location','louise','boarding'].includes(kind)) html += `<div class="field-row">${input('start_time','Heure de début (facultatif)',r.start_time || '','time')}${input('end_time','Heure de fin (facultatif)',r.end_time || '','time')}</div>`;
    }
    if (kind === 'restaurant') {
      html += `<div class="field-row">${input('start','Date de réservation',r.start,'date','required')}${select('meal','Quel repas ?',[['lunch','Midi'],['dinner','Soir'],['other','Autre moment']],r.meal || 'dinner')}</div><input type="hidden" name="end" value="${esc(r.start)}"><div class="field-row">${input('start_time','Heure de réservation',r.start_time || '','time','required')}${input('guests','Nombre de personnes',r.guests || 2,'number','min="1" max="100"')}</div>${input('address','Adresse / ville',r.address || '','text','maxlength="500"')}${select('status','Réservation',statuses,r.status || 'booked')}${input('reference','Référence / nom de la réservation',r.reference || '','text','maxlength="300"')}`;
    }
    if (['personal','professional','restaurant'].includes(kind)) html += `<label class="check-label important-check"><input type="checkbox" name="important" ${r.important ? 'checked' : ''}> ★ Événement important</label>`;
    if (kind === 'louise') {
      if (r.series_id && s.editing) html += '<p class="linked-note">Cette date appartient à une série. La modification concerne cette période uniquement. Vous pouvez supprimer toute la série avec le bouton Supprimer.</p>';
      if (!s.editing) html += `<div class="form-section"><h3>${icon('heart')} Gagner du temps sur les dates de garde</h3>${select('repeat','Répétition',[['none','Une seule période'],['weekly','Chaque semaine'],['fortnightly','Une semaine sur deux']],r.repeat || 'none')}<div id="repeat-dates">${input('repeat_until','Répéter jusqu’au (inclus)',r.repeat_until || `${s.cursor.getFullYear()}-12-31`,'date')}</div><p class="form-hint">La même période est répétée tous les 7 ou 14 jours. Chaque date reste modifiable individuellement.</p></div>`;
    }
    if (kind === 'location') {
      if (r.reservation_owner && r.reservation_owner !== r.owner) html += `<p class="linked-note">Les réservations conservées sur cette période concernent ${ownerName(r.reservation_owner)}.</p>`;
      if (!s.editing) html += `<label class="check-label"><input name="fill_gaps" type="checkbox" ${r.fill_gaps ? 'checked' : ''}> Remplir seulement les jours sans lieu <span class="sr-only">Les séjours existants sont conservés</span></label><p class="form-hint">Un lieu par jour et par personne. Les séjours existants sont conservés en mode remplissage.</p>`;
      html += '<label class="check-label"><input name="replace_conflicts" type="checkbox"> Remplacer le lieu habituel sur ces dates</label><p class="form-hint">Utile si votre année est déjà remplie. Les dates autour de ce séjour restent inchangées. Un séjour avec des réservations doit être modifié directement.</p>';
      for (const prefix of ['boarding','transport']) {
        const stat = r[prefix + '_status'] || (['paris','away'].includes(r.place) ? 'pending' : 'not_needed');
        html += `<section class="form-section"><h3>${icon(prefix === 'boarding' ? 'paw' : 'plane')} ${prefix === 'boarding' ? 'La pension du chien' : 'Les billets et trajets'}</h3>${select(prefix + '_status','Réservation',statuses,stat)}${prefix === 'boarding' ? select('boarding_location','Quelle pension ?',[['','Lieu à préciser'],['itana','Itana'],['lafeuillade','Lafeuillade']],r.boarding_location || '') : ''}<div id="${prefix}-dates">${prefix === 'transport' ? `<label class="check-label"><input name="transport_round_trip" type="checkbox" ${r.transport_round_trip !== false ? 'checked' : ''}> Prévoir un aller et un retour</label>` : ''}<div class="field-row">${input(prefix + '_start',prefix === 'boarding' ? 'Début de pension' : 'Date de l’aller',r[prefix + '_start'] || r.start,'date')}${input(prefix + '_end',prefix === 'boarding' ? 'Fin de pension' : 'Date du retour prévu',r[prefix + '_end'] || (prefix === 'boarding' || stat !== 'booked' || !s.editing ? r.end : ''),'date')}</div>${prefix === 'transport' ? `<div class="field-row">${select('transport_mode','Transport',[['Avion','Avion'],['Train','Train'],['Voiture','Voiture'],['Autre','Autre']],r.transport_mode || 'Avion')}${input('transport_origin','Ville de départ / de retour',r.transport_origin || '','text','maxlength="300" placeholder="Ex. Nice"')}</div>` : ''}<p class="form-hint">${prefix === 'boarding' ? 'Ces dates sont affichées avec le statut choisi : à réserver, réservé ou à modifier.' : 'L’aller et le retour restent visibles, même avant réservation. Ajoutez un trajet séparé si le retour se fait dans une autre ville.'}</p>${prefix === 'transport' ? '<p class="form-hint" id="transport-return-hint">Sans date de retour, la fin du séjour est affichée comme retour à confirmer ; elle ne vaut pas réservation.</p>' : ''}</div>${textarea(prefix + '_notes',prefix === 'boarding' ? 'Notes pension (contact, horaires, consignes…)' : 'Notes transport (référence, horaires, bagages…)',r[prefix + '_notes'] || '', 'maxlength="10000"')}</section>`;
      }
    }
    if (kind === 'boarding' || kind === 'transport') {
      html += select('status','Statut',statuses,r.status || 'pending');
      if (kind === 'boarding') html += select('boarding_location','Quelle pension ?',[['','Lieu à préciser'],['itana','Itana'],['lafeuillade','Lafeuillade']],r.boarding_location || '');
      if (kind === 'transport') html += `<div class="field-row">${input('origin','Départ',r.origin || '', 'text','required maxlength="300" placeholder="Ex. Paris Orly"')}${input('destination','Arrivée',r.destination || '', 'text','required maxlength="300" placeholder="Ex. Nice / Puget"')}</div>${select('mode','Moyen de transport',[['Avion','Avion'],['Train','Train'],['Voiture','Voiture'],['Autre','Autre']],r.mode || 'Avion')}`;
      html += input('reference','Référence de réservation (facultatif)',r.reference || '', 'text','maxlength="300"');
      html += '<p class="form-hint">Réservation indépendante. Pour mettre à jour une réservation déjà liée à un séjour, ouvrez le séjour dans Déplacements.</p>';
    }
    if (item && kind !== 'note') {
      if (kind === 'shopping') html += select('list_id','Liste de courses',shoppingLists().map(l => [l.id,l.name]),r.list_id || 'autre') + input('quantity','Quantité (facultatif)',r.quantity || '', 'text','maxlength="80" placeholder="Ex. 2 paquets"');
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
      const visible = status.value !== 'not_needed', area = $(`#${prefix}-dates`);
      area.hidden = !visible;
      $$('input,select',area).forEach(el => { el.disabled = !visible; el.required = visible && (el.name === prefix + '_start' || prefix === 'boarding' && el.name === 'boarding_end'); });
      if (prefix === 'transport') {
        const returning = form.elements.transport_round_trip?.checked !== false;
        const end = form.elements.transport_end;
        end.disabled = !visible || !returning;
        end.closest('.field').hidden = !returning;
        const hint = $('#transport-return-hint');
        if (hint) hint.hidden = !visible || !returning || !!end.value;
      }
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
    data.important = form.elements.important?.checked || false;
    data.fill_gaps = form.elements.fill_gaps?.checked || false;
    data.replace_conflicts = form.elements.replace_conflicts?.checked || false;
    if (form.elements.transport_round_trip) data.transport_round_trip = form.elements.transport_round_trip.checked;
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
      toast(result.count === 0 ? 'Tous ces jours ont déjà un lieu. Aucun séjour n’a été modifié.' : result.count > 1 ? (payload.kind === 'location' ? `${result.count} périodes complétées. Les réservations sont conservées une seule fois.` : `${result.count} périodes enregistrées.`) : 'Enregistré dans votre planning partagé.');
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
  function setFocus(active) {
    s.focus = active;
    document.body.classList.toggle('planner-focus',active);
    $('#fullscreen').setAttribute('aria-pressed',String(active));
    $('#fullscreen span').textContent = active ? 'Quitter le plein écran' : 'Plein écran';
    $('#add-calendar').hidden = !active;
  }
  async function toggleFullscreen() {
    if (s.focus) {
      setFocus(false);
      if (document.fullscreenElement && document.exitFullscreen) await document.exitFullscreen().catch(() => {});
      s.nativeFullscreen = false;
      return;
    }
    setFocus(true);
    // A full-window layout remains available when native fullscreen is denied
    // or unsupported, including iOS and embedded browsers.
    if (document.documentElement.requestFullscreen && document.fullscreenEnabled !== false) {
      try { await document.documentElement.requestFullscreen(); s.nativeFullscreen = true; }
      catch (_) { s.nativeFullscreen = false; }
    }
  }
  const EXPORT_SCOPES = [['all','Tout le planning'],['louise','Louise'],['location','Voyages et séjours'],['transport','Transports'],['boarding','Pension chien'],['restaurant','Restaurants'],['training','Formations'],['personal','Rendez-vous personnels'],['professional','Rendez-vous professionnels'],['task','À faire']];
  function exportPreset(preset) {
    const year = s.cursor.getFullYear(), month = s.cursor.getMonth();
    const first = preset === 'year' ? `${year}-01-01` : preset === 'rolling' ? s.today : iso(new Date(year,month,1));
    const end = preset === 'year' ? `${year}-12-31` : preset === 'rolling' ? add(iso(new Date(date(s.today).getFullYear()+1,date(s.today).getMonth(),date(s.today).getDate())), -1) : iso(new Date(year,month+1,0));
    $('#export-form').elements.start.value = first; $('#export-form').elements.end.value = end;
  }
  function openExport(scope) {
    if (!s.data) return;
    scope = scope || (EXPORT_SCOPES.some(([key]) => key === s.tab) ? s.tab : 'all');
    $('#export-fields').innerHTML = select('scope','Que souhaitez-vous imprimer ?',EXPORT_SCOPES,scope) + select('layout','Présentation',[['calendar','Calendrier mensuel + détail des événements'],['list','Liste chronologique compacte']], 'calendar') + `<div class="export-presets"><button type="button" class="button small" data-export-preset="month">Ce mois</button><button type="button" class="button small" data-export-preset="year">Année ${s.cursor.getFullYear()}</button><button type="button" class="button small" data-export-preset="rolling">Les 12 prochains mois</button></div><div class="field-row">${input('start','Du (inclus)','','date','required')}${input('end','Au (inclus)','','date','required')}</div>` + select('owner','Pour qui ?',[['all','Tout le monde'],['clement','Clément'],['elsa','Elsa']],s.owner);
    exportPreset(scope === 'all' ? 'month' : 'year'); errorAt('#export-error',''); $('#export-dialog').showModal();
  }
  async function downloadPdf(path,button,filename,errorTarget='#load-error') {
    if (!s.data || button.disabled) return false;
    button.disabled = true;
    const popup = window.open('about:blank','_blank');
    if (popup) { popup.opener = null; popup.document.title = 'Préparation du planning'; popup.document.body.textContent = 'Préparation de votre PDF…'; }
    try {
      const response = await fetch(`/gestion-clement-elsa${path}`,{credentials:'same-origin',cache:'no-store'});
      if (response.redirected || !response.headers.get('content-type')?.includes('application/pdf') || !response.ok) {
        const error = response.headers.get('content-type')?.includes('application/json') ? (await response.json()).error : 'Votre session a expiré. Rechargez la page avant de réessayer.';
        throw new Error(error || 'Impossible de préparer le PDF. Réessayez.');
      }
      const url = URL.createObjectURL(await response.blob());
      if (popup && !popup.closed) popup.location.replace(url);
      else {
        const link = document.createElement('a'); link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove();
      }
      setTimeout(() => URL.revokeObjectURL(url),120000);
      return true;
    } catch (e) { if (popup && !popup.closed) popup.close(); errorAt(errorTarget,e.message); toast(e.message); return false; }
    finally { button.disabled = false; }
  }
  function exportPdf() {
    const query = new URLSearchParams({year:String(s.cursor.getFullYear()),month:String(s.cursor.getMonth() + 1),owner:s.owner,hidden:[...s.hidden].join(',')});
    return downloadPdf(`/month.pdf?${query}`,$('#export-pdf'),`planning-clement-elsa-${s.cursor.getFullYear()}-${String(s.cursor.getMonth()+1).padStart(2,'0')}.pdf`);
  }
  document.addEventListener('dragstart',e => {
    const chip = e.target.closest('.calendar-day .event-chip');
    if (!chip) return;
    if (chip.draggable !== true || s.loading || s.moving) { e.preventDefault(); return; }
    const event = calendarEvents().find(r => r.id === chip.dataset.event);
    const record = s.data.records.find(r => r.id === (event?.record_id || event?.id));
    if (!record || event.readonly) { e.preventDefault(); return; }
    s.drag = {event:{...event},record:{...record},day:chip.closest('.calendar-day').dataset.day};
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain',event.id);
    chip.classList.add('drag-source');
    document.body.classList.add('calendar-dragging');
  });
  document.addEventListener('dragover',e => {
    if (!s.drag || s.moving) return;
    const day = e.target.closest('.calendar-day'), nav = e.target.closest('#prev,#next');
    $$('.drop-target').forEach(el => { if (el !== day) el.classList.remove('drop-target'); });
    if (day || nav) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }
    if (day) day.classList.toggle('drop-target',day.dataset.day !== s.drag.day);
    if (nav !== s.dragNav) {
      clearTimeout(s.dragNavTimer);
      $$('.drag-nav-target').forEach(el => el.classList.remove('drag-nav-target'));
      s.dragNav = nav;
      if (nav) {
        nav.classList.add('drag-nav-target');
        s.dragNavTimer = setTimeout(() => { if (s.drag) navigate(nav.id === 'prev' ? -1 : 1); },700);
      }
    }
  });
  document.addEventListener('dragleave',e => {
    const day = e.target.closest('.calendar-day');
    if (day && !day.contains(e.relatedTarget)) day.classList.remove('drop-target');
    if (s.dragNav && !s.dragNav.contains(e.relatedTarget)) {
      clearTimeout(s.dragNavTimer); s.dragNav.classList.remove('drag-nav-target'); s.dragNav = null;
    }
  });
  document.addEventListener('drop',e => {
    if (!s.drag) return;
    e.preventDefault();
    const day = e.target.closest('.calendar-day'), drag = s.drag;
    s.ignoreClickUntil = Date.now() + 400;
    clearDrag();
    if (day && !s.loading) moveEvent(drag,day.dataset.day);
  });
  document.addEventListener('dragend',() => {
    if (s.drag) s.ignoreClickUntil = Date.now() + 400;
    clearDrag();
  });
  document.addEventListener('keydown',e => { if (e.key === 'Escape' && s.drag) clearDrag(); });
  document.addEventListener('click',e => {
    if (Date.now() < (s.ignoreClickUntil || 0)) { e.preventDefault(); e.stopImmediatePropagation(); }
  },true);
  document.addEventListener('click', async e => {
    const target = e.target.closest('button,a,[data-day]'); if (!target) return;
    if (target.dataset.close) { $('#' + target.dataset.close).close(); return; }
    if (!s.data) return;
    if (target.dataset.tab) { setTab(target.dataset.tab); return; }
    if (target.dataset.new) { openEditor(target.dataset.new,null,target.dataset.place ? {place:target.dataset.place} : {}); return; }
    if (target.dataset.addDate) { openEditor('personal',null,{start:target.dataset.addDate,end:target.dataset.addDate}); return; }
    if (target.dataset.dayNew) { openEditor(target.dataset.dayNew,null,{start:s.selectedDay,end:s.selectedDay,important:target.dataset.important === 'true'}); return; }
    if (target.dataset.shoppingList) { s.shoppingList = target.dataset.shoppingList; renderList(); return; }
    if (target.id === 'new-shopping-list' || target.id === 'rename-shopping-list') { openShoppingList(target.id === 'rename-shopping-list'); return; }
    if (target.dataset.exportScope) { openExport(target.dataset.exportScope); return; }
    if (target.dataset.exportPreset) { exportPreset(target.dataset.exportPreset); return; }
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
      if (el.name === 'kind' && !s.editing) { const previous = formValue(); renderForm({kind:el.value,owner:previous.owner,start:previous.start || s.today,end:previous.end || s.today,title:previous.title || '',notes:previous.notes || '',important:previous.important,list_id:previous.list_id || s.shoppingList}); }
      if (el.name === 'place') {
        const form = $('#event-form');
        if (!s.editing) for (const prefix of ['boarding','transport']) if (form.elements[prefix + '_status'].value !== 'booked') form.elements[prefix + '_status'].value = ['paris','away'].includes(el.value) ? 'pending' : 'not_needed';
      }
      if (el.name === 'start') {
        const form = $('#event-form'); if (form.elements.kind.value === 'restaurant' || form.elements.end.value < el.value) form.elements.end.value = el.value;
      }
      if (/^(boarding|transport)_(start|end)$/.test(el.name)) el.dataset.manual = 'true';
      if (!s.editing && ['start','end','boarding_status','transport_status'].includes(el.name)) {
        const form = $('#event-form');
        for (const prefix of ['boarding','transport']) {
          const first = form.elements[prefix + '_start'], last = form.elements[prefix + '_end'];
          if (first && !first.dataset.manual) first.value = form.elements.start.value;
          if (last && !last.dataset.manual) last.value = form.elements.end.value;
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
    try { await api('/records',{method:'POST',body:JSON.stringify({kind:s.tab,title:form.elements.title.value,owner:s.owner === 'all' ? 'both' : s.owner,list_id:s.shoppingList})}); await load(); $('#quick-add input')?.focus(); }
    catch (e) { btn.disabled = false; errorAt('#load-error',e.message); }
  });
  $('#shopping-list-form').addEventListener('submit',async e => {
    e.preventDefault(); const button = $('#save-shopping-list'); if (button.disabled) return; button.disabled = true;
    try {
      const result = await api(s.editingList ? `/shopping-lists/${s.editingList.id}` : '/shopping-lists',{method:s.editingList ? 'PUT' : 'POST',body:JSON.stringify({name:$('#shopping-list-name').value,revision:s.editingList?.revision})});
      s.shoppingList = result.id; $('#shopping-list-dialog').close(); await load();
    } catch (e) { errorAt('#shopping-list-error',e.message); } finally { button.disabled = false; }
  });
  $('#export-form').addEventListener('submit',async e => {
    e.preventDefault(); errorAt('#export-error',''); const values = Object.fromEntries(new FormData(e.target));
    const ok = await downloadPdf(`/export.pdf?${new URLSearchParams(values)}`,$('#generate-export'),`planning-${values.scope}-${values.start}-${values.end}.pdf`,'#export-error');
    if (ok) $('#export-dialog').close();
  });
  $('#open-export').addEventListener('click',() => openExport());
  $('#event-form').addEventListener('submit',save);
  $('#fullscreen').addEventListener('click',toggleFullscreen);
  $('#export-pdf').addEventListener('click',exportPdf);
  $('#add-calendar').addEventListener('click',() => openEditor('personal'));
  document.addEventListener('fullscreenchange',() => { if (s.nativeFullscreen && !document.fullscreenElement) { s.nativeFullscreen = false; setFocus(false); } });
  document.addEventListener('keydown',e => { if (e.key === 'Escape' && s.focus && !$$('dialog[open]').length) toggleFullscreen(); });
  $('#refresh').addEventListener('click',load);
  $('#add-main').addEventListener('click',() => openEditor(['calendar','training','alerts','dashboard'].includes(s.tab) ? 'personal' : s.tab));
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
  document.addEventListener('visibilitychange',() => { if (!document.hidden && !s.loading && !s.drag && !s.moving && !$$('dialog[open]').length && Date.now() - s.lastLoaded > 60000) load(); });
  load();
})();
