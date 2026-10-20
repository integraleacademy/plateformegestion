const {test} = require('node:test');
const assert = require('node:assert/strict');
const blocks = require('../static/js/aps-editor-blocks.js');
const planner = require('../static/js/aps-day-planner.js');
const slot = (start, end, key, deliveryType = 'theory', extra = {}) => ({start, end, uv: 'UV3',
  pedagogicalKey: key, title: key, modality: 'presentiel', part: 'Présentiel', room: 'Salle 1', trainer: 'Rachid',
  deliveryType, programVersion: 'V3.2', ...extra});
const afternoon = () => [slot('13:30', '15:30', 'theory'), slot('15:30', '16:30', 'practice', 'practice'),
  slot('16:30', '17:30', 'practice', 'practice')];
const contents = [{key: 'theory', uv: 'UV3', title: 'theory', modality: 'presentiel', part: 'Présentiel', expectedMinutes: 120, deliveryType: 'theory'},
  {key: 'practice', uv: 'UV3', title: 'practice', modality: 'presentiel', part: 'Présentiel', expectedMinutes: 180, deliveryType: 'practice'}];
const plan = slots => [{date: '2026-11-18', slots}];

test('the screenshot afternoon becomes exactly one 4h UV3 block without changing stored courses', () => {
  const slots = [slot('10:30', '12:30', 'morning'), ...afternoon()];
  const before = JSON.stringify(slots);
  const rows = blocks.rows(slots);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows.map(row => [row.start, row.end, row.slotIndices]),
    [['10:30', '12:30', [0]], ['13:30', '17:30', [1, 2, 3]]]);
  assert.equal(rows[1].durationMinutes, 240);
  assert.equal(JSON.stringify(slots), before);
});

test('breaks, another UV, empty availability, instructor, room, modality and phase changes separate blocks', () => {
  const first = slot('13:30', '14:30', 'first');
  for (const change of [{start: '14:45'}, {uv: 'UV2'}, {isEmpty: true}, {trainer: 'Autre'},
    {room: 'Salle 2'}, {modality: 'elearning'}, {part: 'Autre période'}]) {
    assert.equal(blocks.rows([first, slot('14:30', '15:30', 'second', 'practice', change)]).length, 2);
  }
  assert.equal(blocks.rows([first, slot('14:30', '15:30', 'second', 'practice')]).length, 1);
  assert.equal(blocks.rows([{...first, uv: 'EXAM'}, slot('14:30', '15:30', 'exam', 'theory', {uv: 'EXAM'})]).length, 2);
});

test('deleting a displayed block releases every underlying course and preserves the other half-day', () => {
  const slots = [slot('10:30', '12:30', 'morning'), ...afternoon()];
  const cleared = blocks.clear(slots, blocks.rows(slots)[1]);
  assert.equal(cleared.length, 2);
  assert.deepEqual(cleared[0], slots[0]);
  assert.equal(cleared[1].isEmpty, true);
  assert.equal(cleared[1].pedagogicalKey, undefined);
  assert.deepEqual([cleared[1].start, cleared[1].end, cleared[1].durationMinutes], ['13:30', '17:30', 240]);
  assert.equal(planner.remainingCourses(plan(cleared), contents)[0].remainingMinutes, 120);
  assert.equal(slots.length, 4);
});

test('shortening a block across internal boundaries retains canonical identities and exact practice minutes', () => {
  const input = plan(afternoon());
  const shorter = blocks.resize(input, 0, blocks.rows(input[0].slots)[0], 'end', '16:00', contents);
  assert.deepEqual(shorter[0].slots.map(s => [s.pedagogicalKey, s.start, s.end, s.practiceMinutes]),
    [['theory', '13:30', '15:30', 0], ['practice', '15:30', '16:00', 30]]);
  const restored = blocks.resize(shorter, 0, blocks.rows(shorter[0].slots)[0], 'end', '17:30', contents);
  assert.equal(blocks.rows(restored[0].slots)[0].durationMinutes, 240);
  assert.deepEqual(planner.remainingCourses(restored, contents).map(c => c.remainingMinutes), [0, 60]);
  assert.equal(input[0].slots.length, 3);
});

