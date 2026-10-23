const test = require('node:test');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {parseDate, isValidDate, summarize, duration} = require('../static/js/a3p-builder-utils.js');

test('date entry accepts a complete French year and rejects partial or impossible dates', () => {
  for (const value of ['10/11/2026', '10112026', '10.11.2026', '2026-11-10']) assert.equal(parseDate(value), '2026-11-10');
  for (const value of ['10/11/2', '10/11/202', '0002-11-10', '31/11/2026', '29/02/2026', '10/13/2026']) assert.equal(parseDate(value), '');
  assert.equal(parseDate('29/02/2028'), '2028-02-29');
  assert.equal(isValidDate('2026-02-30'), false);
});

test('local calendar dates do not shift backwards in the French time zone', () => {
  const script = "const {isoDate}=require('./static/js/a3p-builder-utils.js'); process.stdout.write(['2026-11-10','2026-04-06','2026-05-14'].map(d=>isoDate(new Date(d+'T00:00:00'))).join(','))";
  assert.equal(execFileSync(process.execPath, ['-e', script], {cwd:require('node:path').resolve(__dirname,'..'),env:{...process.env,TZ:'Europe/Paris'}}).toString(), '2026-11-10,2026-04-06,2026-05-14');
});

function stats(days, allocatedMinutes = 86*60) {
  return summarize({days,examDate:'2027-01-15',isExcludedDate:d=>d==='2026-11-11'||[0,6].includes(new Date(d+'T12:00:00').getDay()),dayMinutes:d=>d.minutes,allocatedMinutes});
}

test('the 242 hours are module allocation, not a shortage of scheduled hours', () => {
  const days=[];
  const current=new Date('2026-07-01T12:00:00');
  while(days.length<43){
    if(![0,6].includes(current.getDay())) days.push({date:current.toISOString().slice(0,10),minutes:480});
    current.setDate(current.getDate()+1);
  }
  days[42].minutes=90;
  const summary=stats(days);
  assert.equal(summary.dayCount,43);
  assert.equal(summary.scheduledMinutes,337.5*60);
  assert.equal(summary.missingMinutes,0);
  assert.equal(summary.surplusMinutes,9.5*60);
  assert.equal(summary.unallocatedMinutes,242*60);
  assert.equal(summary.freeMinutes,251.5*60);
  assert.equal(duration(summary.scheduledMinutes),'337 h 30');
});

test('days counter excludes exams, holidays, weekends, invalid dates and duplicates', () => {
  const days=[
    {date:'2026-11-10',minutes:480}, {date:'2026-11-10',minutes:480},
    {date:'2026-11-11',minutes:480}, {date:'2026-11-14',minutes:480},
    {date:'2027-01-15',minutes:480}, {date:'2026-11-12',minutes:480,training:false},
    {date:'2026-11-13',minutes:0}, {date:'0002-11-10',minutes:480},
  ];
  const summary=stats(days,0);
  assert.equal(summary.dayCount,1);
  assert.equal(summary.scheduledMinutes,480);
  assert.equal(summary.missingMinutes,320*60);
  assert.equal(summary.allocatedMinutes,0);
});

test('a complete allocation is not added twice to the available date capacity', () => {
  const summary=summarize({days:[{date:'2026-11-10',minutes:328*60}],examDate:'',isExcludedDate:()=>false,dayMinutes:d=>d.minutes,allocatedMinutes:328*60});
  assert.equal(summary.scheduledMinutes,328*60);
  assert.equal(summary.missingMinutes,0);
  assert.equal(summary.unallocatedMinutes,0);
  assert.equal(summary.freeMinutes,0);
});
