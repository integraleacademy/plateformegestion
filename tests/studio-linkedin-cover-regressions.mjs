import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createProject,ALL_FORMATS} from '../static/studio_visuals/js/studio-store.js';
import {applySocialTemplate,compatibleFormat} from '../static/studio_visuals/js/studio-social-tools.js';
import {LINKEDIN_PROFILE_FRAMES,projectCoverRect,checkProfileRect} from '../static/studio_visuals/js/studio-linkedin-preview.js';
const templates=JSON.parse(readFileSync('static/studio_visuals/data/templates.json')).templates;
test('all five LinkedIn covers select the personal-profile ratio, including an old project',()=>{
 const covers=templates.filter(t=>t.isCover&&t.network==='linkedin');assert.equal(covers.length,5);
 for(const t of covers){
  const project=createProject();project.format={id:'linkedin_cover',width:1512,height:256};
  applySocialTemplate(project,t);assert.equal(project.format.width,1584);assert.equal(project.format.height,396);assert.equal(project.slides[0].logo.width,220);
  assert.equal(compatibleFormat(t,{id:'linkedin_cover',width:1512,height:256}),ALL_FORMATS.linkedin_cover);
 }
});
test('the screenshot regression detects the old hidden logo and cropped illustration',()=>{
 const frame=LINKEDIN_PROFILE_FRAMES[0],oldSize={width:1512,height:256};
 const oldLogo=projectCoverRect({left:315,top:53,width:150,height:150},frame,oldSize);
 assert.equal(checkProfileRect(oldLogo,frame).behindAvatar,true);
 const oldArt=projectCoverRect({left:1272,top:-36,width:360,height:330},frame,oldSize);
 assert.equal(checkProfileRect(oldArt,frame).cropped,true);
});
test('profile checks measure centre cropping and the circular avatar rather than only the canvas',()=>{
 const mobile=LINKEDIN_PROFILE_FRAMES[1];
 assert.ok(projectCoverRect({left:0,top:0,width:50,height:50},mobile).left<0);
 assert.equal(checkProfileRect({left:20,top:75,width:100,height:100},mobile).behindAvatar,true);
 assert.deepEqual(checkProfileRect({left:170,top:10,width:180,height:90},mobile),{cropped:false,behindAvatar:false});
});
