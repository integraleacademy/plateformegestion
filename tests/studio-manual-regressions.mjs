import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {renderManualTemplateBody,MANUAL_LAYOUTS} from '../static/studio_visuals/js/studio-manual-templates.js';
import {createProject,normalizeSlideContentForTemplate} from '../static/studio_visuals/js/studio-store.js';
const catalog=JSON.parse(readFileSync('static/studio_visuals/data/templates.json','utf8')).templates;
const manuals=catalog.filter(t=>t.isManual);
test('77 illustrated designs have unique IDs, local assets and complete editable content',()=>{
 assert.equal(manuals.length,77);assert.equal(new Set(catalog.map(t=>t.id)).size,catalog.length);
 assert.equal(new Set(manuals.map(t=>t.formationPreset)).size,7);
 for(const t of manuals){
  assert.ok(MANUAL_LAYOUTS.includes(t.manualLayout));assert.equal(t.supportedFormats.length,4);
  for(const a of [t.illustration,t.secondaryIllustration]){assert.match(a.file,/^[a-z0-9_]+\.webp$/);assert.ok(existsSync('static/studio_visuals/img/manuals/'+a.file),a.file);assert.ok(a.alt);}
  const p=createProject({formation:t.formationPreset,templateId:t.id});normalizeSlideContentForTemplate(p.slides[0],t);
  const html=renderManualTemplateBody({template:t,slide:p.slides[0]});
  for(const k of ['eyebrow','title','introduction','cta'])assert.equal((html.match(new RegExp(`data-content-key="${k}"`,'g'))||[]).length,1,t.id+' '+k);
  assert.ok(html.includes(t.contentDefaults.title));assert.ok(!html.includes('undefined'));assert.ok(!html.includes('175 h'));
  assert.equal((html.match(/<img /g)||[]).length,t.manualLayout==='storyboard'?3:t.manualLayout==='duo'?2:1);
 }
});
test('all compositions escape editable values and preserve manual edits',()=>{
 for(const t of manuals){const p=createProject({templateId:t.id,formation:t.formationPreset});p.slides[0].content={...t.contentDefaults,title:'Titre <script>alert(1)</script>',introduction:'A & B',_manual:true};normalizeSlideContentForTemplate(p.slides[0],t);const html=renderManualTemplateBody({template:t,slide:p.slides[0]});assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));assert.ok(html.includes('A &amp; B'));}
});
