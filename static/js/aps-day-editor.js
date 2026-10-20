const dayDialog = document.getElementById('dayDialog');
const dayForm = document.getElementById('dayForm');
const dayFields = document.getElementById('dayFields');
let daySaving = false;
const daySelectedUvs = new Set();
const dayFillMode = () => document.querySelector('[name="dayFillMode"]:checked').value;

function renderDayModuleChoices() {
  const groups = APSDayPlanner.modules(planning, curriculum.contents, {modality: document.getElementById('dayModality').value}).filter(item => item.remainingMinutes > 0);
  for (const uv of daySelectedUvs) if (!groups.some(item => item.uv === uv)) daySelectedUvs.delete(uv);
  document.getElementById('dayCourseChoices').innerHTML = groups.length ? groups.map(item =>
    `<label class="module-choice"><input type="checkbox" data-day-module value="${esc(item.uv)}" ${daySelectedUvs.has(item.uv) ? 'checked' : ''}><span><strong>${esc(item.label)}</strong><small>${hours(item.remainingMinutes)} restant à planifier</small></span></label>`).join('')
    : '<p class="muted">Tous les modules sont déjà planifiés pour cette modalité.</p>';
}

function dayOptions() {
  return {examDate: planningSession.date_exam, lunchStart: planningSession.apsLunchStart, lunchEnd: planningSession.apsLunchEnd};
}

function readDayFields() {
  return {
    date: document.getElementById('dayDate').value,
    modality: document.getElementById('dayModality').value,
    room: planningSession.salle || planningSession.room || '',
    morning: document.getElementById('dayMorning').checked ? {start: document.getElementById('dayMorningStart').value, end: document.getElementById('dayMorningEnd').value} : null,
    afternoon: document.getElementById('dayAfternoon').checked ? {start: document.getElementById('dayAfternoonStart').value, end: document.getElementById('dayAfternoonEnd').value} : null,
  };
}

function prepareDay() {
  const fields = readDayFields();
  const draft = APSDayPlanner.createDay(planning, fields, dayOptions());
  const mode = dayFillMode();
  if (mode === 'manual' && !daySelectedUvs.size) throw new Error('Cochez au moins un module, ou choisissez « Journée vide ».');
  if (mode !== 'empty') return APSDayPlanner.fill(draft, curriculum.contents, {...dayOptions(), date: fields.date,
    ...(mode === 'manual' ? {selectedUvs: [...daySelectedUvs]} : {})});
  return {planning: draft, addedMinutes: 0};
}

function updateDayPreview() {
  for (const [toggle, start, end] of [['dayMorning', 'dayMorningStart', 'dayMorningEnd'], ['dayAfternoon', 'dayAfternoonStart', 'dayAfternoonEnd']]) {
    const enabled = document.getElementById(toggle).checked;
    for (const id of [start, end]) { document.getElementById(id).disabled = !enabled; document.getElementById(id).required = enabled; }
  }
  const mode = dayFillMode();
  document.getElementById('dayCourseSelection').hidden = mode !== 'manual';
  document.getElementById('createDay').textContent = mode === 'auto' ? 'Ajouter et remplir la journée' : mode === 'manual' ? 'Ajouter les cours cochés' : 'Ajouter la journée vide';
  const preview = document.getElementById('dayPreview');
  try {
    const result = prepareDay();
    const day = result.planning.find(item => item.date === document.getElementById('dayDate').value);
    const total = day.slots.reduce((value, slot) => value + slotMinutes(slot), 0);
    preview.textContent = mode !== 'empty'
      ? `${hours(result.addedMinutes)} de cours seront planifiées sur ${hours(total)} disponibles.${result.addedMinutes < total ? ' Le temps restant sera conservé en créneaux libres.' : ''}`
      : `${hours(total)} de créneaux disponibles. Vous pourrez les remplir automatiquement ensuite.`;
    if (mode === 'manual') {
      const chosenMinutes = APSDayPlanner.modules(planning, curriculum.contents, {modality: document.getElementById('dayModality').value})
        .filter(item => daySelectedUvs.has(item.uv)).reduce((n, item) => n + item.remainingMinutes, 0);
      if (chosenMinutes > result.addedMinutes) preview.textContent += ` ${hours(chosenMinutes - result.addedMinutes)} de votre sélection resteront à planifier.`;
    }
    const added = new Map();
    for (const slot of day.slots.filter(slot => !slot.isEmpty)) added.set(slot.uv, (added.get(slot.uv) || 0) + slotMinutes(slot));
    if (added.size) {
      const list = document.createElement('ul');
      for (const [uv, value] of added) { const row = document.createElement('li'); row.textContent = `${APSDayPlanner.moduleLabel(uv)} : ${hours(value)}`; list.appendChild(row); }
      preview.appendChild(list);
    }
    if (total > dailyCapacityMinutes) preview.textContent += ` Durée indicative habituelle : ${hours(dailyCapacityMinutes)} par jour.`;
  } catch (error) { preview.textContent = error.message; }
}

