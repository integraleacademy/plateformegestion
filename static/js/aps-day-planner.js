/* Day creation and course allocation. All durations come from the current timetable. */
const APSDayPlanner = (() => {
  const copy = value => JSON.parse(JSON.stringify(value));
  const toMinutes = value => {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(value || '')) return NaN;
    const [hour, minute] = value.split(':').map(Number);
    return hour * 60 + minute;
  };
  const toTime = value => `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
  const duration = slot => toMinutes(slot.end) - toMinutes(slot.start);
  const scheduled = slot => !slot.isEmpty;
  const timedSlot = (slot, start, end) => ({...slot, start: toTime(start), end: toTime(end), durationMinutes: end - start, duration: (end - start) / 60});
  const lunch = options => [toMinutes(options.lunchStart || '12:30'), toMinutes(options.lunchEnd || '13:30')];

  function remainingCourses(planning, contents) {
    const courses = contents.map(item => ({...item, remainingMinutes: Number(item.expectedMinutes)}));
    for (const day of planning) {
      for (const slot of (day.slots || []).filter(scheduled)) {
        const course = courses.find(item => slot.pedagogicalKey ? item.key === slot.pedagogicalKey
          : item.key === slot.uv || (item.uv === slot.uv && item.title === slot.title && item.modality === (slot.modality || 'presentiel')));
        if (course) course.remainingMinutes -= Math.max(0, duration(slot) || 0);
      }
    }
    return courses;
  }

  function createDay(planning, fields, options = {}) {
    const parsed = new Date(`${fields.date}T12:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(fields.date || '') || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== fields.date) {
      throw new Error('Choisissez une date valide.');
    }
    if (fields.date === String(options.examDate || '').slice(0, 10)) throw new Error('Cette date est réservée à l’examen. Choisissez une autre journée.');
    if (planning.some(day => day.date === fields.date)) throw new Error('Cette journée existe déjà. Utilisez « Planifier les cours restants » ou « Ajouter un créneau » sur cette journée.');
    const [lunchStart, lunchEnd] = lunch(options);
    const slots = [];
    for (const [period, label] of [['morning', 'matin'], ['afternoon', 'après-midi']]) {
      if (!fields[period]) continue;
      const {start, end} = fields[period];
      const from = toMinutes(start), to = toMinutes(end);
      if (!Number.isFinite(from) || !Number.isFinite(to) || to <= from) throw new Error(`Vérifiez les horaires du ${label} : la fin doit être après le début.`);
      if ((period === 'morning' && to > lunchStart) || (period === 'afternoon' && from < lunchEnd)) {
        throw new Error(`Respectez la pause déjeuner de ${toTime(lunchStart)} à ${toTime(lunchEnd)}.`);
      }
      slots.push(timedSlot({isEmpty: true, modality: fields.modality || 'presentiel', room: fields.room || '', trainer: fields.trainer || ''}, from, to));
    }
    if (!slots.length) throw new Error('Ajoutez au moins une demi-journée.');
    return [...copy(planning), {date: fields.date, dayLabel: new Intl.DateTimeFormat('fr-FR', {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'}).format(parsed), slots}]
      .sort((a, b) => a.date.localeCompare(b.date));
  }

  function freeIntervals(start, end, occupied) {
    let intervals = [[start, end]];
    for (const [busyStart, busyEnd] of occupied) {
      intervals = intervals.flatMap(([from, to]) => {
        if (busyEnd <= from || busyStart >= to) return [[from, to]];
        return [[from, Math.min(to, busyStart)], [Math.max(from, busyEnd), to]].filter(([a, b]) => b > a);
      });
    }
    return intervals;
  }

  function fill(planning, contents, options = {}) {
    const result = copy(planning);
    const courses = remainingCourses(result, contents);
    const addedKeys = new Set();
    let addedMinutes = 0, unusedMinutes = 0;
    const mixed = contents.some(item => item.modality === 'elearning');
    for (const day of [...result].sort((a, b) => a.date.localeCompare(b.date))) {
      if (options.date && day.date !== options.date) continue;
      if (day.date === String(options.examDate || '').slice(0, 10)) continue;
      const occupied = (day.slots || []).filter(scheduled).map(slot => [toMinutes(slot.start), toMinutes(slot.end)]);
      occupied.push(lunch(options));
      const slots = (day.slots || []).filter(scheduled);
      for (const slot of (day.slots || []).filter(slot => slot.isEmpty).sort((a, b) => toMinutes(a.start) - toMinutes(b.start))) {
        const start = toMinutes(slot.start), end = toMinutes(slot.end);
        if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) throw new Error(`Vérifiez les horaires du créneau disponible le ${day.date}.`);
        const modality = slot.modality || 'presentiel';
        const conflictsWithPeriod = mixed && (slots.some(other => scheduled(other) && (other.modality || 'presentiel') !== modality) || result.some(otherDay => (otherDay.slots || []).some(other => scheduled(other) &&
          (modality === 'elearning' ? other.modality !== 'elearning' && otherDay.date <= day.date
            : other.modality === 'elearning' && otherDay.date >= day.date))));
        for (const [from, to] of freeIntervals(start, end, occupied)) {
          let cursor = from;
          if (!conflictsWithPeriod) {
            for (const course of courses) {
              if (cursor >= to) break;
              if (course.modality !== modality || course.remainingMinutes <= 0) continue;
              const minutes = Math.min(to - cursor, course.remainingMinutes);
              slots.push(timedSlot({...slot, isEmpty: false, uv: course.uv, title: course.title, part: course.part,
                modality, pedagogicalKey: course.key, deliveryType: course.deliveryType,
                practiceMinutes: course.deliveryType === 'practice' ? minutes : 0, programVersion: course.programVersion}, cursor, cursor + minutes));
              course.remainingMinutes -= minutes;
              addedMinutes += minutes;
              addedKeys.add(course.key);
              cursor += minutes;
            }
          }
          if (cursor < to) {
            slots.push(timedSlot(slot, cursor, to));
            unusedMinutes += to - cursor;
          }
          occupied.push([from, to]);
        }
      }
      day.slots = slots.sort((a, b) => toMinutes(a.start) - toMinutes(b.start));
    }
    return {planning: result, addedMinutes, addedCourses: addedKeys.size, unusedMinutes,
      remainingMinutes: courses.reduce((total, item) => total + Math.max(0, item.remainingMinutes), 0)};
  }

  return {createDay, fill, remainingCourses};
})();
if (typeof module !== 'undefined') module.exports = APSDayPlanner;
