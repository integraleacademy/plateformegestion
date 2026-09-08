import {projectCoverRect,checkProfileRect} from './studio-linkedin-preview.js';

export const FACEBOOK_COVER_SIZE={width:1640,height:720};
// Measured from the supplied 941 px iPhone screenshot. The image continues
// behind the white profile panel: its 3:2 crop is taller than the visible area.
// The note and navigation controls also mask the cover on the owner's profile.
const screenshot={width:941,height:630,avatar:{left:271,top:304,size:402},occlusions:[
 {id:'status',left:0,top:0,width:941,height:108},
 {id:'menu',left:20,top:177,width:66,height:60},
 {id:'actions',left:637,top:177,width:270,height:68},
 {id:'note',left:290,top:272,width:364,height:158},
 {id:'camera',left:842,top:498,width:80,height:66},
 {id:'panel',left:0,top:575,width:941,height:55}
]};
const mobile=width=>{const s=width/screenshot.width;return {id:'mobile-'+width,label:`Profil Facebook sur téléphone · ${width} px`,width,height:screenshot.height*s,avatar:Object.fromEntries(Object.entries(screenshot.avatar).map(([k,v])=>[k,v*s])),occlusions:screenshot.occlusions.map(o=>({...o,left:o.left*s,top:o.top*s,width:o.width*s,height:o.height*s}))}};
export const FACEBOOK_PROFILE_FRAMES=[
 {...screenshot,id:'screenshot',label:'Recadrage de la capture iPhone'},mobile(390),mobile(320),
 {id:'desktop',label:'Profil Facebook sur ordinateur',width:851,height:315,avatar:{left:35,top:210,size:180},occlusions:[]}
];
export function checkFacebookProfileRect(rect,frame){
 const result=checkProfileRect(rect,frame);
 const maskedBy=(frame.occlusions||[]).filter(o=>Math.min(rect.left+rect.width,o.left+o.width)>Math.max(rect.left,o.left)+.5&&Math.min(rect.top+rect.height,o.top+o.height)>Math.max(rect.top,o.top)+.5).map(o=>o.id);
 return {...result,maskedBy};
}
export function validateFacebookProfilePreview(node,source=FACEBOOK_COVER_SIZE){
 const canvas=node.getBoundingClientRect(),scale=canvas.width/source.width,errors=[];
 for(const selector of ['.studio-brand-footer__logo','.social-cover-title','.social-cover-intro','.sv-brand__slogan','.sv-footer__site','[data-cover-illustration]']){
  const el=node.querySelector(selector);if(!el){errors.push(`Élément Facebook absent : ${selector}`);continue}
  const r=el.getBoundingClientRect(),rect={left:(r.left-canvas.left)/scale,top:(r.top-canvas.top)/scale,width:r.width/scale,height:r.height/scale};
  if(!rect.width||!rect.height)errors.push(`Élément Facebook invisible : ${selector}`);
  for(const frame of FACEBOOK_PROFILE_FRAMES){
   const check=checkFacebookProfileRect(projectCoverRect(rect,frame,source),frame);
   if(check.cropped)errors.push(`${frame.id} : ${selector} est recadré`);
   if(check.behindAvatar)errors.push(`${frame.id} : ${selector} passe sous la photo de profil`);
   if(check.maskedBy.length)errors.push(`${frame.id} : ${selector} est masqué par ${check.maskedBy.join(', ')}`);
  }
 }
 return errors;
}
export function renderFacebookProfilePreview(data,frame=FACEBOOK_PROFILE_FRAMES[1]){
 const card=document.createElement('div');card.className='facebook-profile-preview';card.style.width=frame.width+'px';
 const banner=document.createElement('div');banner.className='facebook-profile-preview__banner';banner.style.height=frame.height+'px';
 const image=new Image();image.src=data;image.alt='Couverture dans le recadrage du profil Facebook';banner.append(image);card.append(banner);
 const place=(element,rect)=>Object.assign(element.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});
 for(const o of frame.occlusions||[]){const mask=document.createElement('div');mask.className='facebook-profile-preview__mask facebook-profile-preview__'+o.id;place(mask,o);mask.textContent=({status:'08:26',menu:'☰',actions:'⌕   ···',note:'Partagez une note…',camera:'▣'})[o.id]||'';card.append(mask)}
 const avatar=document.createElement('div');avatar.className='facebook-profile-preview__avatar';avatar.textContent='Votre photo';place(avatar,{...frame.avatar,width:frame.avatar.size,height:frame.avatar.size});card.append(avatar);
 const name=document.createElement('p');name.className='facebook-profile-preview__name';name.textContent='Votre profil Facebook';name.style.marginTop=Math.max(20,frame.avatar.top+frame.avatar.size-frame.height+14)+'px';card.append(name);
 return card;
}