function suggestDayDate() {
  const start = String(planningSession.date_debut || planning[0]?.date || '').slice(0, 10);
  const end = String(planningSession.date_fin || planning.at(-1)?.date || start).slice(0, 10);
  const cursor = new Date(`${start}T12:00:00Z`);
  for (let index = 0; index < 370 && !Number.isNaN(cursor.getTime()); index++, cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const value = cursor.toISOString().slice(0, 10);
    if (value > end) break;
    if (![0, 6].includes(cursor.getUTCDay()) && value !== String(planningSession.date_exam || '').slice(0, 10) && !planning.some(day => day.date === value)) return value;
  }
  return '';
}

function suggestDayModality() {
  const date = document.getElementById('dayDate').value;
  const remaining = APSDayPlanner.remainingCourses(planning, curriculum.contents);
  const hasDistance = remaining.some(item => item.modality === 'elearning' && item.remainingMinutes > 0);
  const firstOnSite = planning.filter(day => day.slots.some(slot => !slot.isEmpty && slot.modality !== 'elearning')).map(day => day.date).sort()[0];
  document.getElementById('dayModality').value = hasDistance && (!firstOnSite || (date && date < firstOnSite)) ? 'elearning' : 'presentiel';
}

function openDayDialog() {
  if (planningChangePending || daySaving || !curriculum) return;
  dayForm.reset();
  daySelectedUvs.clear();
  document.getElementById('dayDate').value = suggestDayDate();
  const [lunchStart, lunchEnd] = slotLunchBreak();
  document.getElementById('dayMorningEnd').value = slotTime(lunchStart);
  document.getElementById('dayAfternoonStart').value = slotTime(lunchEnd);
  document.getElementById('dayModalityField').hidden = !curriculum.contents.some(item => item.modality === 'elearning');
  suggestDayModality();
  renderDayModuleChoices();
  document.getElementById('dayDialogError').style.display = 'none';
  updateDayPreview();
  dayDialog.showModal();
  document.getElementById('dayDate').focus();
}

function updateDayTools() {
  document.querySelectorAll('[data-day-action]').forEach(button => { button.disabled = planningChangePending || !curriculum; });
  const fillButton = document.getElementById('fillRemainingCourses');
  if (fillButton) fillButton.disabled = planningChangePending || !curriculum || !planning.some(day => day.slots.some(slot => slot.isEmpty)) || !APSDayPlanner.remainingCourses(planning, curriculum.contents).some(item => item.remainingMinutes > 0);
}

function allocationMessage(result) {
  return `${hours(result.addedMinutes)} de cours ajoutées et enregistrées.${result.remainingMinutes ? ` Il reste ${hours(result.remainingMinutes)} à planifier.` : ' Tous les cours sont planifiés.'}${result.unusedMinutes ? ` ${hours(result.unusedMinutes)} restent libres dans les créneaux sélectionnés.` : ''}`;
}

async function fillRemainingCourses(date = '') {
  if (planningChangePending || !curriculum) return;
  try {
    const result = APSDayPlanner.fill(planning, curriculum.contents, {...dayOptions(), date});
    if (!result.addedMinutes) {
      show(err, 'Aucun cours ne peut être ajouté dans ces créneaux. Vérifiez les heures restantes et la modalité des créneaux ; le distanciel doit précéder le présentiel.');
      return;
    }
    await savePlanningChange(() => { planning = result.planning; }, allocationMessage(result));
    if (date) scrollToDay(date);
  } catch (error) { show(err, error.message); }
}

