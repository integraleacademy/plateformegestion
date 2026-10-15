const slotDialog = document.getElementById('slotDialog');
const slotForm = document.getElementById('slotForm');
const slotFields = document.getElementById('slotFields');
const slotDate = document.getElementById('slotDate');
const slotStart = document.getElementById('slotStart');
const slotEnd = document.getElementById('slotEnd');
const slotModality = document.getElementById('slotModality');
let slotSaving = false;

function slotTime(value) {
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
}

function slotLunchBreak() {
  return [minutes(planningSession.apsLunchStart || '12:30'), minutes(planningSession.apsLunchEnd || '13:30')];
}

function suggestSlotTimes(day) {
  const remaining = Math.max(60, availability(day || {slots: []}).available);
  const [lunchStart, lunchEnd] = slotLunchBreak();
  const occupied = (day?.slots || []).map(slot => [minutes(slot.start), minutes(slot.end)])
    .filter(([start, end]) => Number.isFinite(start) && end > start).sort((a, b) => a[0] - b[0]);
  const gaps = [];
  const afternoonEnd = Math.min(1439, Math.max(990, lunchEnd + Math.min(remaining, 240)));
  for (const [windowStart, windowEnd] of [[510, lunchStart], [lunchEnd, afternoonEnd]]) {
    let cursor = windowStart;
    for (const [start, end] of occupied) {
      if (end <= cursor || start >= windowEnd) continue;
      if (start > cursor) gaps.push([cursor, Math.min(start, windowEnd)]);
      cursor = Math.max(cursor, end);
    }
    if (cursor < windowEnd) gaps.push([cursor, windowEnd]);
  }
  gaps.sort((a, b) => (b[1] - b[0]) - (a[1] - a[0]));
  const gap = gaps[0];
  return gap ? [slotTime(gap[0]), slotTime(Math.min(gap[1], gap[0] + remaining))] : ['', ''];
}

function updateSlotDuration() {
  const duration = minutes(slotEnd.value) - minutes(slotStart.value);
  document.getElementById('slotDuration').textContent = Number.isFinite(duration) && duration > 0
    ? `Durée du créneau : ${hours(duration)}` : 'Renseignez les horaires du créneau.';
}

function presetSlotDate() {
  const day = planning.find(item => item.date === slotDate.value);
  [slotStart.value, slotEnd.value] = suggestSlotTimes(day);
  slotModality.value = day?.slots?.find(slot => !slot.isEmpty)?.modality
    || day?.slots?.[0]?.modality || 'presentiel';
  updateSlotDuration();
}

function openSlotDialog(date = '') {
  if (planningChangePending || slotSaving) return;
  slotForm.reset();
  slotDate.value = date;
  document.getElementById('slotDialogError').style.display = 'none';
  presetSlotDate();
  slotDialog.showModal();
  (date ? slotStart : slotDate).focus();
}

slotDate.addEventListener('change', presetSlotDate);
slotStart.addEventListener('input', updateSlotDuration);
slotEnd.addEventListener('input', updateSlotDuration);
document.getElementById('cancelSlot').addEventListener('click', () => slotDialog.close());
slotDialog.addEventListener('cancel', event => { if (slotSaving) event.preventDefault(); });

slotForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (slotSaving || planningChangePending) return;
  const date = slotDate.value, start = slotStart.value, end = slotEnd.value;
  const startMinutes = minutes(start), endMinutes = minutes(end);
  const parsedDate = new Date(`${date}T12:00:00Z`);
  const fail = message => show(document.getElementById('slotDialogError'), message);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(parsedDate.getTime()) || parsedDate.toISOString().slice(0, 10) !== date) {
    fail('Choisissez une date valide.'); return;
  }
  if (date === String(planningSession.date_exam || '').slice(0, 10)) {
    fail('Cette date est réservée à l’examen. Choisissez une autre journée.'); return;
  }
  if (!Number.isFinite(startMinutes) || !Number.isFinite(endMinutes) || endMinutes <= startMinutes) {
    fail('L’heure de fin doit être après l’heure de début.'); return;
  }
  const [lunchStart, lunchEnd] = slotLunchBreak();
  if (startMinutes < lunchEnd && endMinutes > lunchStart) {
    fail(`Ce créneau traverse la pause déjeuner (${slotTime(lunchStart)}–${slotTime(lunchEnd)}). Ajoutez un créneau le matin et un autre l’après-midi.`); return;
  }
  const day = planning.find(item => item.date === date);
  if ((day?.slots || []).some(slot => startMinutes < minutes(slot.end) && endMinutes > minutes(slot.start))) {
    fail('Ces horaires chevauchent un créneau existant. Choisissez d’autres horaires ou utilisez « Insérer un cours » sur un créneau disponible.'); return;
  }
  const defaults = day?.slots?.find(slot => !slot.isEmpty) || day?.slots?.[0] || {};
  const newSlot = {
    start, end, durationMinutes: endMinutes - startMinutes, duration: (endMinutes - startMinutes) / 60,
    modality: slotModality.value, room: defaults.room || planningSession.salle || planningSession.room || '',
    trainer: defaults.trainer || '', isEmpty: true,
  };
  slotSaving = true;
  slotFields.disabled = true;
  const submitButton = document.getElementById('createSlot');
  submitButton.textContent = 'Ajout en cours…';
  try {
    const saved = await savePlanningChange(() => {
      let destination = planning.find(item => item.date === date);
      if (!destination) {
        destination = {date, dayLabel: new Intl.DateTimeFormat('fr-FR', {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'}).format(parsedDate), slots: []};
        planning.push(destination);
      }
      destination.slots.push(newSlot);
      destination.slots.sort((a, b) => minutes(a.start) - minutes(b.start));
      planning.sort((a, b) => a.date.localeCompare(b.date));
    }, 'Créneau ajouté et enregistré. Choisissez maintenant le cours.');
    if (!saved) return;
    slotDialog.close();
    const dayIndex = planning.findIndex(item => item.date === date);
    const slotIndex = planning[dayIndex]?.slots.findIndex(slot => slot.isEmpty && slot.start === start && slot.end === end);
    scrollToDay(date);
    if (dayIndex >= 0 && slotIndex >= 0) openInsert(dayIndex, slotIndex);
  } finally {
    slotSaving = false;
    slotFields.disabled = false;
    submitButton.textContent = 'Ajouter et choisir le cours';
  }
});
