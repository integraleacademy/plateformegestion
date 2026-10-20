const {test} = require('node:test');
const assert = require('node:assert/strict');
const planner = require('../static/js/aps-day-planner.js');
const course = (key, minutes, modality = 'presentiel', extra = {}) => ({key, uv: key, title: key, expectedMinutes: minutes, modality, ...extra});
const empty = (start = '08:30', end = '12:30', modality = 'presentiel') => ({start, end, isEmpty: true, modality, room: 'Salle 1', trainer: ''});
const day = (date, slots) => ({date, slots});
const fields = {date: '2026-11-02', morning: {start: '08:30', end: '12:30'}, afternoon: {start: '13:30', end: '16:30'}};

test('a full day is created without changing the input and rejects duplicate / exam dates', () => {
  const original = [];
  const result = planner.createDay(original, fields);
  assert.deepEqual(original, []);
  assert.deepEqual(result[0].slots.map(slot => slot.durationMinutes), [240, 180]);
  assert.throws(() => planner.createDay(result, fields), /existe déjà/);
  assert.throws(() => planner.createDay([], fields, {examDate: fields.date}), /examen/);
  assert.throws(() => planner.createDay([], {...fields, date: '2026-02-30'}), /date valide/);
  assert.throws(() => planner.createDay([], {...fields, morning: {start: '10:00', end: '09:00'}}), /horaires/);
  assert.throws(() => planner.createDay([], {...fields, afternoon: {start: '12:00', end: '16:30'}}), /pause déjeuner/);
});

test('supports a half day and a configured lunch break', () => {
  const plan = planner.createDay([], {...fields, morning: null, afternoon: {start: '14:00', end: '17:00'}}, {lunchStart: '13:00', lunchEnd: '14:00'});
  assert.equal(plan[0].slots.length, 1);
  assert.equal(plan[0].slots[0].durationMinutes, 180);
});

test('splits courses at lunch, finishes a partial course and fills the next course', () => {
  const existing = {...empty('08:30', '09:30'), isEmpty: false, uv: 'UV1', title: 'UV1', pedagogicalKey: 'UV1', durationMinutes: 999};
  const original = [day('2026-10-30', [existing])];
  const draft = planner.createDay(original, fields);
  const result = planner.fill(draft, [course('UV1', 360), course('UV2', 180)]);
  assert.equal(result.addedMinutes, 420);
  assert.equal(result.remainingMinutes, 60);
  assert.deepEqual(result.planning[0].slots[0], existing);
  assert.deepEqual(draft[1].slots.map(slot => slot.isEmpty), [true, true]);
  assert.deepEqual(result.planning[1].slots.map(slot => [slot.uv, slot.start, slot.end]), [
    ['UV1', '08:30', '12:30'], ['UV1', '13:30', '14:30'], ['UV2', '14:30', '16:30'],
  ]);
  const again = planner.fill(result.planning, [course('UV1', 360), course('UV2', 180)]);
  assert.equal(again.addedMinutes, 0);
  assert.deepEqual(again.planning, JSON.parse(JSON.stringify(result.planning)));
});

test('recomputes remaining time from unsaved edits and leaves excess capacity empty', () => {
  const existing = {...empty('08:30', '10:00'), isEmpty: false, uv: 'UV1', title: 'UV1', durationMinutes: 30};
  const result = planner.fill([day('2026-11-02', [existing, empty('10:00', '12:30')])], [course('UV1', 120)]);
  assert.equal(result.addedMinutes, 30);
  assert.equal(result.remainingMinutes, 0);
  assert.equal(result.unusedMinutes, 120);
  assert.equal(result.planning[0].slots[2].start, '10:30');
  assert.equal(result.planning[0].slots[2].isEmpty, true);
});

test('fills only the selected date and preserves previously scheduled courses and their teachers', () => {
  const planned = {...empty(), isEmpty: false, uv: 'UV1', title: 'UV1', trainer: 'Formateur désigné'};
  const input = [day('2026-11-03', [empty()]), day('2026-11-02', [planned, empty('13:30', '16:30')])];
  const result = planner.fill(input, [course('UV1', 600)], {date: '2026-11-02'});
  assert.deepEqual(result.planning[0], input[0]);
  assert.deepEqual(result.planning[1].slots[0], planned);
  assert.equal(result.addedMinutes, 180);
});

