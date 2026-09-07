import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {GENERAL_DESIGNS} from '../static/studio_visuals/js/studio-general-templates.js';
import {renderMetierIllustration,renderMetierTemplateBody} from '../static/studio_visuals/js/studio-metier-templates.js';
import {defaultContentForFormation,normalizeSlideContentForTemplate} from '../static/studio_visuals/js/studio-store.js';

const catalog=JSON.parse(readFileSync(new URL('../static/studio_visuals/data/templates.json',import.meta.url))).templates;
const general=catalog.filter(t=>t.isGeneral);

test('thirty general compositions are distinct, gold, editable and available in every format',()=>{
 assert.equal(general.length,30);
 assert.equal(new Set(general.map(t=>t.id)).size,30);
 assert.equal(new Set(GENERAL_DESIGNS.map(renderMetierIllustration)).size,30);
 assert.equal(new Set(GENERAL_DESIGNS.map(d=>d.layout)).size,15);
 assert.equal(general.filter(t=>t.motion).length,17);
 for(const template of general){
  assert.equal(template.formationPreset,'OR');
  assert.equal(template.collection,'GÉNÉRAL');
  assert.equal(template.status,'ready');
  assert.equal(template.supportedFormats.length,4);
  const d=GENERAL_DESIGNS.find(d=>d.id===template.id);
  assert.deepEqual(template.contentDefaults,d.contentDefaults);
  const body=renderMetierTemplateBody({template,slide:{content:template.contentDefaults}});
  for(const key of ['title','introduction','cta'])assert.equal(body.split(`data-content-key="${key}"`).length-1,1);
  assert.equal(body.includes('data-motion='),Boolean(template.motion));
  assert.doesNotMatch(body,/\b\d{2}\s*\/\s*\d{2}\b|FORMATION OR|🛡|175 h|CPF|Faites le premier pas/);
  assert.doesNotMatch(renderMetierIllustration(d),/NaN|undefined/);
 }
 assert.equal(catalog.filter(t=>t.isMetier).length,125,'profession collections retain their own filter and count');
});

test('general presets replace automatic profession copy and keep custom contact details',()=>{
 const slide={content:{...defaultContentForFormation('SSIAP'),footer:{website:'mon-centre.fr',phone:'0102030405'}}};
 normalizeSlideContentForTemplate(slide,general[0]);
 assert.equal(slide.content._autoFormation,'OR');
 assert.equal(slide.content.title,general[0].contentDefaults.title);
 normalizeSlideContentForTemplate(slide,general[1]);
 assert.equal(slide.content.cta,general[1].contentDefaults.cta);
 assert.equal(slide.content.footer.website,'mon-centre.fr');
 assert.equal(slide.content.footer.phone,'0102030405');
});

test('general templates preserve manual content and escape it in the canvas',()=>{
 const title='<img src=x onerror="alert(1)">';
 const slide={content:{...defaultContentForFormation('OR'),title,_manual:true}};
 normalizeSlideContentForTemplate(slide,general[2]);
 assert.equal(slide.content.title,title);
 const body=renderMetierTemplateBody({template:general[2],slide});
 assert.ok(body.includes('&lt;img'));
 assert.ok(!body.includes('<img src=x'));
});
