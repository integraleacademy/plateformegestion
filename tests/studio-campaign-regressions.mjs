import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {CAMPAIGN_EVENTS,CAMPAIGN_DESIGNS,renderCampaignIllustration} from '../static/studio_visuals/js/studio-campaign-templates.js';
import {SEASONAL_DESIGNS,renderSeasonalTemplateBody,renderSeasonalCaptionPanel} from '../static/studio_visuals/js/studio-seasonal-templates.js';
import {FORMATS,createProject,normalizeSlideContentForTemplate} from '../static/studio_visuals/js/studio-store.js';
const catalog=JSON.parse(readFileSync(new URL('../static/studio_visuals/data/templates.json',import.meta.url))).templates;
const models=catalog.filter(t=>t.isCampaign);

test('eight campaigns each supply five unique general models, three animated, and complete social captions',()=>{
 assert.equal(models.length,40);assert.equal(CAMPAIGN_DESIGNS.length,40);
 assert.equal(new Set(catalog.map(t=>t.id)).size,catalog.length);
 assert.equal(new Set(CAMPAIGN_DESIGNS.map(d=>d.art)).size,40);
 assert.equal(new Set(CAMPAIGN_DESIGNS.map(d=>d.socialCopy.facebook)).size,40);
 assert.equal(Object.keys(CAMPAIGN_EVENTS).length,8);
 for(const event of Object.keys(CAMPAIGN_EVENTS)){
  const group=models.filter(t=>t.seasonalEvent===event);
  assert.equal(group.length,5);assert.equal(group.filter(t=>t.motion).length,3);
  assert.equal(new Set(group.map(t=>t.composition)).size,5);
 }
 for(const t of models){
  assert.equal(t.isSeasonal,true);assert.equal(t.formationPreset,'OR');assert.equal(t.status,'ready');
  assert.deepEqual(t.supportedFormats,Object.keys(FORMATS));
  const d=CAMPAIGN_DESIGNS.find(d=>d.id===t.id);assert.ok(SEASONAL_DESIGNS.includes(d));
  assert.deepEqual(t.contentDefaults,d.contentDefaults);
  const slide=createProject({formation:'APS'}).slides[0];normalizeSlideContentForTemplate(slide,t);
  assert.equal(slide.content.title,d.title);assert.equal(slide.content._autoFormation,'OR');
  const html=renderSeasonalTemplateBody({template:t,slide});
  assert.ok(html.includes(d.title));assert.equal(html.includes('data-motion='),Boolean(t.motion));
  for(const key of ['title','introduction','cta'])assert.equal(html.split(`data-content-key="${key}"`).length-1,1);
  assert.doesNotMatch(html,/undefined|NaN|Faites le premier pas|🛡|🎄|\b\d{2}\s*\/\s*\d{2}\b/);
  assert.match(renderCampaignIllustration(d),/viewBox="0 0 500 360"/);
  const {facebook,instagram}=d.socialCopy;
  assert.ok(facebook.length>300);assert.ok(instagram.length<2200);
  assert.match(facebook,/https:\/\/www\.integraleacademy\.com/);assert.match(instagram,/lien en bio/);
  assert.match(facebook,/\p{Extended_Pictographic}/u);assert.match(instagram,/#IntegraleAcademy/);
  assert.doesNotMatch(facebook+instagram,/🛡|🎄|\bDM\b|message privé|\d+\s*%/);
  assert.match(renderSeasonalCaptionPanel(t),/Copier le texte Instagram/);
 }
 assert.equal(catalog.filter(t=>t.isSeasonal&&!t.isCampaign).length,20);
 assert.equal(catalog.filter(t=>t.isGeneral).length,30);
});

test('event copy avoids invented schedules and states the right publication context',()=>{
 assert.match(CAMPAIGN_EVENTS.reussite.window,/Après l’annonce des résultats/);
 for(const d of CAMPAIGN_DESIGNS.filter(d=>d.event==='portes_ouvertes')){
  assert.match(d.socialCopy.facebook,/modalités|possibilités|organiser/);
  assert.doesNotMatch(d.socialCopy.facebook,/\d{1,2}\s*(h|mai|juin|septembre)|inscription gratuite|entrée libre|sans rendez-vous/i);
 }
 assert.throws(()=>renderCampaignIllustration({event:'paques',art:'unknown'}),/inconnue/);
});
