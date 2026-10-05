import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import vm from 'node:vm';
import {renderCanvasTemplateBody,CANVAS_LAYOUTS} from '../static/studio_visuals/js/studio-expanded-templates.js';
import {applyCanvasTemplate} from '../static/studio_visuals/js/studio-canvas-models.js';
import {createProject,FORMATS,normalizeSlideContentForTemplate} from '../static/studio_visuals/js/studio-store.js';
const templates=JSON.parse(readFileSync('static/studio_visuals/data/templates.json','utf8')).templates;
const canvases=templates.filter(t=>t.isCanvas),expansion=templates.filter(t=>t.isStudioExpansion);
const app=readFileSync('static/studio_visuals/js/studio-app.js','utf8');

test('the expansion adds exactly 35 illustrated models and 15 canvases without duplicate IDs',()=>{
 assert.equal(expansion.length,50);assert.equal(expansion.filter(t=>t.isManual).length,35);assert.equal(canvases.length,15);
 assert.equal(new Set(templates.map(t=>t.id)).size,templates.length);
 assert.deepEqual(new Set(canvases.map(t=>t.canvasLayout)),new Set(CANVAS_LAYOUTS));
 for(const t of canvases){assert.deepEqual(t.supportedFormats,Object.keys(FORMATS));assert.ok(existsSync('static/studio_visuals/img/manuals/'+t.illustration.file));}
});
test('single canvases retain the formation, branding, footer and compatible format',()=>{
 for(const t of canvases.filter(t=>!t.isCarousel)){
  const p=createProject({formation:'A3P'});p.format=FORMATS.instagram_story;p.slides[0].content.footer.phone='01 02 03 04 05';p.branding.logoUrl='/custom-logo.png';
  applyCanvasTemplate(p,t);normalizeSlideContentForTemplate(p.slides[0],t);
  assert.equal(p.formation,'A3P');assert.equal(p.format,FORMATS.instagram_story);assert.equal(p.branding.logoUrl,'/custom-logo.png');assert.equal(p.slides[0].content.footer.phone,'01 02 03 04 05');assert.equal(p.slides[0].content._autoFormation,'A3P');
  assert.equal(p.slides[0].content.financing,'');assert.equal(p.slides[0].content.availability,'');assert.ok(!JSON.stringify(p.slides[0].content).includes('175 h'));
 }
});
test('carousel canvases create five independent editable pages with complete content',()=>{
 const carousels=canvases.filter(t=>t.isCarousel);assert.equal(carousels.length,2);
 for(const t of carousels){
  const p=createProject({formation:'VTC'});applyCanvasTemplate(p,t);assert.equal(p.slides.length,5);assert.equal(new Set(p.slides.map(s=>s.id)).size,5);assert.equal(p.activeSlideIndex,0);
  for(const [i,s] of p.slides.entries()){
   normalizeSlideContentForTemplate(s,t);assert.equal(s.carouselPage,i);assert.equal(s.content.title,t.pages[i].contentDefaults.title);
   const html=renderCanvasTemplateBody({template:t,slide:s});assert.ok(html.includes(`data-canvas-layout="${t.pages[i].layout}"`));assert.ok(html.includes(`${i+1} / 5`));assert.ok(!html.includes('undefined'));
  }
  const stepSlide=p.slides.find(s=>s.content.steps.length);const page=stepSlide.carouselPage,original=t.pages[page].contentDefaults.steps[0].title;
  stepSlide.content.steps[0].title='Personnalisé';stepSlide.content._manual=true;normalizeSlideContentForTemplate(stepSlide,t);
  assert.equal(stepSlide.content.steps[0].title,'Personnalisé');assert.equal(t.pages[page].contentDefaults.steps[0].title,original);
 }
});
test('every canvas page renders its editable fields and escapes user content',()=>{
 for(const t of canvases){const p=createProject();applyCanvasTemplate(p,t);
  for(const s of p.slides){
   const html=renderCanvasTemplateBody({template:t,slide:s});
   const keys=[...html.matchAll(/data-content-key="([^"]+)"/g)].map(m=>m[1]);assert.equal(new Set(keys).size,keys.length,t.id);
   for(const key of t.pages?.[s.carouselPage]?.supportedContent||t.supportedContent){if(key==='footer')continue;assert.ok(keys.some(k=>k===key||k.startsWith(key+'.')),t.id+' '+key);}
   for(const key of keys){const parts=key.split('.');let node=s.content;while(parts.length>1)node=node[parts.shift()];node[parts[0]]='<img src=x onerror="alert(1)">';}
   const escaped=renderCanvasTemplateBody({template:t,slide:s});assert.ok(!escaped.includes('<img src=x'));assert.ok(escaped.includes('&lt;img'));
  }
 }
});
test('nested edits through the editor survive normalization and formation changes',()=>{
 const t=canvases.find(t=>t.id==='canvas_programme'),p=createProject({formation:'APS'});applyCanvasTemplate(p,t);
 const state={templateRegistry:{[t.id]:t}},sandbox={state,store:{project:p,commit(_label,fn){fn(p)}},getActiveTemplate:()=>t,PUBLICATION_DATA_FIELDS:[],FORMATION_CONFIG:{BTS:{label:'BTS',defaultThemeId:'bts_default'}},showToast:()=>{}};
 vm.createContext(sandbox);
 for(const name of ['setContentValue','setFormation']){const line=app.split('\n').find(l=>l.startsWith('function '+name+'('));assert.ok(line);vm.runInContext(line,sandbox);}
 sandbox.setContentValue('steps.0.title','Mon module personnalisé');normalizeSlideContentForTemplate(p.slides[0],t);
 sandbox.setFormation('BTS');normalizeSlideContentForTemplate(p.slides[0],t);
 assert.equal(p.slides[0].content.steps[0].title,'Mon module personnalisé');assert.equal(p.slides[0].content._manual,true);assert.equal(p.formation,'BTS');assert.equal(p.themeId,'bts_default');
 assert.notEqual(t.contentDefaults.steps[0].title,'Mon module personnalisé');
});
