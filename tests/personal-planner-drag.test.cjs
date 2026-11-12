/* Real browser + real Flask/SQLite API, isolated from production.
 * PYTHON=/path/to/python CHROMIUM_PATH=/path/to/chromium node tests/personal-planner-drag.test.cjs
 * Requires Playwright, Flask and the project's Python dependencies.
 */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {chromium} = require('playwright');

const fixture = spawn(process.env.PYTHON || 'python', ['-u', '-c', `
import logging, os, tempfile
from flask import Flask, session
from werkzeug.serving import make_server
from services.personal_planner import register
logging.getLogger('werkzeug').setLevel(logging.ERROR)
with tempfile.TemporaryDirectory() as directory:
    app = Flask(__name__, template_folder=os.path.abspath('templates'), static_folder=os.path.abspath('static'))
    app.secret_key = 'isolated-browser-test-only'
    @app.before_request
    def login_fixture():
        session['admin_logged'] = True
    register(app, directory, lambda: {'sessions': [{'id': 'training-test', 'formation': 'APS', 'date_debut': '2026-11-12'}]}, lambda s, m: None)
    server = make_server('127.0.0.1', 0, app)
    print('http://127.0.0.1:' + str(server.server_port), flush=True)
    server.serve_forever()
`], {stdio:['ignore','pipe','inherit']});
let browser;
const passed = [];
const check = label => { passed.push(label); console.log('PASS',label); };

