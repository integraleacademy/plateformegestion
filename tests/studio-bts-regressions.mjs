import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {BTS_DESIGNS,BTS_COURSES,renderBtsIllustration,renderBtsTemplateBody} from '../static/studio_visuals/js/studio-bts-templates.js';
import {FORMATS,FORMATION_CONFIG,createProject,defaultContentForFormation,normalizeSlideContentForTemplate} from '../static/studio_visuals/js/studio-store.js';

const catalog=JSON.parse(readFileSync(new URL('../static/studio_visuals/data/templates.json',import.meta.url))).templates;
const themes=JSON.parse(readFileSync(new URL('../static/studio_visuals/data/themes.json',import.meta.url)));
const bts=catalog.filter(t=>t.isBts);
test('60 selectable BTS models cover all requested audiences and every export format',()=>{
 assert.equal(bts.length,60);assert.equal(new Set(bts.map(t=>t.id)).size,60);
 assert.equal(bts.filter(t=>t.motion).length,36);
 for(const formation of Object.keys(BTS_COURSES)){
  const models=bts.filter(t=>t.formationPreset===formation);
  assert.equal(models.length,10);assert.equal(new Set(models.map(t=>t.composition)).size,10);
  assert.ok(themes[formation]&&FORMATION_CONFIG[formation]);
  const defaults=defaultContentForFormation(formation);
  assert.equal(defaults.duration,'');assert.equal(defaults.financing,'');assert.equal(defaults.availability,'');
  assert.doesNotMatch(defaults.title,/Devenez Management|Devenez Professions/);
 }
 for(const t of bts){
  assert.equal(t.status,'ready');assert.equal(t.renderer,'renderBtsTemplate');assert.ok(t.hasEmojis);
  assert.deepEqual(t.supportedFormats,Object.keys(FORMATS));
  const d=BTS_DESIGNS.find(d=>d.id===t.id);assert.deepEqual(t.contentDefaults,d.contentDefaults);
  const html=renderBtsTemplateBody({template:t,slide:{content:defaultContentForFormation('APS')}});
  assert.ok(html.includes(d.title));
  for(const key of ['title','introduction','cta'])assert.equal(html.split(`data-content-key="${key}"`).length-1,1);
  assert.equal(html.includes('data-motion='),Boolean(t.motion));
  assert.doesNotMatch(html,/\b\d{2}\s*\/\s*\d{2}\b|🛡|175 h|CPF|Faites le premier pas|undefined|NaN/);
  if(t.formationPreset==='BTS')for(const name of ['MOS','PI','MCO','NDRC','CI','CG'])assert.ok(html.includes(name));
 }
 assert.equal(new Set(BTS_DESIGNS.map(renderBtsIllustration)).size,60);
 assert.equal(catalog.filter(t=>t.isMetier).length,125);assert.equal(catalog.filter(t=>t.isGeneral).length,30);
});
test('changing a BTS model updates automatic copy and retains custom contact data',()=>{
 const project=createProject({formation:'APS'}),slide=project.slides[0];
 slide.content.footer={website:'centre.fr',phone:'0102030405'};
 for(const template of bts){
  normalizeSlideContentForTemplate(slide,template);
  assert.equal(slide.content.title,template.contentDefaults.title);
  assert.equal(slide.content._autoFormation,template.formationPreset);
  assert.equal(slide.content.footer.website,'centre.fr');
 }
});
test('manual edits survive switching models and are escaped in the renderer',()=>{
 const content={...defaultContentForFormation('BTS PI'),_manual:true,title:'<img src=x onerror="alert(1)">',introduction:'Mon parcours & mon projet',cta:'Mon choix'};
 const slide={content};normalizeSlideContentForTemplate(slide,bts[0]);
 assert.equal(slide.content.title,content.title);
 const html=renderBtsTemplateBody({template:bts[0],slide});
 assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('<img src=x'));assert.ok(html.includes('Mon parcours &amp; mon projet'));
});
