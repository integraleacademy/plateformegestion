import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
function datasetFrom(attrs){const d={};for(const m of attrs.matchAll(/data-([a-z0-9-]+)="([^"]*)"/g)){const key=m[1].replace(/-([a-z])/g,(_,c)=>c.toUpperCase());d[key]=m[2]}return d}
class MiniNode{constructor(tag){this.tagName=tag;this.dataset={};this.style={setProperty(k,v){this[k]=v}};this._html='';this.className=''}set innerHTML(v){this._html=v}get innerHTML(){return this._html}get textContent(){return this._html.replace(/<[^>]+>/g,'')}querySelectorAll(sel){if(sel==='[data-layout-role]')return [...this._html.matchAll(/<[^>]*data-layout-role="[^"]+"[^>]*>/g)].map(m=>({dataset:datasetFrom(m[0])}));if(sel==='img[alt="Intégrale Academy"]')return [...this._html.matchAll(/<img[^>]*alt="Intégrale Academy"[^>]*>/g)].map(m=>({dataset:datasetFrom(m[0])}));return []}querySelector(sel){return this.querySelectorAll(sel)[0]||null}}
global.document={createElement:t=>new MiniNode(t)};
const {renderSlide,buildTemplateRegistry,getTemplateStructureFingerprint,recommendTemplates}=await import('../static/studio_visuals/js/studio-renderer.js');
const data=JSON.parse(readFileSync('static/studio_visuals/data/templates.json','utf8'));
const themes=JSON.parse(readFileSync('static/studio_visuals/data/themes.json','utf8'));
const ready=data.templates.filter(t=>t.status==='ready');
assert.ok(ready.length >= 110);
const newTemplates=ready.filter(template=>template.isNew);
assert.equal(newTemplates.length,50);
assert.equal(new Set(newTemplates.map(template=>template.id)).size,50);
assert.equal(new Set(newTemplates.map(template=>template.previewStyle)).size,50);
assert.ok(new Set(newTemplates.map(template=>template.brandLayout)).size>=10);
assert.ok(newTemplates.every(template=>template.name.startsWith('NEW')));
assert.ok(new Set(ready.map(t=>t.renderer)).size >= 24);
const project={formation:'A3P',format:{width:1080,height:1080},branding:{logoVisible:true,logoUrl:'/static/img/integrale-academy-logo.svg'},slides:[],activeSlideIndex:0};
const content={title:'Devenez agent de protection physique des personnes',highlightedText:'A3P',introduction:'Une formation concrète pour lancer votre futur métier.',duration:'175 h',location:'Puget-sur-Argens',financing:'CPF',startDate:'09/09/2026',endDate:'30/10/2026',examDate:'04/11/2026',availability:'12',cta:'Contactez-nous',quote:'Votre futur métier commence par un premier pas.',stats:[{label:'Durée',value:'175 h'},{label:'Lieu',value:'Puget-sur-Argens'},{label:'Financement',value:'CPF'},{label:'Certification',value:'A3P'}]};
const registry=buildTemplateRegistry(ready);
const fingerprints=new Map();
for(const t of ready){const slide={templateId:t.id,content,options:{showSafeMargins:false}};const node=renderSlide(project,slide,'export',{templates:ready,templateRegistry:registry,themes:{A3P:{}}});assert.equal(node.dataset.renderedTemplateId,t.id);assert.equal(node.dataset.templateFamily,t.family);assert.equal(node.dataset.studioFormat,'1080x1080');assert.equal(node.dataset.canvasWidth,'1080');assert.equal(node.dataset.canvasHeight,'1080');assert.ok(node.querySelector('img[alt="Intégrale Academy"]'), `${t.id} logo`);assert.ok(node.textContent.includes('Faites le premier pas vers votre futur métier'), `${t.id} slogan`);assert.ok(node.innerHTML.includes('data-region="brand"'),`${t.id} brand region`);assert.ok(node.innerHTML.includes('data-region="footer"'),`${t.id} footer region`);assert.ok(node.innerHTML.includes('data-fit='),`${t.id} fitted text`);const fp=getTemplateStructureFingerprint(node);assert.ok(fp.length>15, `${t.id} fingerprint`);fingerprints.set(t.id,fp)}
assert.equal(new Set(newTemplates.map(template=>fingerprints.get(template.id))).size,50);
for(const a of ready.slice(0,24)){for(const b of ready.slice(0,24)){if(a.family!==b.family)assert.notEqual(fingerprints.get(a.id),fingerprints.get(b.id), `${a.id} vs ${b.id}`)}}
const formats={instagram_square:{width:1080,height:1080},instagram_portrait:{width:1080,height:1350},instagram_story:{width:1080,height:1920},linkedin_landscape:{width:1200,height:627}};
let combinations=0;
for(const [formation,theme] of Object.entries(themes)){for(const [id,dims] of Object.entries(formats)){for(const template of ready){const themedProject={...project,formation,format:{id,...dims}};const slide={templateId:template.id,content,options:{showSafeMargins:false}};const node=renderSlide(themedProject,slide,'export',{templates:ready,templateRegistry:registry,themes});assert.equal(node.dataset.formation,formation);assert.equal(node.dataset.studioFormat,id);assert.equal(node.style['--formation-primary'],theme.primary);assert.equal(node.style['--formation-secondary'],theme.secondary);assert.equal(node.style['--formation-dark'],theme.surfaceDark);assert.ok(node.innerHTML.includes(`class="sv-brand__formation">${formation}</span>`),`${formation} badge`);combinations++}}}
assert.deepEqual(recommendTemplates({...content,examDate:'04/11/2026'}).slice(0,2),['session_calendar','session_ticket']);
console.log(`${ready.length} templates ready, 50 NEW designs distinct, ${combinations} formation/format/template combinations rendered`);
