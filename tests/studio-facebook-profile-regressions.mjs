import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createProject,ALL_FORMATS} from '../static/studio_visuals/js/studio-store.js';
import {applySocialTemplate,normalizeCoverProject} from '../static/studio_visuals/js/studio-social-tools.js';
import {SOCIAL_BY_ID} from '../static/studio_visuals/js/studio-social-content.js';
import {FACEBOOK_COVER_SIZE,FACEBOOK_PROFILE_FRAMES,checkFacebookProfileRect} from '../static/studio_visuals/js/studio-facebook-preview.js';
import {projectCoverRect} from '../static/studio_visuals/js/studio-linkedin-preview.js';
const templates=JSON.parse(readFileSync('static/studio_visuals/data/templates.json')).templates;
test('the five Facebook models use a personal-profile canvas and migrate old drafts once',()=>{
 const covers=templates.filter(t=>t.isCover&&t.network==='facebook');assert.equal(covers.length,5);
 for(const t of covers){
  const p=createProject();applySocialTemplate(p,t);
  assert.deepEqual([p.format.width,p.format.height],[1640,720]);assert.equal(p.slides[0].logo.width,240);
  const title=p.slides[0].content.title;p.format={id:'facebook_cover',width:851,height:315};p.slides[0].logo.width=150;p.slides[0].content.introduction=SOCIAL_BY_ID[t.id].introduction;
  normalizeCoverProject(p);assert.equal(p.format,ALL_FORMATS.facebook_cover);assert.equal(p.slides[0].logo.width,240);assert.equal(p.slides[0].content.title,title);
  const once=JSON.stringify(p);normalizeCoverProject(p);assert.equal(JSON.stringify(p),once);
 }
});
test('the supplied Facebook screenshot exposes cropped logo/art and the masked slogan',()=>{
 const frame=FACEBOOK_PROFILE_FRAMES[0],source={width:851,height:315};
 const check=rect=>checkFacebookProfileRect(projectCoverRect(rect,frame,source),frame);
 assert.equal(check({left:55,top:57,width:150,height:150}).cropped,true);
 assert.equal(check({left:603,top:48,width:224,height:180}).cropped,true);
 assert.equal(check({left:244,top:241,width:450,height:22}).behindAvatar,true);
});
test('the profile checks also include the note, owner controls, camera and bottom panel',()=>{
 const frame=FACEBOOK_PROFILE_FRAMES[0];
 for(const id of ['status','menu','actions','note','camera','panel']){
  const o=frame.occlusions.find(o=>o.id===id);assert.ok(checkFacebookProfileRect(o,frame).maskedBy.includes(id));
 }
 assert.deepEqual(FACEBOOK_COVER_SIZE,{width:1640,height:720});
});
