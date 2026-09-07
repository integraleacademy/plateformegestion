import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {NEW3_DESIGNS,NEW3_IDS,renderNew3TemplateBody} from '../static/studio_visuals/js/studio-new3-templates.js';
const catalog=JSON.parse(readFileSync('static/studio_visuals/data/templates.json','utf8')).templates.filter(t=>t.isNew3);
test('NEW3 provides fifty complete compositions with accurate catalog capabilities',()=>{
 assert.equal(catalog.length,50);assert.equal(new Set(NEW3_IDS).size,50);
 assert.deepEqual(catalog.map(t=>t.id),NEW3_IDS);
 assert.equal(catalog.filter(t=>t.motion).length,30);assert.equal(catalog.filter(t=>t.hasEmojis).length,18);
 const structures=[];
 for(const t of catalog){
  assert.ok(t.name.startsWith('NEW3 · '));assert.equal(t.supportedFormats.length,4);
  const html=renderNew3TemplateBody({template:t,project:{formation:'APS'},slide:{content:{title:'TITLE <script>',introduction:'INTRO & suite',cta:'CTA "ici"',startDate:'DATE <test>'}}});
  for(const key of ['title','introduction','cta'])assert.equal((html.match(new RegExp(`data-content-key="${key}"`,'g'))||[]).length,1,t.id+' '+key);
  assert.ok(html.includes('TITLE &lt;script&gt;'));assert.ok(html.includes('INTRO &amp; suite'));assert.ok(html.includes('CTA &quot;ici&quot;'));assert.equal(html.includes('<script>'),false);
  assert.equal(html.includes('data-motion='),Boolean(t.motion),t.id);
  const keys=[...new Set([...html.matchAll(/data-content-key="([^"]+)"/g)].map(m=>m[1]))];assert.deepEqual(t.supportedContent,keys,t.id);
  // Actual element topology and SVG paths distinguish the designs, without
  // relying on collection IDs, names or arbitrary wrappers.
  structures.push([...html.matchAll(/<\/?([a-z][a-z0-9]*)\b[^>]*>/g)].map(m=>(m[0][1]==='/'?'/':'')+m[1]+(m[1]==='path'?(m[0].match(/ d="([^"]+)"/)||[])[1]:'' )).join(','));
 }
 assert.equal(new Set(structures).size,50);
});
test('NEW3 preserves formation labels and rejects an unknown composition',()=>{
 for(const d of NEW3_DESIGNS)for(const formation of ['APS','A3P','SSIAP','DIRIGEANT','VTC','OR']){
  const html=renderNew3TemplateBody({template:{id:d.id},project:{formation},slide:{content:{}}});
  assert.ok(html.includes('data-new3-design="'+d.id+'"'));
  assert.equal(html.includes('undefined'),false);assert.equal(html.includes('NaN'),false);
 }
 assert.throws(()=>renderNew3TemplateBody({template:{id:'missing'}}),/inconnue/);
});
