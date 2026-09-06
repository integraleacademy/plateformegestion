import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {uniqueSignatureContent,isStudioSlogan,STUDIO_SLOGAN} from '../static/studio_visuals/js/studio-content-rules.js';
import {motionPose,supportedVideoType} from '../static/studio_visuals/js/studio-motion.js';
import {renderNew2TemplateBody,NEW2_IDS} from '../static/studio_visuals/js/studio-new2-templates.js';
import {defaultContentForFormation} from '../static/studio_visuals/js/studio-store.js';
const catalog=JSON.parse(readFileSync('static/studio_visuals/data/templates.json','utf8')).templates;
test('legacy slogan defaults are de-duplicated without changing the saved content',()=>{
  const saved={title:STUDIO_SLOGAN+'.',cta:STUDIO_SLOGAN,quote:STUDIO_SLOGAN,introduction:'Mon projet personnel'};
  const rendered=uniqueSignatureContent(saved);
  for(const key of ['title','cta','quote'])assert.equal(isStudioSlogan(rendered[key]),false);
  assert.equal(saved.cta,STUDIO_SLOGAN);assert.equal(rendered.introduction,saved.introduction);
  assert.equal(isStudioSlogan('  FAITES LE PREMIER PAS VERS VOTRE FUTUR MÉTIER ! '),true);
  for(const code of ['A3P','APS','DIRIGEANT','SSIAP','VTC','OR'])assert.equal(isStudioSlogan(defaultContentForFormation(code).cta),false);
});
test('NEW2 contains twenty different compositions with matching animation metadata',()=>{
  const templates=catalog.filter(t=>t.isNew2),structures=[];
  assert.equal(templates.length,20);assert.deepEqual(templates.map(t=>t.id),NEW2_IDS);
  assert.equal(templates.filter(t=>t.motion).length,12);assert.equal(templates.filter(t=>t.hasEmojis).length,11);
  for(const template of templates){
    assert.ok(template.name.startsWith('NEW2 · '));assert.equal(template.supportedFormats.length,4);
    const html=renderNew2TemplateBody({template,project:{formation:'A3P'},slide:{content:{title:'Titre <script>',cta:'Contactez-nous'}}});
    assert.ok(html.includes('Titre &lt;script&gt;'));assert.equal(html.includes('<script>'),false);
    assert.equal(html.includes('data-motion='),Boolean(template.motion),template.id);
    // Compare actual element topology, not IDs masquerading as unique designs.
    structures.push([...html.matchAll(/<\/?([a-z][a-z0-9]*)\b[^>]*>/g)].map(m=>(m[0][1]==='/'?'/':'')+m[1]).join(','));
  }
  assert.equal(new Set(structures).size,20);
});
test('motion is loopable and bounded and MP4 falls back cleanly where unsupported',()=>{
  for(const kind of ['orbit','pulse','float','rise','bob']){
    const a=motionPose(kind,0),b=motionPose(kind,1);
    for(const key of Object.keys(a))assert.ok(Math.abs(a[key]-b[key])<1e-8);
    for(let i=0;i<=100;i++){const p=motionPose(kind,i/100);assert.ok(Math.abs(p.x)<=10&&Math.abs(p.y)<=11&&p.scale>=.97&&p.scale<=1.03)}
  }
  assert.equal(supportedVideoType({isTypeSupported:type=>type==='video/mp4'}),'video/mp4');
  assert.equal(supportedVideoType({isTypeSupported:type=>type==='video/mp4;codecs=avc1.424028'||type==='video/webm;codecs=vp9'}),'video/mp4;codecs=avc1.424028');
  assert.equal(supportedVideoType({isTypeSupported:type=>type==='video/webm;codecs=vp8'}),'video/webm;codecs=vp8');
  assert.equal(supportedVideoType({isTypeSupported:()=>false}),null);
});
