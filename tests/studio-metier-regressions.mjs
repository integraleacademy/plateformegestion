import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {METIER_DESIGNS,renderMetierTemplateBody,renderMetierIllustration} from '../static/studio_visuals/js/studio-metier-templates.js';
import {defaultContentForFormation,normalizeSlideContentForTemplate} from '../static/studio_visuals/js/studio-store.js';

const catalog=JSON.parse(readFileSync(new URL('../static/studio_visuals/data/templates.json',import.meta.url))).templates;
const templates=catalog.filter(t=>t.isMetier);
test('each profession has ten complete templates with its own artwork and correct preset',()=>{
 assert.equal(templates.length,50);
 assert.equal(METIER_DESIGNS.length,50);
 assert.equal(new Set(METIER_DESIGNS.map(renderMetierIllustration)).size,50);
 assert.equal(new Set(METIER_DESIGNS.map(d=>d.layout)).size,10);
 for(const formation of ['SSIAP','APS','VTC','A3P','DIRIGEANT']){
  const collection=templates.filter(t=>t.formationPreset===formation);
  assert.equal(collection.length,10,formation);
  assert.deepEqual(collection.map(t=>t.professionIndex),[1,2,3,4,5,6,7,8,9,10]);
 }
 for(const template of templates){
  const d=METIER_DESIGNS.find(d=>d.id===template.id);
  assert.ok(d,template.id);
  assert.equal(template.formationPreset,d.formation);
  assert.equal(template.renderer,'renderMetierTemplate');
  assert.equal(template.status,'ready');
  assert.deepEqual(template.contentDefaults,d.contentDefaults);
  assert.equal(template.supportedFormats.length,4);
  const body=renderMetierTemplateBody({template,project:{formation:d.formation},slide:{content:d.contentDefaults}});
  assert.equal((body.match(/data-content-key="title"/g)||[]).length,1);
  assert.equal((body.match(/data-content-key="introduction"/g)||[]).length,1);
  assert.equal((body.match(/data-content-key="cta"/g)||[]).length,1);
  assert.equal(body.includes('data-motion='),Boolean(template.motion));
  assert.ok(!/175 h|CPF|🛡|Faites le premier pas/.test(body));
 }
});
test('selecting a mission updates automatic copy while retaining contact details',()=>{
 const first=templates[0],next=templates[1];
 const slide={content:{...defaultContentForFormation('APS'),footer:{website:'mon-centre.fr',phone:'0102030405'}}};
 normalizeSlideContentForTemplate(slide,first);
 assert.equal(slide.content.title,first.contentDefaults.title);
 assert.equal(slide.content._autoFormation,'SSIAP');
 normalizeSlideContentForTemplate(slide,next);
 assert.equal(slide.content.title,next.contentDefaults.title);
 assert.equal(slide.content._metierTemplateId,next.id);
 assert.equal(slide.content.footer.website,'mon-centre.fr');
 assert.equal(slide.content.footer.phone,'0102030405');
});
test('manual copy remains editable, survives a template change and is escaped',()=>{
 const template=templates[13],title='<script>alert("texte")</script>';
 const slide={content:{...defaultContentForFormation('APS'),title,_manual:true}};
 normalizeSlideContentForTemplate(slide,template);
 assert.equal(slide.content.title,title);
 const body=renderMetierTemplateBody({template,project:{formation:'APS'},slide});
 assert.ok(body.includes('&lt;script&gt;'));
 assert.ok(!body.includes('<script>'));
});
test('missing métier compositions fail explicitly',()=>{
 assert.throws(()=>renderMetierTemplateBody({template:{id:'metier_missing'}}),/inconnue/);
 assert.throws(()=>renderMetierIllustration({formation:'APS',slug:'missing'}),/inconnue/);
});
