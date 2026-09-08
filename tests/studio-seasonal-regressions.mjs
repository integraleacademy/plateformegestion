import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {SEASONAL_EVENTS,SEASONAL_DESIGNS,renderSeasonalIllustration,renderSeasonalTemplateBody,renderSeasonalCaptionPanel} from '../static/studio_visuals/js/studio-seasonal-templates.js';
import {FORMATS,createProject,normalizeSlideContentForTemplate} from '../static/studio_visuals/js/studio-store.js';
const catalog=JSON.parse(readFileSync(new URL('../static/studio_visuals/data/templates.json',import.meta.url))).templates;
const models=catalog.filter(t=>t.isSeasonal);
test('each of the four holidays has five general designs with complete social copy',()=>{
 assert.equal(models.length,20);assert.equal(new Set(models.map(t=>t.id)).size,20);
 assert.equal(models.filter(t=>t.motion).length,12);
 for(const event of Object.keys(SEASONAL_EVENTS)){
  const group=models.filter(t=>t.seasonalEvent===event);
  assert.equal(group.length,5);assert.equal(new Set(group.map(t=>t.composition)).size,5);
 }
 assert.equal(new Set(SEASONAL_DESIGNS.map(renderSeasonalIllustration)).size,20);
 assert.equal(new Set(SEASONAL_DESIGNS.map(d=>d.socialCopy.facebook)).size,20);
 for(const t of models){
  assert.ok(['preview','ready'].includes(t.status));assert.equal(t.formationPreset,'OR');
  assert.equal(t.renderer,'renderSeasonalTemplate');assert.deepEqual(t.supportedFormats,Object.keys(FORMATS));
  const d=SEASONAL_DESIGNS.find(d=>d.id===t.id);assert.deepEqual(t.contentDefaults,d.contentDefaults);
  const html=renderSeasonalTemplateBody({template:t,slide:{content:{title:'Ancien titre APS'}}});
  assert.ok(html.includes(d.title));assert.equal(html.includes('data-motion='),Boolean(t.motion));
  for(const key of ['title','introduction','cta'])assert.equal(html.split(`data-content-key="${key}"`).length-1,1);
  assert.doesNotMatch(html,/undefined|NaN|175 h|CPF|Faites le premier pas|🛡|\b\d{2}\s*\/\s*\d{2}\b/);
  const {facebook,instagram}=d.socialCopy;
  assert.ok(facebook.length>300);assert.ok(instagram.length<2200);
  assert.match(facebook,/https:\/\/www\.integraleacademy\.com/);assert.match(instagram,/lien en bio/);
  assert.match(facebook,/\p{Extended_Pictographic}/u);assert.match(instagram,/#IntegraleAcademy/);
  assert.doesNotMatch(facebook+instagram,/🛡|\bDM\b|message privé/);
  if(t.seasonalEvent==='bonne_annee')assert.match(facebook,/2027/);
  assert.match(renderSeasonalCaptionPanel(t),/readonly/);
 }
 assert.equal(catalog.filter(t=>t.isBts).length,60);
 assert.equal(catalog.filter(t=>t.isGeneral).length,30);
});
test('switching seasonal models resets automatic copy while preserving manual edits and contact data',()=>{
 const slide=createProject({formation:'APS'}).slides[0];slide.content.footer.website='mon-centre.fr';
 for(const t of models){normalizeSlideContentForTemplate(slide,t);assert.equal(slide.content.title,t.contentDefaults.title);assert.equal(slide.content._autoFormation,'OR');assert.equal(slide.content.footer.website,'mon-centre.fr');}
 slide.content._manual=true;slide.content.title='<img src=x onerror="alert(1)">';slide.content.introduction='Votre projet & vos envies';
 normalizeSlideContentForTemplate(slide,models[0]);const html=renderSeasonalTemplateBody({template:models[0],slide});
 assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('<img src=x'));assert.ok(html.includes('Votre projet &amp; vos envies'));
 assert.equal(renderSeasonalCaptionPanel({id:'bts_mos_supervision'}),'');
});
