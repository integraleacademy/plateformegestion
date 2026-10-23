(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.A3pBuilderUtils = api;
})(typeof window === 'undefined' ? globalThis : window, function () {
  'use strict';

  function isoDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }

  function isValidDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return false;
    const year = Number(value.slice(0, 4));
    const date = new Date(value + 'T12:00:00');
    return year >= 1900 && year <= 2199 && !Number.isNaN(date.getTime()) && isoDate(date) === value;
  }

  function parseDate(value) {
    const text = String(value || '').trim();
    if (isValidDate(text)) return text;
    const match = text.match(/^(\d{2})[/.\-](\d{2})[/.\-](\d{4})$/) || text.match(/^(\d{2})(\d{2})(\d{4})$/);
    const iso = match ? `${match[3]}-${match[2]}-${match[1]}` : '';
    return isValidDate(iso) ? iso : '';
  }

  function displayDate(value) {
    return isValidDate(value) ? value.split('-').reverse().join('/') : '';
  }

  function duration(minutes) {
    const value = Math.max(0, Math.round(Number(minutes) || 0));
    const hours = Math.floor(value / 60), remainder = value % 60;
    return `${hours} h${remainder ? ' ' + String(remainder).padStart(2, '0') : ''}`;
  }

  function sortDays(days) {
    return [...days].sort((a, b) => (isValidDate(a.date) ? a.date : '9999').localeCompare(isValidDate(b.date) ? b.date : '9999'));
  }

  function isTrainingDay(day, examDate, isExcludedDate) {
    return isValidDate(day.date) && day.training !== false && day.date !== examDate
      && (day.allowNonWorkingDay === true || !isExcludedDate(day.date));
  }

  function dayPlan(day, placements = []) {
    const minute = value => {
      if (!/^\d{2}:\d{2}$/.test(value || '')) return NaN;
      const [h, m] = value.split(':').map(Number);
      return h < 24 && m < 60 ? h * 60 + m : NaN;
    };
    const time = value => `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
    const busy = placements.map(p => [minute(p.start), minute(p.end)])
      .filter(([s, e]) => Number.isFinite(s) && Number.isFinite(e) && e > s).sort((a, b) => a[0] - b[0]);
    const lockedMinutes = busy.reduce((total, [s, e]) => total + e - s, 0);
    const result = {slots: [], freeSlots: [], pauseStart: '', pauseEnd: '', lockedMinutes, totalMinutes: 0};
    const start = minute(day.dayStart), end = minute(day.dayEnd);
    if (day.training === false || !Number.isFinite(start) || !Number.isFinite(end) || end - start < 120) return result;
    const training = Math.min(480, end - start - 60), windowEnd = start + training + 60;
    const preferredPause = start + Math.floor(training / 2);
    const subtract = interval => busy.reduce((free, [bs, be]) => free.flatMap(([s, e]) => {
      if (be <= s || bs >= e) return [[s, e]];
      return [[s, Math.min(bs, e)], [Math.max(be, s), e]].filter(([a, b]) => b > a);
    }), [interval]);
    const candidates = subtract([start, windowEnd]).filter(([s, e]) => e - s >= 60)
      .map(([s, e]) => Math.max(s, Math.min(preferredPause, e - 60)))
      .sort((a, b) => Math.abs(a - preferredPause) - Math.abs(b - preferredPause) || a - b);
    if (!candidates.length) {
      result.totalMinutes = Math.min(480, lockedMinutes);
      return result;
    }
    const pause = candidates[0];
    result.pauseStart = time(pause); result.pauseEnd = time(pause + 60);
    const slots = [[start, pause], [pause + 60, windowEnd]].filter(([s, e]) => e > s);
    const asSlot = ([s, e]) => ({start: time(s), end: time(e), durationMinutes: e - s});
    result.slots = slots.map(asSlot);
    let capacity = Math.max(0, 480 - lockedMinutes);
    for (const [s, e] of slots.flatMap(subtract)) {
      const take = Math.min(capacity, e - s);
      if (take > 0) result.freeSlots.push(asSlot([s, s + take]));
      capacity -= take;
    }
    result.totalMinutes = Math.min(480, lockedMinutes + result.freeSlots.reduce((sum, slot) => sum + slot.durationMinutes, 0));
    return result;
  }

  // Date capacity and module allocation are two different measures. Count each
  // eligible date once, even when an old draft contains duplicate dates.
  function summarize({days, examDate, isExcludedDate, dayMinutes, allocatedMinutes, targetMinutes = 328 * 60}) {
    const dates = new Set();
    let scheduledMinutes = 0;
    for (const day of days) {
      if (dates.has(day.date) || !isTrainingDay(day, examDate, isExcludedDate)) continue;
      const minutes = Math.max(0, Number(dayMinutes(day)) || 0);
      if (!minutes) continue;
      dates.add(day.date);
      scheduledMinutes += minutes;
    }
    return {
      dayCount: dates.size,
      scheduledMinutes,
      allocatedMinutes,
      missingMinutes: Math.max(0, targetMinutes - scheduledMinutes),
      surplusMinutes: Math.max(0, scheduledMinutes - targetMinutes),
      unallocatedMinutes: Math.max(0, targetMinutes - allocatedMinutes),
      freeMinutes: Math.max(0, scheduledMinutes - allocatedMinutes),
    };
  }

  // Keep the ISO input for FormData and the native calendar, but let the user
  // finish typing a French date before committing it or rebuilding any rows.
  function bindDateInput(input, {onCommit = () => {}, validate = () => '', label = 'Date'} = {}) {
    if (!input || input.a3pDateField) return input?.a3pDateField;
    const wrapper = document.createElement('div');
    wrapper.className = 'a3p-date-field';
    input.replaceWith(wrapper);
    const text = document.createElement('input');
    text.type = 'text';
    text.className = 'a3p-date-text';
    text.placeholder = 'jj/mm/aaaa';
    text.autocomplete = 'off';
    text.setAttribute('aria-label', label + ' (jj/mm/aaaa)');
    text.disabled = input.disabled;
    text.value = displayDate(input.value);
    input.classList.add('a3p-date-native');
    input.tabIndex = -1;
    input.setAttribute('aria-label', label + ' — calendrier');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'a3p-date-button';
    button.setAttribute('aria-label', 'Choisir ' + label.toLowerCase() + ' dans le calendrier');
    button.disabled = input.disabled;
    button.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18"/></svg>';
    wrapper.append(text, input, button);
    let committed = input.value;

    function commit(value) {
      const iso = parseDate(value);
      const error = !iso ? 'Saisissez une date complète au format jj/mm/aaaa.' : validate(iso);
      text.setCustomValidity(error || '');
      text.setAttribute('aria-invalid', error ? 'true' : 'false');
      text.title = error || '';
      if (error) { input.value = committed; return false; }
      text.value = displayDate(iso);
      input.value = iso;
      if (iso !== committed) { committed = iso; onCommit(iso); }
      return true;
    }
    text.addEventListener('input', event => {
      event.stopPropagation();
      text.setCustomValidity('');
      text.removeAttribute('aria-invalid');
    });
    text.addEventListener('change', event => event.stopPropagation());
    text.addEventListener('blur', () => commit(text.value));
    text.addEventListener('keydown', event => {
      if (event.key === 'Enter') { event.preventDefault(); if (commit(text.value)) text.blur(); }
      if (event.key === 'Escape') { text.value = displayDate(committed); text.setCustomValidity(''); text.removeAttribute('aria-invalid'); event.stopPropagation(); }
    });
    input.addEventListener('input', event => event.stopPropagation());
    input.addEventListener('change', event => { event.stopPropagation(); commit(input.value); });
    button.addEventListener('click', () => {
      if (typeof input.showPicker === 'function') input.showPicker();
      else { input.focus(); input.click(); }
    });
    input.a3pDateField = {
      sync() { committed = input.value; text.value = displayDate(input.value); text.setCustomValidity(''); text.removeAttribute('aria-invalid'); },
      commit() { return commit(text.value); },
    };
    return input.a3pDateField;
  }

  return {isoDate, isValidDate, parseDate, displayDate, duration, sortDays, isTrainingDay, dayPlan, summarize, bindDateInput};
});
