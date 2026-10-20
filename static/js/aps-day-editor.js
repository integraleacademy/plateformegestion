const dayDialog = document.getElementById('dayDialog');
const dayForm = document.getElementById('dayForm');
const dayFields = document.getElementById('dayFields');
let daySaving = false;

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
  if (document.getElementById('dayAutoFill').checked) return APSDayPlanner.fill(draft, curriculum.contents, {...dayOptions(), date: fields.date});
  return {planning: draft, addedMinutes: 0};
}

function updateDayPreview() {
  for (const [toggle, start, end] of [['dayMorning', 'dayMorningStart', 'dayMorningEnd'], ['dayAfternoon', 'dayAfternoonStart', 'dayAfternoonEnd']]) {
    const enabled = document.getElementById(toggle).checked;
    for (const id of [start, end]) { document.getElementById(id).disabled = !enabled; document.getElementById(id).required = enabled; }
  }
  const auto = document.getElementById('dayAutoFill').checked;
  document.getElementById('createDay').textContent = auto ? 'Ajouter et remplir la journée' : 'Ajouter la journée';
  const preview = document.getElementById('dayPreview');
  try {
    const result = prepareDay();
    const day = result.planning.find(item => item.date === document.getElementById('dayDate').value);
    const total = day.slots.reduce((value, slot) => value + slotMinutes(slot), 0);
    preview.textContent = auto
      ? `${hours(result.addedMinutes)} de cours seront planifiées sur ${hours(total)} disponibles.${result.addedMinutes < total ? ' Le temps restant sera conservé en créneaux libres.' : ''}`
      : `${hours(total)} de créneaux disponibles. Vous pourrez les remplir automatiquement ensuite.`;
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
  document.getElementById('dayDate').value = suggestDayDate();
  const [lunchStart, lunchEnd] = slotLunchBreak();
  document.getElementById('dayMorningEnd').value = slotTime(lunchStart);
  document.getElementById('dayAfternoonStart').value = slotTime(lunchEnd);
  document.getElementById('dayModalityField').hidden = !curriculum.contents.some(item => item.modality === 'elearning');
  suggestDayModality();
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

dayForm.addEventListener('input', updateDayPreview);
document.getElementById('dayDate').addEventListener('change', () => { suggestDayModality(); updateDayPreview(); });
document.getElementById('cancelDay').addEventListener('click', () => dayDialog.close());
dayDialog.addEventListener('cancel', event => { if (daySaving) event.preventDefault(); });
dayForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (daySaving || planningChangePending) return;
  let result;
  try { result = prepareDay(); }
  catch (error) { show(document.getElementById('dayDialogError'), error.message); return; }
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