(async () => {
  const [output] = await once(fixture.stdout, 'data');
  const origin = output.toString().trim();
  browser = await chromium.launch({headless:true, ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {})});
  const page = await browser.newPage({viewport:{width:1560,height:1300},timezoneId:'Europe/Paris'});
  await page.clock.install({time:new Date('2026-11-12T12:00:00Z')});
  const errors = [];
  page.on('pageerror',e => { errors.push(e.message); console.error('Browser error:',e.message); });
  await page.addInitScript(() => {
    window.dragTrace = [];
    for (const type of ['dragstart','dragover','drop','dragend']) document.addEventListener(type,event => {
      window.dragTrace.push({type,target:event.target.className,day:event.target.closest?.('[data-day]')?.dataset.day,id:event.target.closest?.('[id]')?.id});
      if (window.dragTrace.length > 25) window.dragTrace.shift();
    },true);
  });
  await page.route('https://fonts.googleapis.com/**',r => r.abort());
  const root = '/gestion-clement-elsa';
  await page.goto(origin + root + '/');
  await page.waitForSelector('#tabs [data-tab="calendar"]');
  const api = (path,method='GET',body) => page.evaluate(async ({path,method,body}) => {
    const response = await fetch('/gestion-clement-elsa' + path, {method,headers:{'Content-Type':'application/json','X-Planner-CSRF':document.querySelector('meta[name=planner-csrf]').content},...(body ? {body:JSON.stringify(body)} : {})});
    return {status:response.status,data:await response.json()};
  }, {path,method,body});
  const create = async record => { const response = await api('/records','POST',record); assert.equal(response.status,201,JSON.stringify(response)); return response.data.ids[0]; };
  const record = async id => (await api('/data')).data.records.find(r => r.id === id);
  const day = value => page.locator(`.calendar-day[data-day="${value}"]`);
  const chip = (id,value) => day(value).locator(`[data-event="${id}"]`);
  const refresh = async () => { await page.waitForTimeout(450); await page.locator('#refresh').click(); await page.waitForFunction(() => !document.querySelector('#refresh').disabled); };
  const drag = async (id,from,to,expectedStatus=200) => {
    await chip(id,from).scrollIntoViewIfNeeded();
    await chip(id,from).hover();
    const saved = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().includes('/records/'),{timeout:10000}).catch(error => error);
    await chip(id,from).dragTo(day(to),{targetPosition:{x:30,y:25}});
    const response = await saved;
    if (response instanceof Error) {
      console.error('Drag diagnostics',await page.evaluate(() => ({events:window.dragTrace,body:document.body.className,error:document.querySelector('#load-error').textContent,scrollY:window.scrollY})));
      throw response;
    }
    assert.equal(response.status(),expectedStatus);
    await page.waitForFunction(() => !document.body.classList.contains('calendar-saving'));
    assert.equal(await page.locator('dialog[open]').count(),0,'A drop must not open the day/editor dialog');
    await page.waitForTimeout(450);
  };

  const appointment = await create({kind:'personal',title:'Rendez-vous test',start:'2026-11-13',end:'2026-11-13',start_time:'09:30',end_time:'10:45',notes:'Conserver cette note',owner:'elsa',important:true});
  const restaurant = await create({kind:'restaurant',title:'Restaurant test',start:'2026-11-16',end:'2026-11-16',start_time:'19:30',status:'booked',meal:'dinner',guests:3,address:'Adresse test'});
  const louise = await create({kind:'louise',start:'2026-11-17',end:'2026-11-19'});
  const task = await create({kind:'task',title:'Tâche test',due:'2026-11-23'});
  const stay = await create({kind:'location',place:'paris',start:'2026-11-04',end:'2026-11-07',boarding_status:'booked',boarding_start:'2026-11-03',boarding_end:'2026-11-08',transport_status:'booked',transport_start:'2026-11-03',transport_end:'2026-11-08',transport_origin:'Nice'});
  await refresh();
  await page.locator('#tabs [data-tab="calendar"]').click();

  await drag(appointment,'2026-11-13','2026-11-14');
  let saved = await record(appointment);
  assert.deepEqual([saved.start,saved.end,saved.start_time,saved.end_time,saved.notes,saved.owner,saved.important],['2026-11-14','2026-11-14','09:30','10:45','Conserver cette note','elsa',true]);
  await page.reload(); await page.locator('#tabs [data-tab="calendar"]').click();
  assert.equal(await chip(appointment,'2026-11-14').count(),1);
  check('Rendez-vous déplacé, horaires et détails conservés, persistance après rechargement');

  await drag(restaurant,'2026-11-16','2026-11-17');
  saved = await record(restaurant);
  assert.deepEqual([saved.start,saved.end,saved.start_time,saved.guests,saved.status],['2026-11-17','2026-11-17','19:30',3,'booked']);
  await drag(louise,'2026-11-18','2026-11-20');
  saved = await record(louise);
  assert.deepEqual([saved.start,saved.end],['2026-11-19','2026-11-21']);
  check('Restaurant et période de plusieurs jours déplacés depuis le jour saisi');

  await drag(task,'2026-11-23','2026-11-24');
  saved = await record(task); assert.equal(saved.due,'2026-11-24'); assert.equal(saved.done,false);
  await drag(stay + ':boarding','2026-11-04','2026-11-05');
  saved = await record(stay);
  assert.deepEqual([saved.start,saved.end,saved.boarding_start,saved.boarding_end],['2026-11-04','2026-11-07','2026-11-04','2026-11-09']);
  await drag(stay + ':transport','2026-11-03','2026-11-02');
  await drag(stay + ':transport:return','2026-11-08','2026-11-09');
  saved = await record(stay);
  assert.deepEqual([saved.start,saved.end,saved.transport_start,saved.transport_end],['2026-11-04','2026-11-07','2026-11-02','2026-11-09']);
  check('Échéance, pension liée et chaque trajet déplacés indépendamment du séjour');

  await drag(stay + ':transport:return','2026-11-09','2026-11-01',400);
  assert.equal((await record(stay)).transport_end,'2026-11-09');
  assert.equal(await chip(stay + ':transport:return','2026-11-09').count(),1);
  const before = await record(appointment);
  await chip(appointment,'2026-11-14').dragTo(day('2026-11-14'),{targetPosition:{x:30,y:25}});
  await page.waitForTimeout(450);
  assert.equal((await record(appointment)).revision,before.revision);
  const training = page.locator('.event-chip[data-event^="session:"]');
  assert.equal(await training.getAttribute('draggable'),'false');
  check('Dates incohérentes refusées, dépôt au même endroit sans écriture, formations en lecture seule');

  assert.equal((await api('/records/' + appointment,'PUT',{...before,notes:'Modifié sur un autre appareil'})).status,200);
  await drag(appointment,'2026-11-14','2026-11-15',409);
  assert.equal((await record(appointment)).start,'2026-11-14');
  assert.equal((await record(appointment)).notes,'Modifié sur un autre appareil');
  assert.match(await page.locator('#load-error').textContent(),/autre appareil/);
  await refresh();
  await page.route('**/records/' + task,r => r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Indisponibilité de test'})}));
  await drag(task,'2026-11-24','2026-11-25',503);
  await page.unroute('**/records/' + task);
  assert.equal((await record(task)).due,'2026-11-24');
  assert.equal(await chip(task,'2026-11-24').count(),1);
  check('Conflit concurrent et indisponibilité : données conservées, erreur visible');

  const projected = await create({kind:'location',place:'paris',start:'2026-11-25',end:'2026-11-27',boarding_status:'not_needed',transport_status:'booked',transport_start:'2026-11-25',transport_origin:'Nice'});
  await refresh();
  await drag(projected + ':transport','2026-11-25','2026-11-24');
  assert.equal((await record(projected)).transport_end,'');
  let projectedReturn = (await api('/data')).data.reservations.find(r => r.id === projected + ':transport:return');
  assert.equal(projectedReturn.status,'pending');
  await drag(projected + ':transport:return','2026-11-27','2026-11-28');
  projectedReturn = (await api('/data')).data.reservations.find(r => r.id === projected + ':transport:return');
  assert.equal(projectedReturn.start,'2026-11-28');
  assert.equal(projectedReturn.status,'needs_change');
  check('Retour prévisionnel : déplacer une date ne confirme jamais une réservation');

  await refresh();
  // Both the source and the toolbar must be in the viewport for a real mouse drag.
  await page.evaluate(() => window.scrollTo(0,0));
  await chip(appointment,'2026-11-14').scrollIntoViewIfNeeded();
  await chip(appointment,'2026-11-14').hover();
  const source = await chip(appointment,'2026-11-14').boundingBox();
  const next = await page.locator('#next').boundingBox();
  assert.ok(next.y >= 0 && source.y + source.height < 1300,JSON.stringify({source,next}));
  await page.mouse.move(source.x + source.width/2,source.y + source.height/2);
  await page.mouse.down();
  await page.mouse.move(source.x + 15,source.y + 10,{steps:5});
  await page.mouse.move(next.x + next.width/2,next.y + next.height/2,{steps:10});
  // Chromium needs a second move at the destination to dispatch dragover reliably.
  await page.mouse.move(next.x + next.width/2,next.y + next.height/2);
  try {
    await page.waitForFunction(() => document.querySelector('#period-label').textContent.includes('décembre'),{},{timeout:5000});
  } catch (error) {
    console.error('Navigation diagnostics',await page.evaluate(() => ({events:window.dragTrace,body:document.body.className,period:document.querySelector('#period-label').textContent,next:document.querySelector('#next').className,scrollY:window.scrollY})));
    throw error;
  }
  const target = await day('2026-12-15').boundingBox();
  const moved = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().includes(appointment));
  await page.mouse.move(target.x + 30,target.y + 25,{steps:10});
  await page.mouse.move(target.x + 30,target.y + 25);
  await page.mouse.up();
  assert.equal((await moved).status(),200);
  await page.waitForFunction(() => !document.body.classList.contains('calendar-saving'));
  assert.equal((await record(appointment)).start,'2026-12-15');
  check('Changement de mois pendant le glisser-déposer avec la flèche');

  // Switch to week view: the same handlers must work after replacing the grid.
  await page.waitForTimeout(450);
  await page.locator('#view-switch [data-view="week"]').click();
  const decemberTask = await create({kind:'task',title:'Semaine test',due:'2026-12-02'});
  await refresh();
  await drag(decemberTask,'2026-12-02','2026-12-03');
  assert.equal((await record(decemberTask)).due,'2026-12-03');
  check('Glisser-déposer dans la vue semaine');

  const recurring = (await api('/records','POST',{kind:'louise',start:'2026-10-23',end:'2026-10-25',repeat:'weekly',repeat_until:'2026-11-08'})).data.ids;
  const untouched = await record(recurring[1]);
  await page.locator('#view-switch [data-view="month"]').click();
  await page.locator('#prev').click(); await page.locator('#prev').click();
  await refresh();
  await drag(recurring[0],'2026-10-24','2026-10-26');
  saved = await record(recurring[0]);
  assert.deepEqual([saved.start,saved.end],['2026-10-25','2026-10-27']);
  assert.deepEqual(await record(recurring[1]),untouched);
  check('Changement d’heure : durée conservée et seule l’occurrence saisie est déplacée');

  assert.deepEqual(errors,[]);
  console.log(`${passed.length} scénarios navigateur réussis, aucune erreur JavaScript.`);
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (browser) await browser.close();
  fixture.kill();
});
