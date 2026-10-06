import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {renderManualTemplateBody,MANUAL_LAYOUTS} from '../static/studio_visuals/js/studio-manual-templates.js';
import {applyManualCarousel,retargetManualCarousel} from '../static/studio_visuals/js/studio-manual-carousels.js';
import {createProject,FORMATS,normalizeSlideContentForTemplate} from '../static/studio_visuals/js/studio-store.js';
const catalog=JSON.parse(readFileSync('static/studio_visuals/data/templates.json','utf8')).templates;
const manuals=catalog.filter(t=>t.isManual);
test('77 illustrated designs have unique IDs, local assets and complete editable content',()=>{
 assert.equal(manuals.length,77);assert.equal(new Set(catalog.map(t=>t.id)).size,catalog.length);
 assert.equal(new Set(manuals.map(t=>t.formationPreset)).size,7);
 for(const t of manuals){
  assert.ok(MANUAL_LAYOUTS.includes(t.manualLayout));assert.equal(t.supportedFormats.length,4);
  for(const a of [t.illustration,t.secondaryIllustration]){assert.match(a.file,/^[a-z0-9_]+\.webp$/);assert.ok(existsSync('static/studio_visuals/img/manuals/'+a.file),a.file);assert.ok(a.alt);}
  const p=createProject({formation:t.formationPreset,templateId:t.id});if(t.isCarousel)applyManualCarousel(p,t);normalizeSlideContentForTemplate(p.slides[0],t);
  const html=renderManualTemplateBody({template:t,slide:p.slides[0]});
  for(const k of ['eyebrow','title','introduction','cta'])assert.equal((html.match(new RegExp(`data-content-key="${k}"`,'g'))||[]).length,1,t.id+' '+k);
  assert.ok(html.includes((t.pages?.[0]?.contentDefaults||t.contentDefaults).title));assert.ok(!html.includes('undefined'));assert.ok(!html.includes('175 h'));
  assert.equal((html.match(/<img /g)||[]).length,1);
 }
});
test('all compositions escape editable values and preserve manual edits',()=>{
 for(const t of manuals){const p=createProject({templateId:t.id,formation:t.formationPreset});p.slides[0].content={...t.contentDefaults,title:'Titre <script>alert(1)</script>',introduction:'A & B',_manual:true};normalizeSlideContentForTemplate(p.slides[0],t);const html=renderManualTemplateBody({template:t,slide:p.slides[0]});assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));assert.ok(html.includes('A &amp; B'));}
});

test('all 14 multi-scene models create one independent, editable slide per illustration',()=>{
 const carousels=manuals.filter(t=>t.isCarousel);assert.equal(carousels.length,14);
 for(const t of carousels){
  const count=t.manualLayout==='storyboard'?3:2,p=createProject({formation:'APS'});
  p.format=FORMATS.instagram_portrait;p.slides[0].content.footer.phone='01 02 03 04 05';p.branding.logoUrl='/custom-logo.png';
  applyManualCarousel(p,t);
  assert.equal(p.slides.length,count);assert.equal(new Set(p.slides.map(s=>s.id)).size,count);
  assert.equal(p.activeSlideIndex,0);assert.equal(p.formation,t.formationPreset);assert.equal(p.format,FORMATS.instagram_portrait);
  assert.equal(p.branding.logoUrl,'/custom-logo.png');
  const files=[];
  for(const [i,slide] of p.slides.entries()){
   normalizeSlideContentForTemplate(slide,t);
   assert.equal(slide.carouselPage,i);assert.equal(slide.content.title,t.pages[i].contentDefaults.title);
   assert.equal(slide.content.footer.phone,'01 02 03 04 05');
   const html=renderManualTemplateBody({template:t,slide});
   assert.equal((html.match(/<img /g)||[]).length,1);
   assert.ok(html.includes(t.pages[i].illustration.file));assert.ok(html.includes(`${i+1} / ${count}`));
   files.push(t.pages[i].illustration.file);
  }
  assert.equal(new Set(files).size,count);
  p.slides[1].content.title='Ma scène personnalisée';p.slides[1].content._manual=true;
  normalizeSlideContentForTemplate(p.slides[1],t);
  assert.equal(p.slides[1].content.title,'Ma scène personnalisée');
  assert.notEqual(p.slides[0].content.title,'Ma scène personnalisée');assert.notEqual(t.pages[1].contentDefaults.title,'Ma scène personnalisée');
  const saved=JSON.parse(JSON.stringify(p));assert.equal(saved.slides[1].carouselPage,1);
 }
});
test('switching the formation retargets every scene while preserving edited content',()=>{
 const before=manuals.find(t=>t.id==='manual_aps_storyboard'),after=manuals.find(t=>t.id==='manual_ssiap_storyboard');
 const p=createProject();applyManualCarousel(p,before);p.slides[1].content.title='Titre personnel';p.slides[1].content._manual=true;
 retargetManualCarousel(p,before,after);
 assert.ok(p.slides.every(s=>s.templateId===after.id));assert.equal(p.slides.length,3);
 assert.equal(p.slides[0].content.title,after.pages[0].contentDefaults.title);assert.equal(p.slides[1].content.title,'Titre personnel');
 assert.ok(renderManualTemplateBody({template:after,slide:p.slides[2]}).includes(after.pages[2].illustration.file));
});