test('editing the start trims all affected sequences and can restore the missing hours', () => {
  const input = plan(afternoon());
  const shorter = blocks.resize(input, 0, blocks.rows(input[0].slots)[0], 'start', '16:00', contents);
  assert.deepEqual(shorter[0].slots.map(s => [s.start, s.end, s.practiceMinutes]),
    [['16:00', '16:30', 30], ['16:30', '17:30', 60]]);
  const restored = blocks.resize(shorter, 0, blocks.rows(shorter[0].slots)[0], 'start', '13:30', contents);
  assert.equal(blocks.rows(restored[0].slots)[0].durationMinutes, 240);
  assert.ok(restored[0].slots.every(s => s.durationMinutes > 0));
});

test('extensions allocate remaining same-UV content and consume overlapping empty availability', () => {
  const input = plan([...afternoon(), {start: '17:30', end: '19:00', isEmpty: true, modality: 'presentiel'}]);
  const extended = blocks.resize(input, 0, blocks.rows(input[0].slots)[0], 'end', '18:30', contents);
  assert.equal(blocks.rows(extended[0].slots)[0].end, '18:30');
  assert.equal(extended[0].slots.at(-1).isEmpty, true);
  assert.equal(extended[0].slots.at(-1).start, '18:30');
  assert.deepEqual(planner.remainingCourses(extended, contents).map(c => c.remainingMinutes), [0, 0]);
});

test('invalid hours, lunch, overlaps and extensions beyond remaining hours leave the original plan untouched', () => {
  const input = plan(afternoon()), before = JSON.stringify(input), row = blocks.rows(input[0].slots)[0];
  for (const [key, value, message] of [['end', '', /horaires/], ['end', '13:00', /horaires/],
    ['start', '12:00', /pause déjeuner/], ['end', '19:00', /assez d’heures/]]) {
    assert.throws(() => blocks.resize(input, 0, row, key, value, contents), message);
    assert.equal(JSON.stringify(input), before);
  }
  const occupied = plan([...afternoon(), slot('17:30', '18:30', 'other', 'theory', {uv: 'UV4'})]);
  assert.throws(() => blocks.resize(occupied, 0, row, 'end', '18:00', contents), /chevauchent/);
});

test('legacy on-site plans without canonical keys or phase metadata can still be extended as one block', () => {
  const input = plan([{uv: 'UV2', title: 'Ancien intitulé', start: '13:30', end: '15:30', modality: 'presentiel'}]);
  const courses = [{key: 'UV2', uv: 'UV2', title: 'Juridique', expectedMinutes: 240, modality: 'presentiel', part: 'Programme APS'}];
  const extended = blocks.resize(input, 0, blocks.rows(input[0].slots)[0], 'end', '17:30', courses);
  assert.equal(blocks.rows(extended[0].slots).length, 1);
  assert.equal(blocks.rows(extended[0].slots)[0].durationMinutes, 240);
  assert.equal(planner.remainingCourses(extended, courses)[0].remainingMinutes, 0);
});

test('empty slot editing and a session-specific lunch break remain supported', () => {
  const input = plan([{start: '14:00', end: '17:00', isEmpty: true, modality: 'presentiel'}]);
  const options = {lunchStart: '13:00', lunchEnd: '14:00'};
  const changed = blocks.resize(input, 0, blocks.rows(input[0].slots)[0], 'end', '18:00', [], options);
  assert.deepEqual([changed[0].slots[0].isEmpty, changed[0].slots[0].durationMinutes], [true, 240]);
  assert.throws(() => blocks.resize(input, 0, blocks.rows(input[0].slots)[0], 'start', '13:30', [], options), /pause déjeuner/);
});