dayForm.addEventListener('input', event => {
  document.getElementById('dayDialogError').style.display = 'none';
  if (event.target.matches('[data-day-module]')) {
    if (event.target.checked) daySelectedUvs.add(event.target.value); else daySelectedUvs.delete(event.target.value);
  }
  if (event.target.id === 'dayModality') renderDayModuleChoices();
  updateDayPreview();
});
document.getElementById('dayDate').addEventListener('change', () => { suggestDayModality(); renderDayModuleChoices(); updateDayPreview(); });
document.getElementById('cancelDay').addEventListener('click', () => dayDialog.close());
dayDialog.addEventListener('cancel', event => { if (daySaving) event.preventDefault(); });
dayForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (daySaving || planningChangePending) return;
  let result;
  try { result = prepareDay(); }
  catch (error) { show(document.getElementById('dayDialogError'), error.message); return; }
  if (dayFillMode() === 'manual' && !result.addedMinutes) {
    show(document.getElementById('dayDialogError'), 'Les modules cochés ne peuvent pas être placés à cette date. Vérifiez la modalité et l’ordre des journées à distance et en présentiel.'); return;
  }
  const date = document.getElementById('dayDate').value;
  daySaving = true;
  dayFields.disabled = true;
  document.getElementById('createDay').textContent = 'Enregistrement…';
  try {
    const message = result.addedMinutes ? allocationMessage(result) : 'Journée ajoutée et enregistrée. Les créneaux sont disponibles pour les cours restants.';
    const saved = await savePlanningChange(() => { planning = result.planning; }, message);
    if (saved) { dayDialog.close(); scrollToDay(date); }
  } finally { daySaving = false; dayFields.disabled = false; updateDayPreview(); }
});

function openModuleInsert(di, si) {
  const day = planning[di], slot = day.slots[si], available = insertableMinutes(day, slot);
  selectedSlot = {di, si};
  modalErr.style.display = 'none';
  const groups = APSDayPlanner.modules(planning, curriculum.contents, {modality: slot.modality || 'presentiel'}).filter(item => item.remainingMinutes > 0);
  document.getElementById('modalHint').textContent = `Créneau : ${slot.start}–${slot.end}. Choisissez le module à ajouter, jusqu’à ${hours(available)}.`;
  document.getElementById('courseChoices').innerHTML = groups.length ? groups.map(item => `<button type="button" class="course-choice" data-action="insert-module" data-uv="${esc(item.uv)}" ${available <= 0 ? 'disabled' : ''}><span><strong>${esc(item.label)}</strong><br><small>${hours(item.remainingMinutes)} restantes</small></span><strong>${hours(Math.min(available, item.remainingMinutes))}</strong></button>`).join('') : '<p>Aucun module restant pour cette modalité.</p>';
  document.getElementById('courseModal').classList.add('open');
}

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-action="insert-module"]');
  if (!button || planningChangePending || !selectedSlot) return;
  const {di, si} = selectedSlot, day = planning[di], slot = day?.slots[si];
  if (!slot?.isEmpty) return;
  try {
    const result = APSDayPlanner.fill(planning, curriculum.contents, {...dayOptions(), date: day.date,
      slotIndex: si, selectedUvs: [button.dataset.uv], maxMinutes: insertableMinutes(day, slot)});
    if (!result.addedMinutes) { showActionError('Ce module ne peut pas être ajouté dans ce créneau. Vérifiez la modalité et l’ordre des journées.'); return; }
    document.querySelectorAll('[data-action="insert-module"]').forEach(item => item.disabled = true);
    if (await savePlanningChange(() => { planning = result.planning; }, allocationMessage(result))) closeModal();
  } catch (error) { showActionError(error.message); }
  finally { document.querySelectorAll('[data-action="insert-module"]').forEach(item => item.disabled = false); }
});
