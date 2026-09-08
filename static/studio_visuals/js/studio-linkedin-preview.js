// The desktop overlay follows the supplied screenshot. Narrower 3:1 mobile
// frames stress-test centre cropping in addition to the native 4:1 profile.
export const LINKEDIN_PROFILE_FRAMES=[
 {id:'desktop',label:'Profil sur ordinateur · 634 px',width:634,height:158.5,avatar:{left:22,top:84,size:124}},
 {id:'mobile',label:'Simulation mobile · 390 px · recadrage 3:1',width:390,height:130,avatar:{left:16,top:70,size:112}},
 {id:'small',label:'Simulation petit écran · 320 px · recadrage 3:1',width:320,height:320/3,avatar:{left:16,top:51,size:96}}
];
export function projectCoverRect(rect,frame,source={width:1584,height:396}){
 const scale=Math.max(frame.width/source.width,frame.height/source.height);
 return {left:rect.left*scale+(frame.width-source.width*scale)/2,top:rect.top*scale+(frame.height-source.height*scale)/2,width:rect.width*scale,height:rect.height*scale};
}
export function checkProfileRect(rect,frame){
 const {left,top,width,height}=rect,{avatar}=frame,cx=avatar.left+avatar.size/2,cy=avatar.top+avatar.size/2,r=avatar.size/2;
 const nearestX=Math.max(left,Math.min(cx,left+width)),nearestY=Math.max(top,Math.min(cy,top+height));
 return {cropped:left<-.5||top<-.5||left+width>frame.width+.5||top+height>frame.height+.5,behindAvatar:(nearestX-cx)**2+(nearestY-cy)**2<r*r};
}
export function validateLinkedInProfilePreview(node,source={width:1584,height:396}){
 const canvas=node.getBoundingClientRect(),scale=canvas.width/source.width;
 const selectors=['.studio-brand-footer__logo','.social-cover-title','.social-cover-intro','.sv-brand__slogan','.sv-footer__site','[data-cover-illustration]'];
 const errors=[];
 for(const selector of selectors){
  const element=node.querySelector(selector);
  if(!element){errors.push(`Élément LinkedIn absent : ${selector}`);continue}
  const r=element.getBoundingClientRect(),rect={left:(r.left-canvas.left)/scale,top:(r.top-canvas.top)/scale,width:r.width/scale,height:r.height/scale};
  if(!rect.width||!rect.height)errors.push(`Élément invisible : ${selector}`);
  for(const frame of LINKEDIN_PROFILE_FRAMES){
   const check=checkProfileRect(projectCoverRect(rect,frame,source),frame);
   if(check.cropped)errors.push(`${frame.id} : ${selector} est recadré`);
   if(check.behindAvatar)errors.push(`${frame.id} : ${selector} passe sous la photo de profil`);
  }
 }
 return errors;
}
