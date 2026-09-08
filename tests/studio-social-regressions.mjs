import {readFileSync,writeFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {SOCIAL_COURSES,CAROUSEL_DESIGNS,COVER_DESIGNS,SESSION_DESIGNS} from '../static/studio_visuals/js/studio-social-content.js';
import {createProject,ALL_FORMATS,FORMATION_CONFIG} from '../static/studio_visuals/js/studio-store.js';
import {applySocialTemplate,matchesTemplateSearch,compatibleFormat,publicationText,createCarouselZip} from '../static/studio_visuals/js/studio-social-tools.js';
import {renderSocialTemplateBody,renderSocialCoverBody} from '../static/studio_visuals/js/studio-social-templates.js';
const {templates}=JSON.parse(readFileSync('static/studio_visuals/data/templates.json'));
const themes=JSON.parse(readFileSync('static/studio_visuals/data/themes.json'));
const models=templates.filter(t=>t.isSocialSuite);
test('115 catalog entries: 65 genuine five-slide carousels, 10 covers and 40 announcements',()=>{
 assert.equal(models.length,115);assert.equal(CAROUSEL_DESIGNS.length,65);assert.equal(COVER_DESIGNS.length,10);assert.equal(SESSION_DESIGNS.length,40);
 for(const [key,course] of Object.entries(SOCIAL_COURSES)){assert.equal(CAROUSEL_DESIGNS.filter(d=>d.key===key).length,5);assert.ok(themes[course.formation]);assert.ok(FORMATION_CONFIG[course.formation]);}
 for(const kind of ['places','session'])for(const key of ['aps','a3p','desp_initial','ssiap1'])assert.equal(SESSION_DESIGNS.filter(d=>d.kind===kind&&d.key===key).length,5);
 for(const t of models){assert.ok(t.supportedFormats.every(id=>ALL_FORMATS[id]));assert.ok(['preview','ready'].includes(t.status));assert.equal(t.contentDefaults.duration,'');assert.equal(t.contentDefaults.availability,'');assert.ok(t.renderer==='renderSocialCover'||t.renderer==='renderSocialTemplate');}
});
test('all 325 slides are real editable pages, preserve their ordering and have complete matching captions',()=>{
 for(const t of models.filter(t=>t.isCarousel)){
  const p=createProject();p.slides[0].content.footer.phone='0123456789';applySocialTemplate(p,t);
  assert.equal(p.slides.length,5);assert.equal(new Set(p.slides.map(s=>s.content.title)).size,5);assert.deepEqual(p.slides.map(s=>s.carouselPage),[0,1,2,3,4]);
  assert.equal(p.formation,t.formationPreset);
  for(const slide of p.slides){assert.equal(slide.content._autoFormation,t.formationPreset);assert.equal(slide.content.footer.phone,'0123456789');const html=renderSocialTemplateBody({slide,template:t});assert.ok(html.includes('data-content-key="title"'));assert.ok(!html.includes('07/10'));}
  p.slides[2].content.title='Une précision personnalisée';p.slides[2].content.introduction='Un texte modifié <sans code actif>.';
  assert.ok(publicationText(p,t).includes('Une précision personnalisée'));assert.ok(publicationText(p,t).includes('https://www.integraleacademy.com'));
  const html=renderSocialTemplateBody({slide:p.slides[2],template:t});assert.ok(html.includes('&lt;sans code actif&gt;'));assert.ok(!html.includes('<sans code actif>'));
  const restored=JSON.parse(JSON.stringify(p));assert.deepEqual(restored.slides.map(s=>s.carouselPage),[0,1,2,3,4]);
 }
});
test('native covers switch format and leave one compatible slide; post templates restore post formats',()=>{
 const p=createProject();applySocialTemplate(p,models.find(t=>t.isCarousel));
 for(const t of models.filter(t=>t.isCover)){applySocialTemplate(p,t);assert.equal(p.slides.length,1);assert.equal(p.format.id,t.network+'_cover');assert.ok(renderSocialCoverBody({slide:p.slides[0],template:t}).includes('social-cover-title'));}
 const old=templates.find(t=>!t.isSocialSuite);assert.equal(compatibleFormat(old,p.format).id,'instagram_square');
});
test('search handles accents, apostrophes, partial names, DESP VAE and collections',()=>{
 for(const query of ['les onglets des possibles','LES ONGLETS DES POSSIBLES','onglets possibles'])assert.ok(models.some(t=>matchesTemplateSearch(t,query)));
 const t=models.find(t=>t.id==='carousel_desp_vae_1');assert.ok(matchesTemplateSearch(t,'carrousel desp vae'));assert.ok(!matchesTemplateSearch(t,'BTS MCO'));
 assert.ok(matchesTemplateSearch(models.find(t=>t.id==='places_aps_1'),'dernieres places aps'));
});
test('session captions use user data and keep DESP initial and VAE separate',()=>{
 const t=models.find(t=>t.id==='session_ssiap1_1'),p=createProject();applySocialTemplate(p,t);
 Object.assign(p.slides[0].content,{startDate:'12 octobre',endDate:'23 octobre',availability:'Deux places disponibles'});
 for(const network of ['facebook','instagram','linkedin']){const text=publicationText(p,t,network);assert.ok(text.includes('Du 12 octobre au 23 octobre'));assert.ok(text.includes('Deux places disponibles'));assert.ok(text.includes('SSIAP 1'));assert.ok(!text.includes('175 h'));assert.ok(!text.includes('🎄'));}
 const vae=models.find(t=>t.id==='carousel_desp_vae_5');applySocialTemplate(p,vae);assert.ok(publicationText(p,vae).includes('jury'));
});
test('legacy placeholder facts are not promoted into publication claims',()=>{
 const t=templates.find(t=>t.id==='new_manifesto_highlight'),p=createProject({formation:'A3P'});
 const automatic=publicationText(p,t);assert.ok(!automatic.includes('175 h'));assert.ok(!automatic.includes('CPF'));
 p.slides[0].content._publicationFields=['duration'];assert.ok(publicationText(p,t).includes('175 h'));
});
test('ZIP contains binary files and UTF-8 caption in a single archive',async()=>{
 const blob=createCarouselZip([{name:'01.png',bytes:new Uint8Array([137,80,78,71,0,255])},{name:'texte-publication.txt',bytes:new TextEncoder().encode('🔥 Formation SSIAP 1')}]);
 const buffer=Buffer.from(await blob.arrayBuffer());assert.equal(buffer.readUInt32LE(0),0x04034b50);assert.equal(buffer.readUInt32LE(buffer.length-22),0x06054b50);assert.equal(buffer.readUInt16LE(buffer.length-14),2);
 writeFileSync('/tmp/studio-social-zip-test.zip',buffer);
});