test('keeps distance and on-site courses separate, respects order and practice metadata', () => {
  const contents = [course('D', 60, 'elearning'), course('P', 120, 'presentiel', {deliveryType: 'practice'})];
  const result = planner.fill([day('2026-11-02', [empty('08:30', '09:30', 'elearning'), empty('13:30', '16:30')]), day('2026-11-03', [empty()])], contents);
  assert.equal(result.addedMinutes, 180);
  assert.equal(result.planning[0].slots[1].isEmpty, true);
  assert.equal(result.planning[1].slots[0].practiceMinutes, 120);
  const backwards = planner.fill([day('2026-11-03', [{...empty(), isEmpty: false, uv: 'P', title: 'P'}]), day('2026-11-04', [empty('08:30', '09:30', 'elearning')])], contents);
  assert.equal(backwards.addedMinutes, 0);
});

test('never inserts over existing courses, the lunch break or overlapping placeholders', () => {
  const planned = {...empty('10:00', '11:00'), isEmpty: false, uv: 'UV1', title: 'UV1'};
  const result = planner.fill([day('2026-11-02', [planned, empty('08:30', '16:30'), empty('09:00', '12:00')])], [course('UV1', 420)]);
  assert.equal(result.addedMinutes, 360);
  assert.deepEqual(result.planning[0].slots.map(slot => [slot.start, slot.end]), [['08:30', '10:00'], ['10:00', '11:00'], ['11:00', '12:30'], ['13:30', '16:30']]);
});

test('does not fill exam dates and rejects invalid availability without mutating data', () => {
  const input = [day('2026-11-02', [empty()])];
  assert.equal(planner.fill(input, [course('UV1', 420)], {examDate: '2026-11-02'}).addedMinutes, 0);
  const invalid = [day('2026-11-02', [empty('08:30', '')])];
  const before = JSON.stringify(invalid);
  assert.throws(() => planner.fill(invalid, [course('UV1', 420)]), /horaires/);
  assert.equal(JSON.stringify(invalid), before);
});

test('groups sequences and modalities into a single correctly labelled UV', () => {
  const contents = [course('distance', 120, 'elearning', {uv: 'UV2'}), course('theory', 60, 'presentiel', {uv: 'UV2'}),
    course('practice', 60, 'presentiel', {uv: 'UV2', deliveryType: 'practice'}), course('UV10', 420), course('UV1', 840)];
  const plan = [day('2026-11-02', [{...empty('08:30', '09:00', 'elearning'), isEmpty: false, pedagogicalKey: 'distance'}])];
  const groups = planner.modules(plan, contents);
  assert.deepEqual(groups.map(item => item.uv), ['UV1', 'UV2', 'UV10']);
  assert.equal(groups[0].label, 'UV 1 - Module Secourisme');
  assert.equal(groups[1].plannedMinutes, 30);
  assert.equal(groups[1].remainingMinutes, 210);
  assert.deepEqual(groups[1].remainingByModality, {elearning: 90, presentiel: 120});
  assert.equal(planner.modules(plan, contents, {modality: 'presentiel'}).find(item => item.uv === 'UV2').remainingMinutes, 120);
});

test('manual selection allocates only checked UVs across their canonical sequences', () => {
  const contents = [course('UV1', 840), course('UV2-theory', 120, 'presentiel', {uv: 'UV2'}),
    course('UV2-practice', 60, 'presentiel', {uv: 'UV2', deliveryType: 'practice'}), course('UV3', 60)];
  const plan = planner.createDay([], fields);
  const result = planner.fill(plan, contents, {selectedUvs: ['UV2', 'UV3']});
  const scheduled = result.planning[0].slots.filter(slot => !slot.isEmpty);
  assert.deepEqual(scheduled.map(slot => slot.uv), ['UV2', 'UV2', 'UV3']);
  assert.deepEqual(scheduled.map(slot => slot.pedagogicalKey), ['UV2-theory', 'UV2-practice', 'UV3']);
  assert.equal(scheduled[1].practiceMinutes, 60);
  assert.equal(result.addedMinutes, 240);
  assert.equal(result.remainingMinutes, 840);
  assert.equal(planner.fill(plan, contents, {selectedUvs: []}).addedMinutes, 0);
});

test('inserting a grouped module into a single slot preserves other free slots and the duration limit', () => {
  const contents = [course('UV4-theory', 60, 'presentiel', {uv: 'UV4'}), course('UV4-practice', 120, 'presentiel', {uv: 'UV4', deliveryType: 'practice'})];
  const plan = planner.createDay([], fields);
  const result = planner.fill(plan, contents, {date: fields.date, slotIndex: 1, selectedUvs: ['UV4'], maxMinutes: 90});
  assert.deepEqual(result.planning[0].slots[0], plan[0].slots[0]);
  assert.equal(result.addedMinutes, 90);
  assert.deepEqual(result.planning[0].slots.slice(1).map(slot => [slot.start, slot.end, slot.isEmpty]),
    [['13:30', '14:30', false], ['14:30', '15:00', false], ['15:00', '16:30', true]]);
});
