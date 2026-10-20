/* Editable module blocks. Canonical course sequences remain separate in storage. */
const APSEditorBlocks = (() => {
  const planner = typeof module !== 'undefined' ? require('./aps-day-planner.js') : APSDayPlanner;
  const copy = value => JSON.parse(JSON.stringify(value));
  const minutes = value => /^([01]\d|2[0-3]):[0-5]\d$/.test(value || '')
    ? Number(value.slice(0, 2)) * 60 + Number(value.slice(3)) : NaN;
  const time = value => `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
  const duration = slot => minutes(slot.end) - minutes(slot.start);
  const timed = (slot, start, end) => ({...slot, start: time(start), end: time(end),
    durationMinutes: end - start, duration: (end - start) / 60,
    ...(slot.isEmpty ? {} : {practiceMinutes: slot.deliveryType === 'practice' ? end - start
      : Math.round((slot.practiceMinutes || 0) * (end - start) / duration(slot))})});
  const value = (slot, key) => slot[key] || (key === 'modality' ? 'presentiel' : '');

  function rows(slots) {
    const result = [];
    slots.forEach((slot, index) => {
      const previous = result.at(-1);
      const sameModule = !slot.isEmpty && !previous?.isEmpty && /^UV(?:[1-9]|1[0-4])$/.test(slot.uv || '')
        && previous && ['uv', 'modality', 'room', 'trainer', 'part'].every(key => value(previous, key) === value(slot, key));
      if (sameModule && previous.end === slot.start && duration(slot) > 0 && duration(previous) > 0) {
        previous.end = slot.end;
        previous.durationMinutes = duration(previous);
        previous.duration = previous.durationMinutes / 60;
        previous.slotIndices.push(index);
      } else result.push({...copy(slot), slotIndices: [index]});
    });
    return result;
  }

  function clear(slots, block) {
    const selected = new Set(block.slotIndices);
    const empty = {start: block.start, end: block.end, durationMinutes: duration(block), duration: duration(block) / 60,
      modality: block.modality || 'presentiel', room: block.room || '', trainer: block.trainer || '', isEmpty: true};
    return slots.flatMap((slot, index) => index === block.slotIndices[0] ? [empty] : selected.has(index) ? [] : [copy(slot)]);
  }

  function resize(planning, dayIndex, block, key, newValue, contents, options = {}) {
    const start = minutes(key === 'start' ? newValue : block.start);
    const end = minutes(key === 'end' ? newValue : block.end);
    if (!['start', 'end'].includes(key) || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      throw new Error('Vérifiez les horaires : la fin doit être après le début.');
    }
    const lunchStart = minutes(options.lunchStart || '12:30'), lunchEnd = minutes(options.lunchEnd || '13:30');
    if (start < lunchEnd && end > lunchStart) throw new Error(`Respectez la pause déjeuner de ${time(lunchStart)} à ${time(lunchEnd)}.`);
    const selected = new Set(block.slotIndices);
    const original = planning[dayIndex].slots;
    if (original.some((slot, index) => !selected.has(index) && !slot.isEmpty && start < minutes(slot.end) && end > minutes(slot.start))) {
      throw new Error('Ces horaires chevauchent un autre cours déjà planifié sur cette journée.');
    }
    const result = copy(planning);
    const replacement = block.isEmpty ? [timed(original[block.slotIndices[0]], start, end)]
      : block.slotIndices.flatMap(index => {
        const slot = original[index], from = Math.max(start, minutes(slot.start)), to = Math.min(end, minutes(slot.end));
        return to > from ? [timed(slot, from, to)] : [];
      });
    // Retain untouched sequences and allocate only genuinely unplanned minutes when extending.
    result[dayIndex].slots = original.filter((slot, index) => !selected.has(index)).concat(replacement);
    if (!block.isEmpty) {
      const remaining = planner.remainingCourses(result, contents).filter(course => course.uv === block.uv
        && value(course, 'modality') === value(block, 'modality')
        && (course.key === block.uv || !block.part || value(course, 'part') === value(block, 'part')));
      const extensions = [[start, Math.min(end, minutes(block.start)), original[block.slotIndices[0]]],
        [Math.max(start, minutes(block.end)), end, original[block.slotIndices.at(-1)]]];
      for (const [from, to, edge] of extensions) {
        let cursor = from;
        const preferredKey = edge.pedagogicalKey || edge.uv;
        const ordered = from < minutes(block.start) ? remaining
          : [...remaining].sort((a, b) => Number(b.key === preferredKey) - Number(a.key === preferredKey));
        for (const course of ordered) {
          if (cursor >= to) break;
          const added = Math.min(to - cursor, Math.max(0, course.remainingMinutes));
          if (!added) continue;
          replacement.push({...edge, start: time(cursor), end: time(cursor + added), durationMinutes: added, duration: added / 60,
            title: course.title, pedagogicalKey: course.key, part: edge.part, modality: course.modality,
            deliveryType: course.deliveryType, programVersion: course.programVersion,
            practiceMinutes: course.deliveryType === 'practice' ? added : 0});
          course.remainingMinutes -= added;
          cursor += added;
        }
        if (cursor < to) throw new Error('Il ne reste pas assez d’heures de ce module à planifier pour prolonger ce cours.');
      }
    }
    // An extended block consumes any empty availability it covers.
    result[dayIndex].slots = original.flatMap((slot, index) => {
      if (selected.has(index)) return [];
      if (!slot.isEmpty || minutes(slot.end) <= start || minutes(slot.start) >= end) return [copy(slot)];
      return [[minutes(slot.start), Math.min(start, minutes(slot.end))], [Math.max(end, minutes(slot.start)), minutes(slot.end)]]
        .filter(([from, to]) => to > from).map(([from, to]) => timed(slot, from, to));
    }).concat(replacement).sort((a, b) => minutes(a.start) - minutes(b.start));
    return result;
  }

  return {rows, clear, resize};
})();
if (typeof module !== 'undefined') module.exports = APSEditorBlocks;
